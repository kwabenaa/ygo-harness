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

    def u16(self) -> int:
        (v,) = struct.unpack_from("<H", self.buf, self.off); self.off += 2; return v

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


# ---------------------------------------------------------------------------
# Decision points reached by the wider card pool.
#
# Everything below is asked by playerop.cpp and blocks until answered. They
# were absent from DECISION_MESSAGES until the puzzle runner reached them, and
# the resulting failures did not look like "unhandled message" - `pending` went
# stale, the policy answered the previous question forever, and the error named
# the wrong message. tests/test_constants.py now derives the required set from
# playerop.cpp so that cannot recur silently.
# ---------------------------------------------------------------------------


@dataclass
class SelectOption:
    """A "pick one of these effect modes" decision. Response is the index."""
    player: int
    options: list[int]

    @staticmethod
    def encode(index: int) -> bytes:
        return struct.pack("<i", index)


def parse_select_option(payload: bytes) -> SelectOption:
    r = _Reader(payload)
    player, count = r.u8(), r.u8()          # count is uint8, not uint32
    return SelectOption(player, [r.u64() for _ in range(count)])


@dataclass
class SortCard:
    """A "put these in an order" decision (MSG_SORT_CARD / MSG_SORT_CHAIN)."""
    player: int
    cards: list[CardRef]

    @staticmethod
    def encode(order: list[int]) -> bytes:
        """One int8 per card, forming a permutation of 0..n-1.

        Not an index like most decisions. The validator walks every position
        and rejects a repeat, so answering with a plain `0` - which is what
        the placeholder did - fails the moment there is more than one card.
        """
        return b"".join(struct.pack("<b", i) for i in order)

    @staticmethod
    def decline() -> bytes:
        """-1 leaves the order alone. Always legal."""
        return struct.pack("<b", -1)


def parse_sort_card(payload: bytes) -> SortCard:
    r = _Reader(payload)
    player = r.u8()
    cards = []
    for _ in range(r.u32()):
        code, con = r.u32(), r.u8()
        loc, seq = r.u32(), r.u32()         # both uint32 here, unlike loc_info
        cards.append(CardRef(code, con, loc, seq, 0, 0))
    return SortCard(player, cards)


@dataclass
class SelectCounter:
    """A "remove N counters from these cards" decision."""
    player: int
    counter_type: int
    count: int
    cards: list[tuple[int, int]]            # (code, counters on it)

    @staticmethod
    def encode(taken: list[int]) -> bytes:
        """One uint16 per offered card, summing to `count`."""
        return b"".join(struct.pack("<H", n) for n in taken)

    def spread(self) -> list[int]:
        """Take counters greedily from the front until `count` is met."""
        left, out = self.count, []
        for _code, have in self.cards:
            take = min(left, have)
            out.append(take)
            left -= take
        return out


def parse_select_counter(payload: bytes) -> SelectCounter:
    r = _Reader(payload)
    player = r.u8()
    ctype, count = r.u16(), r.u16()
    cards = []
    for _ in range(r.u32()):
        code = r.u32()
        r.u8(), r.u8(), r.u8()              # controller, location, sequence
        cards.append((code, r.u16()))
    return SelectCounter(player, ctype, count, cards)


