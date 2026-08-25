"""Write EDOPro-compatible .yrp replay files.

A replay is (deck lists, seed, ordered response log) - exactly what the duel
already records for reproducibility, so exporting one is nearly free and gets
the real EDOPro client, with card art and animation, for no rendering work.
EDOPro does not store a picture of the duel: it re-simulates it in its own
core from the seed and feeds our responses back in (`ReplayMode::StartDuel`
in `gframe/old_replay_mode.cpp`).

Format (edopro/gframe/replay.h and replay.cpp):

    ExtendedReplayHeader                                        (72 bytes)
        ReplayHeader  id, version, flag, timestamp, datasize, hash  (6x u32)
                      props[8]
        header_version  u64   must be <= 1 or ParseReplayHeader rejects it
        seed[4]         u64   <- the Xoshiro256 state we duel with
    body (uncompressed when REPLAY_COMPRESSED is unset)
        home player count  u32   <- REPLAY_NEWREPLAY only
        home names         40 bytes each, UTF-16LE
        opposing count     u32   <- REPLAY_NEWREPLAY only
        opposing names     40 bytes each
        start_lp           u32
        start_hand         u32
        draw_count         u32
        duel flags         u64  (with REPLAY_64BIT_DUELFLAG)
        per player: main count u32 + codes, extra count u32 + codes
        custom rule cards  u32 count + codes   <- REPLAY_NEWREPLAY only
        responses          u8 length + that many bytes, repeated

Two fields exist only because we set REPLAY_NEWREPLAY, and both are silent
killers if omitted - `Replay::ParseNames` reads the per-side player count as
a u32 before any name, so leaving it out makes the client read the first four
bytes of "Player 1" as a count of seven million players; `Replay::ParseDecks`
reads the custom-rule-card count immediately after the decks, so leaving it
out makes it consume the first response byte instead.

Note the deck list written is the *shuffled* order, not the source decklist.
The engine does not shuffle - we do - so the dealt order is what reproduces
the duel.
"""

from __future__ import annotations

import lzma
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

#: ExtendedReplayHeader::latest_header_version. Anything higher is rejected,
#: and `CanBePlayedInOldMode` requires exactly 1.
HEADER_VERSION = 1

#: gframe/config.h packs the client and core versions into one u32. The yrp1
#: path hardcodes `legacy_race_size = false` so it never reads this back, but
#: other paths derive it from the core major - claim the core we link (11.0)
#: rather than leaving it 0, which would read as a pre-10 legacy core.
_EDOPRO_VERSION = (41, 0)
_CORE_VERSION = (11, 0)
CLIENT_VERSION = (
    (_EDOPRO_VERSION[0] & 0xFF)
    | ((_EDOPRO_VERSION[1] & 0xFF) << 8)
    | ((_CORE_VERSION[0] & 0xFF) << 16)
    | ((_CORE_VERSION[1] & 0xFF) << 24)
)


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
    rule_cards: list[int] = (),
) -> bytes:
    """Serialise one duel into a .yrp byte string.

    `decks` must be in dealt order - the order cards were handed to
    OCG_DuelNewCard - not the order they appear in the .ydk.
    """
    body = bytearray()
    for i in range(2):                  # one player per side, count-prefixed
        body += struct.pack("<I", 1)
        body += _name(names[i])
    body += struct.pack("<III", start_lp, start_hand, draw_count)
    body += struct.pack("<Q", duel_flags)
    for main, extra in decks:
        body += struct.pack("<I", len(main))
        body += b"".join(struct.pack("<I", c) for c in main)
        body += struct.pack("<I", len(extra))
        body += b"".join(struct.pack("<I", c) for c in extra)
    body += struct.pack("<I", len(rule_cards))
    body += b"".join(struct.pack("<I", c) for c in rule_cards)
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


