"""The transcript must narrate what actually happened.

This is the artifact you read to answer "what went wrong?", and given how
quietly this engine fails it is often the fastest diagnostic available - a
transcript would have shown, immediately, that no card was ever activating.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.carddb import CardDB, ScriptProvider
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load
from viz.duel_log import DuelLog

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"


def transcript(seed=7):
    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    log = DuelLog(db)
    with Duel((seed + 1, seed + 7, seed + 13, seed + 29), lib=lib, carddb=db,
              scripts=sp) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed)
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed + 500)
        d.start()
        r = d.run(RandomLegal(seed=seed), max_steps=300_000, retry_limit=400)
    for m in r["messages"]:
        log.feed(m)
    return log


def test_transcript_has_turns_and_a_result():
    log = transcript()
    text = log.render()
    assert log.turn > 3, f"only {log.turn} turns narrated"
    assert "=== Turn 1" in text
    assert "WINS" in text, "no result line"


def test_transcript_narrates_real_play():
    """Guards the global-scripts class of bug: if no card ever activates or
    summons, the transcript says so plainly."""
    text = transcript().render()
    assert "activates" in text, "no card was ever activated"
    assert "Summons" in text, "nothing was ever summoned"


def test_transcript_names_cards():
    text = transcript().render()
    assert "Sky Striker" in text, "card names are not being resolved"
