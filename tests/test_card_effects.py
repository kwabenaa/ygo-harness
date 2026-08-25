"""Cards must actually have their effects.

The core requests only cXXXXXXX.lua on demand; the shared library scripts are
the host's responsibility. Without them every card script dies on its first
line - `local s,id=GetID()` - and the card ends up with no effects.

The failure is silent in the worst way: duels still run to completion, because
summoning and setting are rules actions that need no script. It looks like a
game where nothing has an ability, not like an error. It cost a full debugging
session to notice, so it gets a test.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.carddb import CardDB, ScriptProvider
from engine.constants import MSG_SELECT_IDLECMD
from engine.deck import Deck
from engine.duel import Duel
from engine.messages import parse_idlecmd
from engine.ocgapi import load

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"
ENGAGE = 63166095


def play(seed=1, load_globals=True):
    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    seen = []

    class W(RandomLegal):
        def __call__(self, msg, duel):
            if msg is not None and msg.id == MSG_SELECT_IDLECMD:
                seen.extend(parse_idlecmd(msg.payload).activatable)
            return super().__call__(msg, duel)

    with Duel((seed, seed + 7, seed + 13, seed + 29), lib=lib, carddb=db,
              scripts=sp, load_globals=load_globals) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed)
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed + 500)
        d.start()
        d.run(W(seed=seed), max_steps=300_000, retry_limit=400)
        errors = [l for l in d.log if "nil value" in l or "error function" in l]
    return seen, errors


def test_no_script_errors():
    _, errors = play()
    assert not errors, f"{len(errors)} script errors, first: {errors[0][:120]}"


def test_cards_are_activatable():
    activatable, _ = play()
    assert activatable, (
        "no card was ever activatable - the global scripts are probably not "
        "loaded, so every card has no effect"
    )


def test_engage_is_offered():
    """Sky Striker's core engine card must be usable, or the deck is inert."""
    activatable, _ = play()
    assert any(a.code == ENGAGE for a in activatable), (
        "Sky Striker Mobilize - Engage! was never activatable"
    )


def test_missing_globals_is_loud_not_silent():
    """Skipping the globals must produce visible errors, not a quiet no-op."""
    activatable, errors = play(load_globals=False)
    assert errors, "expected script errors when globals are not loaded"
    assert not activatable, "cards should have no effects without globals"
