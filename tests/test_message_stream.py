"""Golden-file tests for `MSG_*` decoding, against a stream EDOPro recorded.

`docs/PLAN.md` set this as an M1 exit criterion and it was never built,
because there was no source of real client data. There is now: EDOPro writes
`replay/_LastReplay.yrpX` after every duel, and a yrpX is the raw `MSG_*`
packet stream the core emitted - the same stream `engine/messages.py` decodes.

The fixture is one such recording (EDOPro 41.0.2, a WCS2006 puzzle), and the
point is its provenance: **our code was nowhere in the loop that produced it.**
Every other test in this repo checks our encoder against our decoder.

This matters most for trap #7 - the constants are hand-transcribed and a wrong
id misroutes a decision rather than raising. `test_constants.py` checks them
against the core header; this checks them against traffic.

Refresh it with any duel EDOPro records:
    cp ~/Applications/ProjectIgnis/replay/_LastReplay.yrpX \\
       tests/fixtures/edopro-41.0.2-puzzle.yrpX
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.carddb import CardDB
from viz.replay import parse_yrp, parse_yrpx

ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "edopro-41.0.2-puzzle.yrpX"
HEADER = ROOT / "vendor" / "ygopro-core" / "ocgapi_constants.h"

#: Messages whose payload starts with a uint32 card code. Others - MSG_ATTACK
#: and MSG_EQUIP among them - start with a packed location info instead, which
#: is exactly the kind of per-message difference trap #5 warns about.
CODE_LEADING = {70: "MSG_CHAINING", 60: "MSG_SUMMONING",
                62: "MSG_SPSUMMONING", 50: "MSG_MOVE"}


@pytest.fixture(scope="module")
def stream():
    return parse_yrpx(FIXTURE.read_bytes())


@pytest.fixture(scope="module")
def core_msg_ids():
    if not HEADER.exists():
        pytest.skip("ygopro-core not vendored")
    return {int(m[2]): m[1] for m in
            (re.match(r"#define (MSG_\w+)\s+(\d+)", ln) for ln in
             HEADER.read_text().splitlines()) if m}


def test_the_whole_stream_parses(stream):
    """Packets are `uint8 id, uint32 length, length bytes`. Consuming the
    body to exactly zero bytes left is a strong check: any wrong width
    anywhere desyncs the walk and leaves a remainder."""
    assert stream["trailing_bytes"] == 0
    assert len(stream["packets"]) > 100


def test_every_id_is_one_the_core_defines(stream, core_msg_ids):
    unknown = {mid for mid, _ in stream["packets"]} - set(core_msg_ids)
    assert not unknown, f"client sent ids the core header does not define: {unknown}"


def test_our_constants_match_the_ids_in_real_traffic(core_msg_ids):
    """Our names, checked against the header the client's core was built from."""
    from engine import constants as K
    ours = {k: v for k, v in vars(K).items() if k.startswith("MSG_") and isinstance(v, int)}
    for name, value in ours.items():
        if value in core_msg_ids:
            assert core_msg_ids[value] == name, \
                f"we call id {value} {name}; the core calls it {core_msg_ids[value]}"


def test_code_leading_messages_decode_to_real_cards(stream):
    """The sharpest check available. If our offset for the card code were
    wrong, these would decode to numbers no card database has heard of - and
    they resolve to a coherent Elemental HERO puzzle instead."""
    db = CardDB()
    seen = 0
    for mid, payload in stream["packets"]:
        if mid not in CODE_LEADING:
            continue
        code = int.from_bytes(payload[:4], "little")
        assert db.row(code) is not None, \
            f"{CODE_LEADING[mid]} payload[:4] = {code}, which is not a card"
        seen += 1
    assert seen >= 10, "fixture carries too few code-leading messages to check"


def test_offsets_duel_py_depends_on(stream):
    """`Duel.run` reads the turn player from MSG_NEW_TURN's only byte and the
    chain controller from MSG_CHAINING payload[4]. Both are hand-transcribed
    and both fail silently - a wrong turn player just routes decisions to the
    wrong policy."""
    turns = [p for m, p in stream["packets"] if m == 40]
    assert turns, "no MSG_NEW_TURN in fixture"
    for p in turns:
        assert len(p) == 1 and p[0] in (0, 1)
    for p in (p for m, p in stream["packets"] if m == 70):
        assert p[4] in (0, 1), "MSG_CHAINING controller byte is not a player"


def test_the_embedded_yrp1_parses(stream):
    """A yrpX carries the whole yrp1 inside one pseudo-packet, so the fixture
    exercises both readers - and the yrp1 here was written by EDOPro, not us."""
    assert stream["embedded_yrp"] is not None
    inner = parse_yrp(stream["embedded_yrp"])
    assert inner["header_version"] == 1
    assert inner["start_lp"] == 8000
    assert len(inner["responses"]) > 0
    assert inner["scriptname"], "single-mode replay should name its script"
