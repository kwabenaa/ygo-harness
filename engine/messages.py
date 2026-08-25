"""Decoders for the engine messages that ask for a decision.

Layouts are transcribed from ygopro-core's playerop.cpp. One trap worth
naming: in MSG_SELECT_IDLECMD the *repositionable* list writes `sequence` as
uint8 while every other list in the same message writes uint32. Getting that
wrong silently desynchronises the rest of the parse.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# Idle command types (playerop.cpp validator). Response is (index << 16) | type.
IDLE_SUMMON = 0
IDLE_SPSUMMON = 1
IDLE_REPOSITION = 2
IDLE_MSET = 3
IDLE_SSET = 4
IDLE_ACTIVATE = 5
IDLE_TO_BP = 6
IDLE_TO_EP = 7
IDLE_SHUFFLE_HAND = 8

IDLE_NAMES = {
    IDLE_SUMMON: "summon", IDLE_SPSUMMON: "special summon",
    IDLE_REPOSITION: "reposition", IDLE_MSET: "set monster",
    IDLE_SSET: "set spell/trap", IDLE_ACTIVATE: "activate",
    IDLE_TO_BP: "to battle phase", IDLE_TO_EP: "to end phase",
    IDLE_SHUFFLE_HAND: "shuffle hand",
}


@dataclass
class CardRef:
    code: int
    controller: int
    location: int
    sequence: int
    description: int = 0
    client_mode: int = 0


@dataclass
class IdleCmd:
    """The legal-action menu for a main phase decision point."""
    player: int
    summonable: list[CardRef]
    spsummonable: list[CardRef]
    repositionable: list[CardRef]
    msetable: list[CardRef]
    ssetable: list[CardRef]
    activatable: list[CardRef]
    to_bp: bool
    to_ep: bool
    can_shuffle: bool

    def actions(self) -> list[tuple[int, int, CardRef | None]]:
        """Flatten to (type, index, card) triples - the action menu."""
        out: list[tuple[int, int, CardRef | None]] = []
        for t, lst in (
            (IDLE_SUMMON, self.summonable),
            (IDLE_SPSUMMON, self.spsummonable),
            (IDLE_REPOSITION, self.repositionable),
            (IDLE_MSET, self.msetable),
            (IDLE_SSET, self.ssetable),
            (IDLE_ACTIVATE, self.activatable),
        ):
            out.extend((t, i, c) for i, c in enumerate(lst))
        if self.to_bp:
            out.append((IDLE_TO_BP, 0, None))
        if self.to_ep:
            out.append((IDLE_TO_EP, 0, None))
        if self.can_shuffle:
            out.append((IDLE_SHUFFLE_HAND, 0, None))
        return out

    @staticmethod
    def encode(cmd_type: int, index: int = 0) -> bytes:
        return struct.pack("<i", (index << 16) | cmd_type)


class _Reader:
    def __init__(self, buf: bytes):
        self.buf, self.off = buf, 0

    def u8(self) -> int:
        v = self.buf[self.off]; self.off += 1; return v

    def u32(self) -> int:
        (v,) = struct.unpack_from("<I", self.buf, self.off); self.off += 4; return v

    def u64(self) -> int:
        (v,) = struct.unpack_from("<Q", self.buf, self.off); self.off += 8; return v

    def cards(self, *, seq_u8: bool = False, with_desc: bool = False) -> list[CardRef]:
        out = []
        for _ in range(self.u32()):
            code, con, loc = self.u32(), self.u8(), self.u8()
            seq = self.u8() if seq_u8 else self.u32()
            desc = self.u64() if with_desc else 0
            mode = self.u8() if with_desc else 0
            out.append(CardRef(code, con, loc, seq, desc, mode))
        return out


def parse_idlecmd(payload: bytes) -> IdleCmd:
    r = _Reader(payload)
    player = r.u8()
    summonable = r.cards()
    spsummonable = r.cards()
    repositionable = r.cards(seq_u8=True)   # uint8 sequence - see module docstring
    msetable = r.cards()
    ssetable = r.cards()
    activatable = r.cards(with_desc=True)
    return IdleCmd(
        player, summonable, spsummonable, repositionable, msetable, ssetable,
        activatable, bool(r.u8()), bool(r.u8()), bool(r.u8()),
    )


@dataclass
class SelectCard:
    """A "choose N of these cards" decision point."""
    player: int
    cancelable: bool
    min: int
    max: int
    codes: list[int]

    @staticmethod
    def encode(indices: list[int]) -> bytes:
        """Response layout (playerop.cpp parse_response_cards):
        int32 type, uint32 count, then `count` indices - all starting at
        byte offset 8. Type 0 means uint32-wide indices.
        """
        return struct.pack("<iI", 0, len(indices)) + b"".join(
            struct.pack("<I", i) for i in indices
        )

    @staticmethod
    def cancel() -> bytes:
        return struct.pack("<i", -1)


def parse_select_card(payload: bytes) -> SelectCard:
    r = _Reader(payload)
    player, cancelable = r.u8(), bool(r.u8())
    mn, mx, count = r.u32(), r.u32(), r.u32()
    # Each entry is a code plus an info_location blob; we only need codes for
    # now, and the blob width varies, so stop parsing after the counts.
    codes = []
    try:
        for _ in range(count):
            codes.append(r.u32())
            r.off += 4  # info_location
    except (IndexError, struct.error):
        pass
    return SelectCard(player, cancelable, mn, mx, codes)
