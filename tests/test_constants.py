"""Guard against drift between our constants and ygopro-core's header.

These are hand-transcribed from ocgapi_constants.h. A wrong message id does
not raise - it silently misroutes a decision to the wrong decoder, which is
about the worst failure mode available here. So check them all.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import engine.constants as K

HEADER = Path(__file__).parent.parent / "vendor" / "ygopro-core" / "ocgapi_constants.h"

PREFIXES = ("MSG_", "LOCATION_", "POS_", "TYPE_", "DUEL_")


def header_values() -> dict[str, int]:
    text = HEADER.read_text()
    out = {}
    for m in re.finditer(r"#define\s+([A-Z][A-Z0-9_]*)\s+(0x[0-9a-fA-F]+|\d+)\b", text):
        raw = m.group(2)
        # C literal rules: 0x.. is hex, a leading 0 means OCTAL (the
        # LINK_MARKER_* defines rely on this - 0010 is 8, not 10), otherwise
        # decimal.
        if raw.lower().startswith("0x"):
            val = int(raw, 16)
        elif len(raw) > 1 and raw.startswith("0"):
            val = int(raw, 8)
        else:
            val = int(raw, 10)
        out[m.group(1)] = val
    out.update(header_expressions(text, out))
    return out


def header_expressions(text: str, literals: dict[str, int]) -> dict[str, int]:
    """Resolve `#define NAME (A | B | C)` composites.

    The ruleset presets - DUEL_MODE_MR1..MR5, DUEL_MODE_SPEED,
    DUEL_MODE_RUSH - are composed in the header rather than written as
    literals, so the literal-only scan above cannot see them. We compose them
    too, in engine/constants.py, and a composition that silently stops
    matching theirs would select the wrong ruleset without raising: a puzzle
    would load under Master Rule 3 zoning and simply offer the wrong zones.

    Resolution is iterative because some presets reference others
    (DUEL_MODE_GOAT builds on DUEL_MODE_MR1).
    """
    exprs = {
        m.group(1): m.group(2)
        for m in re.finditer(
            r"#define\s+([A-Z][A-Z0-9_]*)\s+\(([A-Z0-9_|\s]+)\)\s*$",
            text, re.MULTILINE,
        )
    }
    known = dict(literals)
    for _ in range(len(exprs) + 1):
        progressed = False
        for name, body in exprs.items():
            if name in known:
                continue
            parts = [t.strip() for t in body.split("|")]
            if all(t in known for t in parts):
                val = 0
                for t in parts:
                    val |= known[t]
                known[name] = val
                progressed = True
        if not progressed:
            break
    return {k: v for k, v in known.items() if k in exprs}


@pytest.mark.skipif(not HEADER.exists(), reason="core not vendored")
def test_constants_match_header():
    truth = header_values()
    ours = {
        k: v for k, v in vars(K).items()
        if k.startswith(PREFIXES) and isinstance(v, int)
    }
    assert ours, "no constants found"
    mismatched = {
        k: (v, truth[k]) for k, v in ours.items()
        if k in truth and truth[k] != v
    }
    assert not mismatched, f"constants disagree with header: {mismatched}"


@pytest.mark.skipif(not HEADER.exists(), reason="core not vendored")
def test_no_invented_constants():
    truth = header_values()
    # Constants the header defines as expressions rather than literals, plus
    # MASTER_RULE_5 which is our own composition.
    COMPOSED = {"POS_FACEDOWN", "POS_FACEUP", "POS_ATTACK", "POS_DEFENSE",
                "LOCATION_ONFIELD", "MASTER_RULE_5"}
    unknown = [
        k for k, v in vars(K).items()
        if k.startswith(PREFIXES) and isinstance(v, int)
        and k not in truth and k not in COMPOSED
    ]
    assert not unknown, f"not present in header: {unknown}"


def test_decision_messages_are_known():
    for mid in K.DECISION_MESSAGES:
        assert mid in K.MSG_NAMES, f"decision message {mid} has no name"
