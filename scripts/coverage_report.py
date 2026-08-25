#!/usr/bin/env python3
"""What ygopro-core can tell us, versus what the harness actually uses.

    python scripts/coverage_report.py
    python scripts/coverage_report.py --missing-only

Finding gaps by watching duels and noticing something looks wrong does not
scale and never terminates - every fix reveals the next omission. The core's
source is vendored, so the set of things it can report is enumerable, and this
walks it directly:

- every `QUERY_*` field `card::get_infos` can serialise, against the flags
  `engine/board.py` actually asks for;
- every `MSG_*` the core emits, against what we name, decode, and put in front
  of the agent.

A field we do not request is not missing data we could go and find later - the
core simply never wrote it, and the board silently reads as though the card had
no such property.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CORE = ROOT / "vendor" / "ygopro-core"
HEADER = CORE / "ocgapi_constants.h"

#: Where each kind of use lives, so "used" means something specific.
NAMED = ROOT / "engine" / "constants.py"
DECODERS = [ROOT / "engine" / "messages.py", ROOT / "engine" / "board.py"]
SHOWN = [ROOT / "llm" / "events.py", ROOT / "engine" / "render.py",
         ROOT / "agents" / "llm_agent.py", ROOT / "viz" / "duel_log.py"]

#: Messages that carry nothing an agent could act on, with the reason. Being
#: explicit here is the point: an unlisted message is a gap, not an oversight.
NOT_AGENT_VISIBLE = {
    "MSG_RETRY": "protocol - our last answer was rejected",
    "MSG_WAITING": "protocol - the other side is thinking",
    "MSG_START": "protocol - duel setup",
    "MSG_UPDATE_DATA": "bulk state push, consumed as board state",
    "MSG_UPDATE_CARD": "bulk state push, consumed as board state",
    "MSG_RELOAD_FIELD": "bulk state push, consumed as board state",
    "MSG_TAG_SWAP": "tag duels, not played here",
    "MSG_MATCH_KILL": "match play, not played here",
    "MSG_AI_NAME": "cosmetic - the puzzle's name for the opponent",
    "MSG_SHOW_HINT": "puzzle author's note, shown as puzzle text already",
}


def _text(paths) -> str:
    return "\n".join(p.read_text() for p in paths if p.exists())


def header_defines(prefix: str) -> dict[str, int]:
    out = {}
    for m in re.finditer(rf"^#define ({prefix}[A-Z0-9_]+)\s+(0x[0-9a-fA-F]+|\d+)\s*$",
                         HEADER.read_text(), re.M):
        raw = m.group(2)
        out[m.group(1)] = int(raw, 16) if raw.lower().startswith("0x") else int(raw)
    return out


def query_coverage() -> list[tuple[str, int, bool]]:
    """Every QUERY_* the core serialises, and whether we ask for it.

    Tests the *value* of the flags we send, not the text of the expression
    that builds them - so a field cannot count as covered because its name
    happens to appear in a comment, and a refactor of the expression cannot
    make coverage look like it changed when it did not.
    """
    from engine.board import FIELD_FLAGS, LIST_FLAGS

    serialised = set(re.findall(r"QUERY_[A-Z0-9_]+", (CORE / "card.cpp").read_text()))
    asked = FIELD_FLAGS | LIST_FLAGS
    out = []
    for name, val in sorted(header_defines("QUERY_").items(), key=lambda kv: kv[1]):
        if name == "QUERY_END" or name not in serialised:
            continue
        out.append((name, val, bool(asked & val)))
    return out


def message_coverage() -> list[tuple[str, int, bool, bool, bool]]:
    """Every MSG_* the core emits, and how far it gets through the harness.

    "Shown" means narrated to the agent as an event. Decisions are excluded
    from that count and reported separately: the policy *answers* those, which
    is a stronger form of handling than describing them, and counting them as
    unshown made the gap look a third larger than it was.
    """
    emitted = set()
    for f in CORE.glob("*.cpp"):
        emitted |= set(re.findall(r"new_message\((MSG_[A-Z0-9_]+)\)", f.read_text()))
    defined = header_defines("MSG_")
    named = set(re.findall(r"^(MSG_[A-Z0-9_]+)\s*=", NAMED.read_text(), re.M))
    decoded_src, shown_src = _text(DECODERS), _text(SHOWN)
    rows = []
    for name in sorted(emitted, key=lambda n: defined.get(n, 999)):
        rows.append((
            name, defined.get(name, -1),
            name in named,
            name in decoded_src,
            name in shown_src,
        ))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--missing-only", action="store_true")
    args = ap.parse_args()

    if not HEADER.exists():
        print("core not vendored - nothing to compare against", file=sys.stderr)
        return 2

    q = query_coverage()
    have = sum(1 for _n, _v, ok in q if ok)
    print(f"QUERY fields: {have}/{len(q)} requested\n")
    print(f"  {'field':22} {'requested':>10}")
    for name, _val, ok in q:
        if args.missing_only and ok:
            continue
        print(f"  {name:22} {'yes' if ok else 'NO':>10}")

    from engine.constants import DECISION_MESSAGES
    import engine.constants as K

    m = message_coverage()
    named = sum(1 for r in m if r[2])

    def kind(name: str) -> str:
        if getattr(K, name, None) in DECISION_MESSAGES:
            return "decision"
        if name in NOT_AGENT_VISIBLE:
            return "skip"
        return "event"

    events = [r for r in m if kind(r[0]) == "event"]
    decisions = [r for r in m if kind(r[0]) == "decision"]
    shown = sum(1 for r in events if r[4])

    print(f"\nMESSAGES the core emits: {len(m)}")
    print(f"  named            : {named}/{len(m)}")
    print(f"  decisions answered: {len(decisions)} (the policy replies to these)")
    print(f"  events narrated   : {shown}/{len(events)}")
    print(f"  nothing to act on : {len(m) - len(events) - len(decisions)}\n")
    print(f"  {'id':>4}  {'message':28} {'kind':>9} {'decoded':>8} {'shown':>6}")
    for name, mid, _is_named, is_decoded, is_shown in m:
        k = kind(name)
        if args.missing_only and (k != "event" or is_shown):
            continue
        tag = f"  ({NOT_AGENT_VISIBLE[name]})" if k == "skip" else ""
        print(f"  {mid:>4}  {name:28} {k:>9} "
              f"{'y' if is_decoded else '-':>8} {'y' if is_shown else '-':>6}{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
