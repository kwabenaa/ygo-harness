"""Replay export.

These tests are deliberately weak on their own: round-tripping through our own
parser proves the bytes are self-consistent, not that EDOPro will open the
file. It missed two missing fields for exactly that reason - our reader agreed
with our writer about omitting them. `test_body_layout_matches_client_reading_
order` below pins offsets against the client's reader instead, and
`tests/test_yrp_edopro.py` replays the file through EDOPro's actual engine.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.carddb import CardDB, ScriptProvider
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load
from viz.replay import REPLAY_YRP1, build_yrp, parse_yrp

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"
SEED = (43, 49, 55, 71)


def recorded():
    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    with Duel(SEED, lib=lib, carddb=db, scripts=sp) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=42)
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=542)
        d.start()
        d.run(RandomLegal(seed=42), max_steps=300_000, retry_limit=400)
        blob = build_yrp(seed=SEED, decks=d.dealt, responses=d.responses,
                         duel_flags=d.flags, start_lp=d.starting_lp,
                         start_hand=d.starting_draw, draw_count=d.draw_per_turn)
        return blob, d.dealt, list(d.responses), d.flags


def test_header_round_trips():
    blob, _, _, flags = recorded()
    back = parse_yrp(blob)
    assert back["id"] == REPLAY_YRP1
    assert tuple(back["seed"]) == SEED, "seed must survive - it is the duel"
    assert back["duel_flags"] == flags


def test_decks_are_dealt_order_not_ydk_order():
    """The engine does not shuffle; we do. The replay must carry the dealt
    order or it reproduces a different duel."""
    blob, dealt, _, _ = recorded()
    back = parse_yrp(blob)
    for i, (main, extra) in enumerate(back["decks"]):
        assert main == dealt[i][0], f"player {i} main deck order differs"
        assert extra == dealt[i][1]
    ydk = Deck.from_ydk(DECK).main
    assert back["decks"][0][0] != ydk, "deck looks unshuffled - is the deal recorded?"


def test_every_response_survives():
    blob, _, responses, _ = recorded()
    back = parse_yrp(blob)
    kept = [r for r in responses if r and len(r) <= 255]
    assert back["responses"] == kept
    assert len(kept) == len(responses), "a response was dropped as oversized"


def test_body_layout_matches_client_reading_order():
    """Pin the byte offsets EDOPro reads at.

    Two fields exist only because we set REPLAY_NEWREPLAY - a per-side player
    count before the names, and a custom-rule-card count after the decks. A
    round-trip through our own parser cannot catch either: it would agree just
    as happily with a writer that omitted both. So check the offsets directly
    against `Replay::ParseNames` / `ParseParams` / `ParseDecks`."""
    blob, dealt, responses, _ = recorded()
    body = blob[72:]                                # sizeof(ExtendedReplayHeader)
    assert struct.unpack_from("<I", body, 0)[0] == 1, "home player count missing"
    assert struct.unpack_from("<I", body, 44)[0] == 1, "opposing player count missing"
    o = 2 * (4 + 40) + 12 + 8                       # names, lp/hand/draw, duel flags
    for main, extra in dealt:
        assert struct.unpack_from("<I", body, o)[0] == len(main)
        o += 4 + 4 * len(main)
        assert struct.unpack_from("<I", body, o)[0] == len(extra)
        o += 4 + 4 * len(extra)
    assert struct.unpack_from("<I", body, o)[0] == 0, "rule-card count missing"
    o += 4
    assert body[o] == len(responses[0]), "responses do not begin where EDOPro looks"
