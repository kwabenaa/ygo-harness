"""Human-readable turn-by-turn transcript of a duel.

Built by narrating the engine's message stream. This is the artifact you read
to answer "what actually happened?" - which, given how quietly this engine
fails, is usually the fastest way to find out that something is wrong. It was
a transcript that would have revealed no card ever activating.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from engine.constants import (
    LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND,
    LOCATION_MZONE, LOCATION_REMOVED, LOCATION_SZONE, MSG_CHAINED,
    MSG_CHAINING, MSG_CHAIN_SOLVED, MSG_DRAW, MSG_NEW_PHASE, MSG_NEW_TURN,
    MSG_WIN, WIN_REASON_DECKOUT, WIN_REASON_LP,
)

MSG_MOVE = 50
MSG_POS_CHANGE = 53
MSG_SET = 54
MSG_SUMMONING = 60
MSG_SPSUMMONING = 62
MSG_FLIPSUMMONING = 64
MSG_DAMAGE = 91
MSG_RECOVER = 92
MSG_LPUPDATE = 94
MSG_ATTACK = 110
MSG_BATTLE = 111

PHASES = {
    0x01: "Draw", 0x02: "Standby", 0x04: "Main 1", 0x08: "Battle Start",
    0x10: "Battle Step", 0x20: "Damage", 0x40: "Damage Calc",
    0x80: "Battle", 0x100: "Main 2", 0x200: "End",
}

LOC = {
    LOCATION_DECK: "Deck", LOCATION_HAND: "hand", LOCATION_MZONE: "field",
    LOCATION_SZONE: "S/T", LOCATION_GRAVE: "GY", LOCATION_REMOVED: "banished",
    LOCATION_EXTRA: "Extra",
}

#: loc_info is controler(1) location(1) sequence(4) position(4).
LOC_INFO = 10


def _u8(b, o):  return b[o]
def _u16(b, o): return struct.unpack_from("<H", b, o)[0]
def _u32(b, o): return struct.unpack_from("<I", b, o)[0]


@dataclass
class DuelLog:
    """Narrates a message stream into a readable transcript."""
    db: object
    names: tuple[str, str] = ("Player 0", "Player 1")
    lines: list[str] = field(default_factory=list)
    turn: int = 0
    turn_player: int = 0

    def _who(self, p: int) -> str:
        return self.names[p] if p in (0, 1) else f"P{p}"

    def _card(self, code: int) -> str:
        return self.db.name(code) if code else "a face-down card"

    def add(self, text: str, indent: int = 1) -> None:
        self.lines.append("  " * indent + text)

    def feed(self, msg) -> None:
        p, mid = msg.payload, msg.id
        try:
            self._feed(mid, p)
        except (IndexError, struct.error):
            pass          # truncated payload: skip rather than abort the log

    def _feed(self, mid: int, p: bytes) -> None:
        if mid == MSG_NEW_TURN:
            self.turn += 1
            self.turn_player = _u8(p, 0)
            self.lines.append("")
            self.lines.append(f"=== Turn {self.turn} - {self._who(self.turn_player)} ===")

        elif mid == MSG_NEW_PHASE:
            ph = PHASES.get(_u16(p, 0), f"phase {_u16(p, 0)}")
            if ph in ("Main 1", "Battle", "Main 2", "End"):
                self.add(f"-- {ph} --", 1)

        elif mid == MSG_DRAW:
            who, n = _u8(p, 0), _u32(p, 1)
            codes = [_u32(p, 5 + i * 8) for i in range(n)] if len(p) >= 5 + n * 8 else []
            shown = ", ".join(self._card(c) for c in codes if c)
            self.add(f"{self._who(who)} draws {n}" + (f": {shown}" if shown else ""), 2)

        elif mid in (MSG_SUMMONING, MSG_SPSUMMONING, MSG_FLIPSUMMONING):
            verb = {MSG_SUMMONING: "Normal Summons",
                    MSG_SPSUMMONING: "Special Summons",
                    MSG_FLIPSUMMONING: "Flip Summons"}[mid]
            code, who = _u32(p, 0), _u8(p, 4)
            self.add(f"{self._who(who)} {verb} {self._card(code)}", 2)

        elif mid == MSG_SET:
            code, who = _u32(p, 0), _u8(p, 4)
            self.add(f"{self._who(who)} sets a card", 2)

        elif mid == MSG_CHAINING:
            code, who = _u32(p, 0), _u8(p, 4)
            link = _u32(p, 4 + LOC_INFO + 1 + 1 + 4 + 8) if len(p) > 28 else 0
            self.add(f"{self._who(who)} activates {self._card(code)}"
                     + (f"  (chain link {link})" if link > 1 else ""), 2)

        elif mid == MSG_CHAIN_SOLVED:
            self.add(f"chain link {_u8(p, 0)} resolves", 3)

        elif mid == MSG_ATTACK:
            who = _u8(p, 0)
            if len(p) >= LOC_INFO * 2 and _u8(p, LOC_INFO + 1) != 0:
                self.add(f"{self._who(who)} attacks", 2)
            else:
                self.add(f"{self._who(who)} attacks directly", 2)

        elif mid == MSG_DAMAGE:
            who, amt = _u8(p, 0), _u32(p, 1)
            self.add(f"{self._who(who)} takes {amt} damage", 3)

        elif mid == MSG_RECOVER:
            who, amt = _u8(p, 0), _u32(p, 1)
            self.add(f"{self._who(who)} gains {amt} LP", 3)

        elif mid == MSG_WIN:
            who, reason = _u8(p, 0), (_u8(p, 1) if len(p) > 1 else None)
            why = {WIN_REASON_LP: "life points reached 0",
                   WIN_REASON_DECKOUT: "opponent decked out"}.get(reason, f"reason {reason}")
            self.lines.append("")
            self.lines.append(f"*** {self._who(who)} WINS - {why} ***")

    def render(self) -> str:
        return "\n".join(self.lines)

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.render() + "\n")
