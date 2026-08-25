"""Replay a .yrp through EDOPro's own engine.

Every other replay test checks our writer against our reader, which cannot
fail for the interesting reason. This one loads the EDOPro install's core,
card databases and Lua scripts and re-runs the duel through them exactly the
way `ReplayMode::StartDuel` does - so it fails when our bytes are wrong, when
the two cores disagree, or when our pinned card scripts have drifted from the
ones EDOPro ships.

Skipped when EDOPro is not installed, so it does not break a fresh checkout.
Point it somewhere else with EDOPRO_DIR.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.carddb import CardDB, ScriptProvider
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load
from scripts.verify_yrp import EDOPRO, RecordedResponses, edopro_data
from viz.replay import build_yrp, parse_yrp

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"
EDO = Path(os.environ.get("EDOPRO_DIR", EDOPRO)).expanduser()

pytestmark = pytest.mark.skipif(
    not (EDO / "libocgcore.dylib").exists(),
    reason=f"no EDOPro install at {EDO}",
)


def a_duel(seed=(101, 107, 113, 129)):
    """Play one duel with our engine and return the .yrp bytes."""
    deck = Deck.from_ydk(DECK)
    with Duel(seed, lib=load(), carddb=CardDB(), scripts=ScriptProvider()) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=100)
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=600)
        d.start()
        r = d.run(RandomLegal(seed=100), max_steps=300_000, retry_limit=400)
        return build_yrp(seed=seed, decks=d.dealt, responses=d.responses,
                         duel_flags=d.flags, start_lp=d.starting_lp,
                         start_hand=d.starting_draw,
                         draw_count=d.draw_per_turn), r["winner"]


def test_edopro_reproduces_the_duel():
    """The whole point: EDOPro re-simulates rather than replaying a recording,
    so a replay is only correct if its engine reaches the same position ours
    did. A desync surfaces as MSG_RETRY - the engine calling one of our
    responses illegal for the state it is in."""
    blob, winner = a_duel()
    data = parse_yrp(blob)
    core, cdbs, scripts = edopro_data(EDO)

    policy = RecordedResponses(data["responses"])
    with Duel(tuple(data["seed"]), lib=load(core), carddb=CardDB(cdbs),
              scripts=scripts, flags=data["duel_flags"],
              starting_lp=data["start_lp"], starting_draw=data["start_hand"],
              draw_per_turn=data["draw_count"]) as d:
        for team, (main, extra) in enumerate(data["decks"]):
            for code in main:
                d.add_card(code, team, 0x01)        # LOCATION_DECK
            for code in extra:
                d.add_card(code, team, 0x40)        # LOCATION_EXTRA
        d.start()
        r = d.run(policy, max_steps=300_000, retry_limit=1)

    assert policy.i == len(data["responses"]), "EDOPro's engine ended early"
    assert r["retries"] == 0
    assert r["winner"] == winner, "EDOPro's engine reached a different result"


def test_our_parser_reads_edopros_own_replays():
    """EDOPro writes `replay/_LastReplay.yrp` whenever it records a duel.
    Reading one is the only direction of the compatibility check we can make
    without a human at the client - it proves the transcription, not just
    that our writer and reader agree with each other."""
    ref = EDO / "replay" / "_LastReplay.yrp"
    if not ref.exists():
        pytest.skip("no _LastReplay.yrp - play or watch a duel in EDOPro first")
    data = parse_yrp(ref.read_bytes())
    assert data["header_version"] == 1
    assert data["start_lp"] > 0 and data["start_hand"] > 0
    # Every field after the names is only reachable if the names were read at
    # the right width, so a sane start_lp is a real check on the layout.
    assert data["start_lp"] % 100 == 0, "params misaligned - name width is wrong"
