"""Write EDOPro-compatible .yrp replay files.

A replay is (deck lists, seed, ordered response log) - exactly what the duel
already records for reproducibility, so exporting one is nearly free and gets
the real EDOPro client, with card art and animation, for no rendering work.

Format (edopro/gframe/replay.h and replay.cpp):

    ExtendedReplayHeader
        ReplayHeader  id, version, flag, timestamp, datasize, hash  (6x u32)
                      props[8]
        header_version  u64
        seed[4]         u64   <- the Xoshiro256 state we duel with
    body (uncompressed when REPLAY_COMPRESSED is unset)
        player names       40 bytes each, UTF-16LE, 2 players
        start_lp           u32
        start_hand         u32
        draw_count         u32
        duel flags         u64  (with REPLAY_64BIT_DUELFLAG)
        per player: main count u32 + codes, extra count u32 + codes
        responses          u8 length + that many bytes, repeated

Note the deck list written is the *shuffled* order, not the source decklist.
The engine does not shuffle - we do - so the dealt order is what reproduces
the duel.
"""

from __future__ import annotations

import struct
import time
from pathlib import Path

REPLAY_COMPRESSED = 0x1
REPLAY_TAG = 0x2
REPLAY_DECODED = 0x4
REPLAY_SINGLE_MODE = 0x8
REPLAY_LUA64 = 0x10
REPLAY_NEWREPLAY = 0x20
REPLAY_HAND_TEST = 0x40
REPLAY_DIRECT_SEED = 0x80
REPLAY_64BIT_DUELFLAG = 0x100
REPLAY_EXTENDED_HEADER = 0x200

REPLAY_YRP1 = 0x31707279
REPLAY_YRPX = 0x58707279

#: ExtendedReplayHeader::latest_header_version
HEADER_VERSION = 1
#: Client version stamp. EDOPro checks this loosely for yrp1 replays.
CLIENT_VERSION = 0x1361


def _name(s: str) -> bytes:
    """20 UTF-16LE code units, null padded - ReadName() reads 40 bytes."""
    b = s.encode("utf-16-le")[:38]
    return b + b"\x00" * (40 - len(b))


def build_yrp(
    *,
    seed: tuple[int, int, int, int],
    decks: list[tuple[list[int], list[int]]],
    responses: list[bytes],
    duel_flags: int,
    names: tuple[str, str] = ("Player 1", "Player 2"),
    start_lp: int = 8000,
    start_hand: int = 5,
    draw_count: int = 1,
) -> bytes:
    """Serialise one duel into a .yrp byte string.

    `decks` must be in dealt order - the order cards were handed to
    OCG_DuelNewCard - not the order they appear in the .ydk.
    """
    body = bytearray()
    for i in range(2):
        body += _name(names[i])
    body += struct.pack("<III", start_lp, start_hand, draw_count)
    body += struct.pack("<Q", duel_flags)
    for main, extra in decks:
        body += struct.pack("<I", len(main))
        body += b"".join(struct.pack("<I", c) for c in main)
        body += struct.pack("<I", len(extra))
        body += b"".join(struct.pack("<I", c) for c in extra)
    for r in responses:
        if not r or len(r) > 255:
            continue                    # length field is a single byte
        body += bytes([len(r)]) + r

    flag = (REPLAY_EXTENDED_HEADER | REPLAY_NEWREPLAY | REPLAY_64BIT_DUELFLAG
            | REPLAY_LUA64)
    header = struct.pack(
        "<IIIIII8s",
        REPLAY_YRP1,
        CLIENT_VERSION,
        flag,
        int(time.time()) & 0xFFFFFFFF,
        len(body),
        0,                              # hash: unchecked for uncompressed bodies
        b"\x00" * 8,                    # props: LZMA properties, unused here
    )
    header += struct.pack("<Q", HEADER_VERSION)
    header += struct.pack("<4Q", *seed)
    return bytes(header) + bytes(body)


def write_yrp(path: str | Path, **kw) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_yrp(**kw))
    return path


def parse_yrp(data: bytes) -> dict:
    """Read back what build_yrp wrote. Round-tripping is the only check we
    can run without EDOPro itself."""
    (rid, version, flag, ts, datasize, hsh) = struct.unpack_from("<IIIIII", data, 0)
    off = 24 + 8                        # 6 u32 + props[8]
    out = {"id": rid, "version": version, "flag": flag, "datasize": datasize}
    if flag & REPLAY_EXTENDED_HEADER:
        (out["header_version"],) = struct.unpack_from("<Q", data, off)
        off += 8
        out["seed"] = struct.unpack_from("<4Q", data, off)
        off += 32
    body = data[off:]
    o = 0
    out["names"] = []
    for _ in range(2):
        out["names"].append(body[o:o + 40].decode("utf-16-le").rstrip("\x00"))
        o += 40
    out["start_lp"], out["start_hand"], out["draw_count"] = struct.unpack_from("<III", body, o)
    o += 12
    (out["duel_flags"],) = struct.unpack_from("<Q", body, o)
    o += 8
    out["decks"] = []
    for _ in range(2):
        (n,) = struct.unpack_from("<I", body, o); o += 4
        main = list(struct.unpack_from(f"<{n}I", body, o)); o += 4 * n
        (m,) = struct.unpack_from("<I", body, o); o += 4
        extra = list(struct.unpack_from(f"<{m}I", body, o)); o += 4 * m
        out["decks"].append((main, extra))
    resp = []
    while o < len(body):
        ln = body[o]; o += 1
        if ln == 0 or o + ln > len(body):
            break
        resp.append(body[o:o + ln]); o += ln
    out["responses"] = resp
    return out
