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
    -1: "decline to respond",
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


@dataclass
class SelectPlace:
    """A "choose a zone" decision point (MSG_SELECT_PLACE / MSG_SELECT_DISFIELD).

    `flag` is a bitmask of *unavailable* zones - a set bit means you may NOT
    place there. Bit layout is relative to the player being asked:

        bits  0-7   your monster zones
        bits  8-15  your spell/trap zones
        bits 16-23  opponent monster zones
        bits 24-31  opponent spell/trap zones

    Monster zones are 0-6, spell/trap zones 0-7 (playerop.cpp validator).
    """
    player: int
    count: int
    flag: int

    def available(self) -> list[tuple[int, int, int]]:
        """Legal (player, location, sequence) placements."""
        from .constants import LOCATION_MZONE, LOCATION_SZONE
        out = []
        for is_opp in (0, 1):
            for loc, maxseq in ((LOCATION_MZONE, 7), (LOCATION_SZONE, 8)):
                for seq in range(maxseq):
                    bit = 1 << seq
                    if loc == LOCATION_SZONE:
                        bit <<= 8
                    if is_opp:
                        bit <<= 16
                    if not (self.flag & bit):
                        who = (1 - self.player) if is_opp else self.player
                        out.append((who, loc, seq))
        return out

    @staticmethod
    def encode(placements: list[tuple[int, int, int]]) -> bytes:
        return b"".join(bytes([p, loc, seq]) for p, loc, seq in placements)


def parse_select_place(payload: bytes) -> SelectPlace:
    r = _Reader(payload)
    return SelectPlace(r.u8(), r.u8(), r.u32())


class SelectUnselect:
    """MSG_SELECT_UNSELECT_CARD - the iterative select/unselect picker.

    Despite the name it does NOT share a response format with MSG_SELECT_CARD.
    It takes exactly one index per round-trip: `int32 count` (which must be
    literally 1 - the validator rejects 0 and anything > 1) followed by
    `int32 index` into the concatenated select_cards + unselect_cards lists.
    -1 finishes, but only when the prompt is cancelable or finishable.
    """

    @staticmethod
    def encode(index: int) -> bytes:
        return struct.pack("<ii", 1, index)

    @staticmethod
    def finish() -> bytes:
        return struct.pack("<i", -1)


@dataclass
class SelectPosition:
    """MSG_SELECT_POSITION - which battle position to summon in.

    `positions` is a bitmask of allowed positions. The response must be a
    single bit that is set in that mask; a zero response is never valid,
    which is a quiet way to loop forever on MSG_RETRY.
    """
    player: int
    code: int
    positions: int

    #: Preference order when nothing smarter is available. Face-up attack is
    #: the usual default for a summon.
    PREFERENCE = (0x1, 0x4, 0x8, 0x2)   # up-ATK, up-DEF, down-DEF, down-ATK

    def available(self) -> list[int]:
        return [p for p in self.PREFERENCE if self.positions & p]

    @staticmethod
    def encode(position: int) -> bytes:
        return struct.pack("<i", position)


def parse_select_position(payload: bytes) -> SelectPosition:
    r = _Reader(payload)
    return SelectPosition(r.u8(), r.u32(), r.u8())


@dataclass
class SelectOption:
    """MSG_SELECT_OPTION - pick among a card's alternative effects."""
    player: int
    count: int

    @staticmethod
    def encode(index: int) -> bytes:
        return struct.pack("<i", index)


def parse_select_option(payload: bytes) -> SelectOption:
    r = _Reader(payload)
    return SelectOption(r.u8(), r.u8())


@dataclass
class SelectChain:
    """MSG_SELECT_CHAIN - "do you want to respond?"

    This is the most interesting decision type in the game: it is where
    handtraps and quick effects are spent, and where a plan meets an
    opponent's interruption.

    `forced` matters. When it is set the effect is mandatory and -1 is
    rejected, so a policy that always declines loops on MSG_RETRY forever.
    """
    player: int
    spe_count: int
    forced: bool
    hint_timing: int
    other_timing: int
    options: list[CardRef]

    def can_decline(self) -> bool:
        return not self.forced

    @staticmethod
    def encode(index: int) -> bytes:
        return struct.pack("<i", index)

    @staticmethod
    def decline() -> bytes:
        return struct.pack("<i", -1)


def parse_select_chain(payload: bytes) -> SelectChain:
    r = _Reader(payload)
    player, spe_count, forced = r.u8(), r.u8(), bool(r.u8())
    hint, other = r.u32(), r.u32()
    opts = []
    for _ in range(r.u32()):
        code, con, loc = r.u32(), r.u8(), r.u8()
        seq, pos = r.u32(), r.u32()      # loc_info tail
        desc, mode = r.u64(), r.u8()
        opts.append(CardRef(code, con, loc, seq, desc, mode))
    return SelectChain(player, spe_count, forced, hint, other, opts)


# Battle command types (playerop.cpp validator). Response is (index << 16) | type,
# the same encoding as idle commands.
BATTLE_ACTIVATE = 0
BATTLE_ATTACK = 1
BATTLE_TO_M2 = 2
BATTLE_TO_EP = 3

BATTLE_NAMES = {
    BATTLE_ACTIVATE: "activate",
    BATTLE_ATTACK: "attack with",
    BATTLE_TO_M2: "to main phase 2",
    BATTLE_TO_EP: "to end phase",
}


@dataclass
class BattleCmd:
    """The legal-action menu for a battle phase decision point."""
    player: int
    activatable: list[CardRef]
    attackable: list[CardRef]
    to_m2: bool
    to_ep: bool

    def actions(self) -> list[tuple[int, int, CardRef | None]]:
        out: list[tuple[int, int, CardRef | None]] = []
        out += [(BATTLE_ACTIVATE, i, c) for i, c in enumerate(self.activatable)]
        out += [(BATTLE_ATTACK, i, c) for i, c in enumerate(self.attackable)]
        if self.to_m2:
            out.append((BATTLE_TO_M2, 0, None))
        if self.to_ep:
            out.append((BATTLE_TO_EP, 0, None))
        return out

    @staticmethod
    def encode(cmd_type: int, index: int = 0) -> bytes:
        return struct.pack("<i", (index << 16) | cmd_type)


def parse_select_battlecmd(payload: bytes) -> BattleCmd:
    r = _Reader(payload)
    player = r.u8()
    activatable = r.cards(with_desc=True)
    # Attackable entries are 8 bytes: code(4) con(1) loc(1) seq(1)
    # direct_attackable(1) - note `sequence` is uint8 here, and there is a
    # trailing flag the other lists do not have.
    attackable = []
    for _ in range(r.u32()):
        code, con, loc, seq = r.u32(), r.u8(), r.u8(), r.u8()
        direct = r.u8()
        ref = CardRef(code, con, loc, seq)
        ref.client_mode = direct          # reuse the field for "can attack directly"
        attackable.append(ref)
    return BattleCmd(player, activatable, attackable, bool(r.u8()), bool(r.u8()))
