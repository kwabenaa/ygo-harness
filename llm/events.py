"""Turning the engine's informational messages into something the agent reads.

The board tells you what the field looks like now. It cannot tell you what
just happened to get there, and in this game that difference decides the next
move: an effect being negated, a summon being interrupted, a card being
revealed to you, a coin coming up tails. `scripts/coverage_report.py` counts
how much of the core's message stream reaches the agent; this module is what
moves that number.

Two things were missing and are worth naming.

**The agent did not know what it was being asked.** `MSG_HINT` with
`HINT_SELECTMSG` states the purpose of the selection that follows, and without
it a chain window arrives as a bare list of cards with "decline to respond"
appended. Reading a transcript, the model spent its reasoning budget guessing
at the question rather than answering it.

**The agent only ever saw its own actions.** `history` was appended by the
policy itself, so everything the opponent or the engine did was invisible
except as an altered board.
"""

from __future__ import annotations

import os
import re
import struct
from functools import lru_cache
from pathlib import Path

from engine import constants as K

HINT_MESSAGE = 2
HINT_SELECTMSG = 3
HINT_OPSELECTED = 4

LOCATIONS = {
    K.LOCATION_DECK: "Deck", K.LOCATION_HAND: "hand",
    K.LOCATION_MZONE: "monster zone", K.LOCATION_SZONE: "spell/trap zone",
    K.LOCATION_GRAVE: "GY", K.LOCATION_REMOVED: "banished",
    K.LOCATION_EXTRA: "Extra Deck",
}


class _R:
    def __init__(self, b: bytes):
        self.b, self.i = b, 0

    def u8(self):
        v = self.b[self.i]; self.i += 1; return v

    def u16(self):
        (v,) = struct.unpack_from("<H", self.b, self.i); self.i += 2; return v

    def u32(self):
        (v,) = struct.unpack_from("<I", self.b, self.i); self.i += 4; return v

    def u64(self):
        (v,) = struct.unpack_from("<Q", self.b, self.i); self.i += 8; return v

    def loc(self):
        """controller, location, sequence, position - 10 bytes."""
        con, loc = self.u8(), self.u8()
        seq, pos = self.u32(), self.u32()
        return con, loc, seq, pos


@lru_cache(maxsize=1)
def _system_strings() -> dict[int, str]:
    """EDOPro's numbered system strings, when an install is available.

    These are what a `HINT_SELECTMSG` description resolves to. They are not in
    the pinned data - they ship with the client - so this degrades to raw ids
    rather than failing, exactly like the EDOPro-dependent tests.
    """
    root = Path(os.environ.get(
        "EDOPRO_DIR", Path.home() / "Applications" / "ProjectIgnis")).expanduser()
    path = root / "config" / "strings.conf"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"!system (\d+) (.+)", line.strip())
        if m:
            out[int(m.group(1))] = m.group(2).strip()
    return out


def describe_hint(desc: int, db) -> str:
    """Resolve a description id to text: a card name, a system string, or raw.

    Descriptions above the card-code boundary encode "this card's Nth effect",
    so the card name alone is the useful part.
    """
    if desc >= 1 << 20:
        code = desc >> 20 if desc >> 20 else desc
        name = db.name(code)
        if not name.startswith("<"):
            return f'"{name}"'
    strings = _system_strings()
    if desc in strings:
        return strings[desc]
    name = db.name(desc)
    return f'"{name}"' if not name.startswith("<") else f"effect #{desc}"


def _who(player: int, viewer: int) -> str:
    return "you" if player == viewer else "opponent"


def describe(msg, db, viewer: int) -> str | None:
    """One line of English for an informational message, or None to skip.

    Returning None is the default: most of the stream is bookkeeping, and a
    history full of "a card moved" crowds out the lines that change a decision.
    """
    p, mid = msg.payload, msg.id
    try:
        r = _R(p)
        if mid == K.MSG_HINT:
            kind, player, desc = r.u8(), r.u8(), r.u64()
            if kind == HINT_SELECTMSG and player == viewer:
                return f"you are being asked: {describe_hint(desc, db)}"
            if kind == HINT_OPSELECTED:
                return f"{_who(player, viewer)} chose {describe_hint(desc, db)}"
            return None

        if mid in (K.MSG_SUMMONING, K.MSG_SPSUMMONING, K.MSG_FLIPSUMMONING):
            code = r.u32()
            con, _loc, _seq, _pos = r.loc()
            how = {K.MSG_SUMMONING: "Normal Summons",
                   K.MSG_SPSUMMONING: "Special Summons",
                   K.MSG_FLIPSUMMONING: "Flip Summons"}[mid]
            return f"{_who(con, viewer)} {how} {db.name(code)}"

        if mid in (K.MSG_DAMAGE, K.MSG_RECOVER, K.MSG_PAY_LPCOST):
            player, amount = r.u8(), r.u32()
            verb = {K.MSG_DAMAGE: "takes", K.MSG_RECOVER: "gains",
                    K.MSG_PAY_LPCOST: "pays"}[mid]
            return f"{_who(player, viewer)} {verb} {amount} LP"

        if mid in (K.MSG_CHAIN_NEGATED, K.MSG_CHAIN_DISABLED):
            word = "negated" if mid == K.MSG_CHAIN_NEGATED else "disabled"
            return f"chain link {r.u8()} was {word}"

        if mid == K.MSG_MISSED_EFFECT:
            _con, _loc, _seq, _pos = r.loc()
            return f"{db.name(r.u32())} missed its timing"

        if mid == K.MSG_ATTACK_DISABLED:
            return "the attack was negated"

        if mid == K.MSG_TOSS_COIN:
            player, count = r.u8(), r.u8()
            flips = ["heads" if r.u8() else "tails" for _ in range(count)]
            return f"{_who(player, viewer)} tossed {', '.join(flips)}"

        if mid == K.MSG_TOSS_DICE:
            player, count = r.u8(), r.u8()
            rolls = [str(r.u8()) for _ in range(count)]
            return f"{_who(player, viewer)} rolled {', '.join(rolls)}"

        if mid == K.MSG_CONFIRM_CARDS:
            player, count = r.u8(), r.u32()
            names = []
            for _ in range(count):
                code = r.u32()
                r.u8(), r.u8(), r.u32()
                names.append(db.name(code))
            if not names:
                return None
            return f"revealed to {_who(player, viewer)}: {', '.join(names)}"

        if mid in (K.MSG_ADD_COUNTER, K.MSG_REMOVE_COUNTER):
            _ctype = r.u16()
            con, _loc, _seq = r.u8(), r.u8(), r.u8()
            n = r.u16()
            verb = "gains" if mid == K.MSG_ADD_COUNTER else "loses"
            return (f"a card {_who(con, viewer)} controls {verb} "
                    f"{n} counter{'s' if n != 1 else ''}")
    except (IndexError, struct.error):
        # A payload we cannot read is a decoder bug, not a reason to stop the
        # duel. Report it as such rather than inventing an event.
        return f"<undecodable {msg.name}>"
    return None


def recent(duel, db, viewer: int, limit: int = 12) -> list[str]:
    """Everything worth telling the agent since it last acted.

    Reads `duel.since_last_decision`, which the duel loop maintains precisely
    because the message buffer is cleared at every decision point.
    """
    out = []
    for m in duel.since_last_decision:
        line = describe(m, db, viewer)
        if line and (not out or out[-1] != line):
            out.append(line)
    return out[-limit:]
