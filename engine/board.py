"""Board state via the engine's query API, and a compact text rendering of it.

State comes from OCG_DuelQuery* rather than from replaying the message stream.
Querying asks the engine what is true right now; reconstructing from messages
means maintaining a shadow state machine that can silently drift out of sync,
and a board that is subtly wrong is worse than no board at all.

The rendering is deliberately terse. It goes into the prompt at every decision
point - 50-100 times per duel - so every token is multiplied by a hundred.
"""

from __future__ import annotations

import ctypes as C
import struct
from dataclasses import dataclass, field

from . import ocgapi as api
from .constants import (
    LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND,
    LOCATION_MZONE, LOCATION_REMOVED, LOCATION_SZONE, POS_FACEDOWN,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_DEFENSE, TYPE_LINK,
)

QUERY_CODE = 0x1
QUERY_POSITION = 0x2
QUERY_TYPE = 0x8
QUERY_LEVEL = 0x10
QUERY_ATTACK = 0x100
QUERY_DEFENSE = 0x200
QUERY_RANK = 0x20
QUERY_ATTRIBUTE = 0x40
QUERY_RACE = 0x80
QUERY_BASE_ATTACK = 0x400
QUERY_BASE_DEFENSE = 0x800
QUERY_EQUIP_CARD = 0x4000
QUERY_TARGET_CARD = 0x8000
QUERY_OVERLAY_CARD = 0x10000
QUERY_COUNTERS = 0x20000
QUERY_STATUS = 0x80000
QUERY_LSCALE = 0x200000
QUERY_RSCALE = 0x400000
QUERY_LINK = 0x800000
QUERY_END = 0x80000000

#: Everything about an on-field card that a duel can change.
#:
#: These are *current* values, which is the entire reason to ask the engine
#: instead of reading the card database: an effect that changes a Level, an
#: Attribute or an ATK makes the printed value wrong, and a harness showing
#: the printed value tells the agent something false without erroring. The
#: previous set was five fields, chosen to avoid "paying for fields we never
#: print" - but the cost is a few bytes of buffer, and the price of omitting
#: them was an agent that could not see Xyz materials, counters, equips,
#: negation, or any stat an effect had modified.
#:
#: scripts/coverage_report.py checks this against what card::get_infos can
#: serialise, so a field we do not ask for is visible as a gap.
FIELD_FLAGS = (
    QUERY_CODE | QUERY_POSITION | QUERY_TYPE
    | QUERY_LEVEL | QUERY_RANK | QUERY_ATTRIBUTE | QUERY_RACE
    | QUERY_ATTACK | QUERY_DEFENSE | QUERY_BASE_ATTACK | QUERY_BASE_DEFENSE
    | QUERY_EQUIP_CARD | QUERY_TARGET_CARD | QUERY_OVERLAY_CARD
    | QUERY_COUNTERS | QUERY_STATUS | QUERY_LSCALE | QUERY_RSCALE | QUERY_LINK
)

#: Hand, graveyard, banished. No zone-relative fields - a card in the GY has
#: no equip target and no counters - but Level and ATK still decide whether a
#: card in hand can be summoned, or a GY card revived to any purpose.
LIST_FLAGS = (
    QUERY_CODE | QUERY_TYPE | QUERY_LEVEL | QUERY_RANK
    | QUERY_ATTRIBUTE | QUERY_RACE | QUERY_ATTACK | QUERY_DEFENSE
    # Base stats come along so `buffed` means the same thing everywhere.
    # Without them every card off the field reads as buffed by its whole ATK.
    | QUERY_BASE_ATTACK | QUERY_BASE_DEFENSE
)

LOCATION_NAMES = {
    LOCATION_DECK: "Deck", LOCATION_HAND: "Hand", LOCATION_MZONE: "M",
    LOCATION_SZONE: "S", LOCATION_GRAVE: "GY", LOCATION_REMOVED: "Banished",
    LOCATION_EXTRA: "Extra",
}


#: card::status bits worth naming. STATUS_DISABLED matters most: a negated
#: monster keeps its stats and loses its effects, and nothing else about the
#: board says so.
STATUS_DISABLED = 0x0001
STATUS_TO_ENABLE = 0x0002


@dataclass
class CardInfo:
    code: int = 0
    position: int = 0
    type: int = 0
    attack: int = 0
    defense: int = 0
    #: Current values. Effects move these away from the printed ones, which
    #: is why they are read from the engine and not from the card database.
    level: int = 0
    rank: int = 0
    attribute: int = 0
    race: int = 0
    base_attack: int = 0
    base_defense: int = 0
    link_rating: int = 0
    link_marker: int = 0
    lscale: int = 0
    rscale: int = 0
    status: int = 0
    #: Xyz materials attached, by code. Detach costs are paid out of this, so
    #: a card showing none is a card that cannot pay them.
    overlay: tuple[int, ...] = ()
    #: (counter type, how many).
    counters: tuple[tuple[int, int], ...] = ()
    #: Where an Equip Spell is attached: (controller, location, sequence).
    equip_target: tuple[int, int, int] | None = None
    #: What this card's continuous effect currently points at.
    targets: tuple[tuple[int, int, int], ...] = ()

    @property
    def disabled(self) -> bool:
        """Effects negated. Stats remain, abilities do not."""
        return bool(self.status & STATUS_DISABLED)

    @property
    def buffed(self) -> int:
        """Signed ATK difference from the printed value."""
        return self.attack - self.base_attack

    @property
    def face_down(self) -> bool:
        return bool(self.position & POS_FACEDOWN)

    @property
    def defense_position(self) -> bool:
        return bool(self.position & (POS_FACEUP_DEFENSE | POS_FACEDOWN_DEFENSE))

    @property
    def is_link(self) -> bool:
        return bool(self.type & TYPE_LINK)


