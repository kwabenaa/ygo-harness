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
    POS_FACEUP_DEFENSE, TYPE_LINK,
)

QUERY_CODE = 0x1
QUERY_POSITION = 0x2
QUERY_TYPE = 0x8
QUERY_LEVEL = 0x10
QUERY_ATTACK = 0x100
QUERY_DEFENSE = 0x200
QUERY_LINK = 0x800000
QUERY_END = 0x80000000

#: Enough to render a field zone without paying for fields we never print.
FIELD_FLAGS = QUERY_CODE | QUERY_POSITION | QUERY_TYPE | QUERY_ATTACK | QUERY_DEFENSE
#: Hand and graveyard only need identity.
LIST_FLAGS = QUERY_CODE | QUERY_TYPE

LOCATION_NAMES = {
    LOCATION_DECK: "Deck", LOCATION_HAND: "Hand", LOCATION_MZONE: "M",
    LOCATION_SZONE: "S", LOCATION_GRAVE: "GY", LOCATION_REMOVED: "Banished",
    LOCATION_EXTRA: "Extra",
}


@dataclass
class CardInfo:
    code: int = 0
    position: int = 0
    type: int = 0
    attack: int = 0
    defense: int = 0

    @property
    def face_down(self) -> bool:
        return bool(self.position & POS_FACEDOWN)

    @property
    def defense_position(self) -> bool:
        return bool(self.position & (POS_FACEUP_DEFENSE | 0x8))

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


def _build(fields: dict[int, bytes]) -> CardInfo:
    return CardInfo(
        code=_u32(fields.get(QUERY_CODE, b"")),
        position=_u32(fields.get(QUERY_POSITION, b"")),
        type=_u32(fields.get(QUERY_TYPE, b"")),
        attack=_u32(fields.get(QUERY_ATTACK, b"")),
        defense=_u32(fields.get(QUERY_DEFENSE, b"")),
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
    lp: tuple[int, int]
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
        (lp,) = struct.unpack_from("<I", raw, off)
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