def parse_header(data: bytes) -> tuple[dict, bytes]:
    """Split a replay into its header fields and its (decompressed) body.

    Shared by both replay kinds. `_LastReplay.yrpX` is written incrementally
    while a duel runs and is *uncompressed*; only `SaveReplay` sets
    REPLAY_COMPRESSED and LZMA-compresses, so handle both.
    """
    (rid, version, flag, ts, datasize, hsh) = struct.unpack_from("<IIIIII", data, 0)
    props = data[24:32]
    off = 24 + 8                        # 6 u32 + props[8]
    out = {"id": rid, "version": version, "flag": flag, "datasize": datasize,
           "timestamp": ts}
    if flag & REPLAY_EXTENDED_HEADER:
        (out["header_version"],) = struct.unpack_from("<Q", data, off)
        off += 8
        out["seed"] = struct.unpack_from("<4Q", data, off)
        off += 32
    body = data[off:]
    if flag & REPLAY_COMPRESSED:
        # LzmaCompress writes 5 props bytes: one packed lc/lp/pb, then dict size.
        lclppb, dict_size = props[0], struct.unpack_from("<I", props, 1)[0]
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{
            "id": lzma.FILTER_LZMA1, "dict_size": dict_size,
            "lc": lclppb % 9, "lp": (lclppb // 9) % 5, "pb": lclppb // 45}])
        body = dec.decompress(body, datasize)
    return out, body


def parse_yrpx(data: bytes) -> dict:
    """Read a yrpX - the *message stream* replay EDOPro records for itself.

    A yrp1 stores the questions' answers; a yrpX stores the `MSG_*` packets
    the core emitted, which is the same stream `engine/messages.py` decodes.
    That makes any yrpX EDOPro wrote a golden file for our decoders: real
    client data, produced without our code anywhere in the loop.

    Packets are `uint8 message, uint32 length, length bytes`
    (`Replay::ReadNextPacket`). One pseudo-packet, OLD_REPLAY_MODE, carries a
    whole embedded yrp1; it is recognised by its magic rather than by its id,
    which is a client-side constant the core header does not define.
    """
    out, body = parse_header(data)
    o = 40 * 2 if out["flag"] & REPLAY_SINGLE_MODE else None
    if o is None:                       # NEWREPLAY: a count per side
        o = 0
        for _ in range(2):
            (n,) = struct.unpack_from("<I", body, o); o += 4 + 40 * n
    # yrpX stores no lp/hand/draw - ParseParams reads those only for yrp1.
    if out["flag"] & REPLAY_64BIT_DUELFLAG:
        (out["duel_flags"],) = struct.unpack_from("<Q", body, o); o += 8
    else:
        (out["duel_flags"],) = struct.unpack_from("<I", body, o); o += 4

    packets, embedded = [], None
    while o + 5 <= len(body):
        msg = body[o]
        (ln,) = struct.unpack_from("<I", body, o + 1)
        if ln > len(body) - o - 5:
            break
        payload = body[o + 5:o + 5 + ln]
        o += 5 + ln
        if len(payload) >= 4 and struct.unpack_from("<I", payload, 0)[0] == REPLAY_YRP1:
            embedded = payload          # OLD_REPLAY_MODE
            continue
        packets.append((msg, payload))
    out["packets"] = packets
    out["embedded_yrp"] = embedded
    out["trailing_bytes"] = len(body) - o
    return out


def parse_yrp(data: bytes) -> dict:
    """Read back what build_yrp wrote, in the order EDOPro reads it.

    Round-tripping through this is a consistency check, not a compatibility
    one - it only catches drift between our writer and our reader. The field
    order here is transcribed from `Replay::ParseNames`/`ParseParams`/
    `ParseDecks`/`ParseResponses` so that at least the transcription is
    reviewed against the client rather than against itself."""
    out, body = parse_header(data)
    flag = out["flag"]
    o = 0
    out["names"] = []
    out["player_counts"] = []
    for _ in range(2):                  # home side, then opposing side
        if flag & REPLAY_SINGLE_MODE:
            n = 1                       # single mode writes two bare names
        elif flag & REPLAY_NEWREPLAY:
            (n,) = struct.unpack_from("<I", body, o); o += 4
        else:
            n = 2 if flag & REPLAY_TAG else 1
        out["player_counts"].append(n)
        for _ in range(n):
            out["names"].append(body[o:o + 40].decode("utf-16-le").rstrip("\x00"))
            o += 40
    out["start_lp"], out["start_hand"], out["draw_count"] = struct.unpack_from("<III", body, o)
    o += 12
    (out["duel_flags"],) = struct.unpack_from("<Q", body, o)
    o += 8
    out["scriptname"] = None
    if flag & REPLAY_SINGLE_MODE:
        (slen,) = struct.unpack_from("<H", body, o); o += 2
        out["scriptname"] = body[o:o + slen].decode("utf-8", "replace"); o += slen
    out["decks"] = []
    # Single mode builds its field from the script, so it stores no decks -
    # unless it is a hand test, which stores them and nothing else.
    n_decks = 0 if (flag & REPLAY_SINGLE_MODE and not (flag & REPLAY_HAND_TEST)) \
        else sum(out["player_counts"])
    for _ in range(n_decks):
        (n,) = struct.unpack_from("<I", body, o); o += 4
        main = list(struct.unpack_from(f"<{n}I", body, o)); o += 4 * n
        (m,) = struct.unpack_from("<I", body, o); o += 4
        extra = list(struct.unpack_from(f"<{m}I", body, o)); o += 4 * m
        out["decks"].append((main, extra))
    out["rule_cards"] = []
    if flag & REPLAY_NEWREPLAY and not (flag & REPLAY_SINGLE_MODE) \
            and not (flag & REPLAY_HAND_TEST):
        (n,) = struct.unpack_from("<I", body, o); o += 4
        out["rule_cards"] = list(struct.unpack_from(f"<{n}I", body, o)); o += 4 * n
    resp = []
    while o < len(body):
        ln = body[o]; o += 1
        if ln == 0 or o + ln > len(body):
            break
        resp.append(body[o:o + ln]); o += ln
    out["responses"] = resp
    return out