def _parse_query_buffer(raw: bytes) -> list[CardInfo | None]:
    """Decode a query buffer into one entry per zone slot.

    Layout: a uint32 total-length prefix, then per card a run of TLV entries -
    uint16 size (= 4 + payload, excluding itself), uint32 flag, payload -
    terminated by a QUERY_END entry. An empty zone is a bare uint16 0.

    The leading length prefix is easy to miss and desynchronises the entire
    parse if skipped, in a way that looks like "the board is empty" rather
    than like an error.
    """
    out: list[CardInfo | None] = []
    cur: dict[int, bytes] = {}
    if len(raw) < 4:
        return out
    off = 4
    while off + 2 <= len(raw):
        (size,) = struct.unpack_from("<H", raw, off)
        off += 2
        if size == 0:                      # empty zone
            out.append(None)
            continue
        if off + 4 > len(raw):
            break
        (flag,) = struct.unpack_from("<I", raw, off)
        if flag == QUERY_END:
            off += 4
            out.append(_build(cur))
            cur = {}
            continue
        cur[flag] = raw[off + 4:off + size]
        off += size
    return out


def _u32(b: bytes) -> int:
    return struct.unpack_from("<I", b)[0] if len(b) >= 4 else 0


def _u64(b: bytes) -> int:
    return struct.unpack_from("<Q", b)[0] if len(b) >= 8 else 0


def _loc(b: bytes, off: int = 0) -> tuple[int, int, int] | None:
    """One loc_info: uint8 controller, uint8 location, uint32 sequence, uint32
    position. The core writes a zeroed one when there is nothing to point at,
    so location 0 means "no target" rather than "the deck"."""
    if len(b) < off + 10:
        return None
    con, loc = b[off], b[off + 1]
    (seq,) = struct.unpack_from("<I", b, off + 2)
    return None if loc == 0 else (con, loc, seq)


def _codes(b: bytes) -> tuple[int, ...]:
    """A uint32 count followed by that many uint32s."""
    return tuple(_u32(b[4 + 4 * i:]) for i in range(_u32(b)))


def _build(fields: dict[int, bytes]) -> CardInfo:
    link = fields.get(QUERY_LINK, b"")
    counters = fields.get(QUERY_COUNTERS, b"")
    targets = fields.get(QUERY_TARGET_CARD, b"")
    packed = _codes(counters)
    return CardInfo(
        code=_u32(fields.get(QUERY_CODE, b"")),
        position=_u32(fields.get(QUERY_POSITION, b"")),
        type=_u32(fields.get(QUERY_TYPE, b"")),
        attack=_u32(fields.get(QUERY_ATTACK, b"")),
        defense=_u32(fields.get(QUERY_DEFENSE, b"")),
        level=_u32(fields.get(QUERY_LEVEL, b"")),
        rank=_u32(fields.get(QUERY_RANK, b"")),
        attribute=_u32(fields.get(QUERY_ATTRIBUTE, b"")),
        # RACE is the one field the core serialises as a uint64.
        race=_u64(fields.get(QUERY_RACE, b"")),
        base_attack=_u32(fields.get(QUERY_BASE_ATTACK, b"")),
        base_defense=_u32(fields.get(QUERY_BASE_DEFENSE, b"")),
        # QUERY_LINK carries two uint32s: the rating, then the marker mask.
        link_rating=_u32(link),
        link_marker=_u32(link[4:]) if len(link) >= 8 else 0,
        lscale=_u32(fields.get(QUERY_LSCALE, b"")),
        rscale=_u32(fields.get(QUERY_RSCALE, b"")),
        status=_u32(fields.get(QUERY_STATUS, b"")),
        overlay=_codes(fields.get(QUERY_OVERLAY_CARD, b"")),
        # Each counter packs its type low and its count high in one uint32.
        counters=tuple((v & 0xFFFF, v >> 16) for v in packed),
        equip_target=_loc(fields.get(QUERY_EQUIP_CARD, b"")),
        targets=tuple(
            t for i in range(_u32(targets))
            if (t := _loc(targets, 4 + 10 * i)) is not None
        ),
    )