@dataclass
class SelectSum:
    """Material selection constrained by a sum - Synchro, Ritual, Xyz tribute.

    `exact` mirrors the core's two modes. When the core wrote mode 0 the
    chosen cards' parameters must total `acc` exactly; when it wrote 1 they
    must merely reach it, without any single card being removable.

    Each card carries `sum_param`, packed as two uint16s: the low half is its
    normal contribution and the high half an alternative (a monster with two
    usable levels). Either may be used, which is why this is a search and not
    a filter.
    """
    player: int
    exact: bool
    acc: int
    min: int
    max: int
    must: list[tuple[int, int]]             # (code, sum_param)
    selectable: list[tuple[int, int]]

    @staticmethod
    def _params(param: int) -> tuple[int, ...]:
        lo, hi = param & 0xFFFF, param >> 16
        return (lo, hi) if hi else (lo,)

    def _exact_ok(self, opts: list[tuple[int, ...]]) -> bool:
        """select_sum_check1: every chosen card is consumed, totalling `acc`.

        Not a subset sum with slack - the core walks the whole list and must
        land on zero at the last card, so an unused card makes the selection
        illegal.
        """
        def reaches(rest: list[tuple[int, ...]], target: int) -> bool:
            if not rest:
                return target == 0
            return any(
                reaches(rest[1:], target - v)
                for v in rest[0] if target - v >= 0
            )
        return bool(opts) and reaches(opts, self.acc)

    def _atleast_ok(self, opts: list[tuple[int, ...]]) -> bool:
        """The max==0 branch: reach `acc`, with no card removable.

        Each card contributes its smaller parameter to `sum` and its larger to
        `mx`. The selection must be able to reach `acc` (`mx >= acc`) while
        being minimal - dropping the smallest contributor has to fall short.
        """
        if not opts:
            return False
        total = mx = 0
        smallest = None
        for choices in opts:
            lo_v = min(choices)
            total += lo_v
            mx += max(choices)
            smallest = lo_v if smallest is None else min(smallest, lo_v)
        return mx >= self.acc and (total - smallest) < self.acc

    def solve(self) -> list[int] | None:
        """Indices into `selectable` the core will accept, or None.

        Searches by increasing selection size, so the answer is the smallest
        legal one - which is also the sane play, since these are materials
        being spent. The lists are one summon's worth of cards, so a plain
        depth-first search over subsets is the right tool.
        """
        must_opts = [self._params(p) for _c, p in self.must]
        ok = self._exact_ok if self.exact else self._atleast_ok

        lo = max(self.min, 0)
        hi = min(self.max or len(self.selectable), len(self.selectable))

        def search(start: int, chosen: list[int]):
            if lo <= len(chosen) <= hi:
                opts = must_opts + [
                    self._params(self.selectable[i][1]) for i in chosen
                ]
                if ok(opts):
                    return list(chosen)
            if len(chosen) >= hi:
                return None
            for i in range(start, len(self.selectable)):
                chosen.append(i)
                found = search(i + 1, chosen)
                chosen.pop()
                if found is not None:
                    return found
            return None

        return search(0, [])


def parse_select_sum(payload: bytes) -> SelectSum:
    r = _Reader(payload)
    player = r.u8()
    # The core writes 0 when a maximum was given and 1 when it was not, so
    # this byte reads backwards from its name: 0 means the exact-sum mode.
    exact = r.u8() == 0
    acc, mn, mx = r.u32(), r.u32(), r.u32()

    def group() -> list[tuple[int, int]]:
        out = []
        for _ in range(r.u32()):
            code = r.u32()
            r.u8(), r.u8(), r.u32(), r.u32()   # loc_info
            out.append((code, r.u32()))        # sum_param
        return out

    must = group()
    return SelectSum(player, exact, acc, mn, mx, must, group())


@dataclass
class AnnounceBits:
    """MSG_ANNOUNCE_RACE / MSG_ANNOUNCE_ATTRIB: name `count` of a bit set.

    The response is a bitmask, not an index, and the core checks both that
    every bit is inside `available` and that exactly `count` bits are set.
    """
    player: int
    count: int
    available: int
    width: int                              # 8 for race, 4 for attribute

    def pick(self) -> int:
        out, taken, bit = 0, 0, 0
        while taken < self.count and bit < self.width * 8:
            if self.available & (1 << bit):
                out |= 1 << bit
                taken += 1
            bit += 1
        return out

    def encode(self, mask: int) -> bytes:
        return struct.pack("<Q" if self.width == 8 else "<I", mask)


def parse_announce_race(payload: bytes) -> AnnounceBits:
    r = _Reader(payload)
    player, count = r.u8(), r.u8()
    return AnnounceBits(player, count, r.u64(), 8)


def parse_announce_attrib(payload: bytes) -> AnnounceBits:
    r = _Reader(payload)
    player, count = r.u8(), r.u8()
    return AnnounceBits(player, count, r.u32(), 4)


@dataclass
class AnnounceNumber:
    """Pick one of a list of numbers. Response is the index, not the value."""
    player: int
    options: list[int]

    @staticmethod
    def encode(index: int) -> bytes:
        return struct.pack("<i", index)


def parse_announce_number(payload: bytes) -> AnnounceNumber:
    r = _Reader(payload)
    player, count = r.u8(), r.u8()
    return AnnounceNumber(player, [r.u64() for _ in range(count)])


@dataclass
class AnnounceCard:
    """Declare a card name - Crush Card Virus, Deck Devastation Virus, etc.

    The payload is not a menu. It is a filter, in the little RPN language
    is_declarable() evaluates in playerop.cpp, and any card in the pool that
    satisfies it is a legal answer. So answering means running that filter,
    which `engine.declare` does.
    """
    player: int
    opcodes: list[int]

    @staticmethod
    def encode(code: int) -> bytes:
        return struct.pack("<i", code)


def parse_announce_card(payload: bytes) -> AnnounceCard:
    r = _Reader(payload)
    player, count = r.u8(), r.u8()
    return AnnounceCard(player, [r.u64() for _ in range(count)])