def query_location(duel, con: int, loc: int, flags: int = FIELD_FLAGS
                   ) -> list[CardInfo | None]:
    info = api.OCG_QueryInfo(flags=flags, con=con, loc=loc, seq=0, overlay_seq=0)
    length = C.c_uint32(0)
    buf = duel.lib.OCG_DuelQueryLocation(duel.handle, C.byref(length),
                                         C.byref(info))
    if not buf or length.value == 0:
        return []
    return _parse_query_buffer(C.string_at(buf, length.value))


def count(duel, con: int, loc: int) -> int:
    return duel.lib.OCG_DuelQueryCount(duel.handle, con, loc)


@dataclass
class Board:
    """One player's view of the field at a moment in time."""
    player: int
    monsters: list[CardInfo | None] = field(default_factory=list)
    spells: list[CardInfo | None] = field(default_factory=list)
    hand: list[CardInfo | None] = field(default_factory=list)
    grave: list[CardInfo | None] = field(default_factory=list)
    banished: list[CardInfo | None] = field(default_factory=list)
    #: Your own Extra Deck. You know its contents; your opponent does not.
    extra: list[CardInfo | None] = field(default_factory=list)
    deck_count: int = 0
    extra_count: int = 0


def read_board(duel, player: int) -> Board:
    return Board(
        player=player,
        monsters=query_location(duel, player, LOCATION_MZONE),
        spells=query_location(duel, player, LOCATION_SZONE),
        hand=query_location(duel, player, LOCATION_HAND, LIST_FLAGS),
        grave=query_location(duel, player, LOCATION_GRAVE, LIST_FLAGS),
        banished=query_location(duel, player, LOCATION_REMOVED, LIST_FLAGS),
        extra=query_location(duel, player, LOCATION_EXTRA, LIST_FLAGS),
        deck_count=count(duel, player, LOCATION_DECK),
        extra_count=count(duel, player, LOCATION_EXTRA),
    )


#: Zone counts under Master Rule 5: 5 main + 2 extra monster zones,
#: 5 spell/trap + 2 pendulum + 1 field zone.
MZONE_SLOTS = 7
SZONE_SLOTS = 8


@dataclass
class FieldInfo:
    """The cheap whole-field summary from OCG_DuelQueryField."""
    duel_options: int
    lp: tuple[int, int]   #: signed - life points legitimately go negative
    chain_length: int = 0


def query_field(duel) -> FieldInfo | None:
    """Read life points and the whole-field summary in one call.

    Layout (ocgapi.cpp OCG_DuelQueryField): uint32 duel_options, then per
    player uint32 lp, one entry per monster zone and spell zone (1 byte if
    empty, 6 if occupied), then six uint32 pile counts.
    """
    length = C.c_uint32(0)
    buf = duel.lib.OCG_DuelQueryField(duel.handle, C.byref(length))
    if not buf or length.value == 0:
        return None
    raw = C.string_at(buf, length.value)

    off = 0
    (first,) = struct.unpack_from("<I", raw, 0)
    # QueryLocation prefixes its buffer with a total length; probe for the
    # same here rather than assuming either way.
    if first == len(raw) - 4:
        off = 4
    (duel_options,) = struct.unpack_from("<I", raw, off)
    off += 4

    lps = []
    for _ in range(2):
        # int32_t in the core: LP goes negative before the win check
        # (`lp <= 0`) fires, so an unsigned read reports ~4.29 billion.
        (lp,) = struct.unpack_from("<i", raw, off)
        off += 4
        lps.append(lp)
        for _ in range(MZONE_SLOTS + SZONE_SLOTS):
            present = raw[off]
            off += 1
            if present:
                off += 5          # position (1) + xyz material count (4)
        off += 6 * 4              # main/hand/grave/removed/extra/extra_p counts
    chain = 0
    if off + 4 <= len(raw):
        (chain,) = struct.unpack_from("<I", raw, off)
    return FieldInfo(duel_options, (lps[0], lps[1]), chain)


def board_signature(duel, viewer: int) -> tuple:
    """A cheap summary of everything a plan depends on.

    Taken often enough that it has to stay cheap - once per chain resolution,
    ~35 times a duel - so it is queries, not a full `read_board`.

    Deliberately partial. Graveyard *contents* and the banished pile churn on
    almost every resolution without changing the route to a target board, and
    a signature that changes every time is worth exactly as much as no
    signature at all. Graveyard *size* is kept because Sky Striker reads it.
    Both players' zones are here: the opponent resolving something on their
    own board changes our route just as much as it changes theirs.
    """
    def zones(cards):
        return tuple((c.code, c.position) if c else None for c in cards)

    fi = query_field(duel)
    other = 1 - viewer
    return (
        zones(query_location(duel, viewer, LOCATION_MZONE)),
        zones(query_location(duel, viewer, LOCATION_SZONE)),
        zones(query_location(duel, other, LOCATION_MZONE)),
        zones(query_location(duel, other, LOCATION_SZONE)),
        tuple(sorted(c.code for c in
                     query_location(duel, viewer, LOCATION_HAND, LIST_FLAGS) if c)),
        count(duel, viewer, LOCATION_GRAVE),
        fi.lp if fi else None,
    )
