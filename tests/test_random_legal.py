"""The random-legal policy is the floor every agent must beat, and the only
thing that exercises the parts of the message space passing never reaches.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.carddb import CardDB, ScriptProvider
from engine.constants import WIN_REASON_DECKOUT, WIN_REASON_LP
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"


def run_many(n=12):
    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    results = []
    for i in range(n):
        with Duel((i + 1, i + 7, i + 13, i + 29), lib=lib, carddb=db, scripts=sp) as d:
            d.load_deck(0, deck.main, deck.extra, shuffle_seed=i)
            d.load_deck(1, deck.main, deck.extra, shuffle_seed=i + 500)
            d.start()
            results.append(d.run(RandomLegal(seed=i), max_steps=300_000,
                                 retry_limit=300))
    return results


def test_random_duels_all_complete():
    for r in run_many():
        assert r["winner"] is not None, "duel did not finish"


def test_random_play_reaches_more_of_the_message_space():
    msgs = Counter()
    for r in run_many():
        msgs.update(m.id for m in r["messages"])
    # Always-pass reaches 9 distinct types; playing should reach far more.
    assert len(msgs) >= 18, f"only reached {len(msgs)} message types"


def test_random_games_end_by_damage():
    """The baseline must actually attack.

    This assertion is inverted from what it originally was, and the history is
    the point. When the baseline never attacked, every game became a deck-out
    race - and because the player going second draws one extra card over the
    game, player 0 won 40/40 by turn order alone, with no relation to play
    quality. That made win rate useless as a signal.

    With attacks enabled, games end by LP damage and the win split becomes
    competitive. Turn order still matters enough that results must be reported
    split by going first vs. second, but it is no longer the whole story.
    """
    results = run_many()
    reasons = Counter(
        m.payload[1] for r in results for m in r["messages"]
        if m.id == 5 and len(m.payload) > 1
    )
    assert reasons[WIN_REASON_LP] > reasons[WIN_REASON_DECKOUT], (
        f"expected mostly LP-damage wins; a baseline that does not attack "
        f"makes every game a deck-out race. Got {dict(reasons)}"
    )


def test_both_players_can_win():
    """Guards against a return of the 40-0 turn-order artifact."""
    winners = Counter(r["winner"] for r in run_many(16))
    assert len(winners) > 1, (
        f"only one player ever wins ({dict(winners)}) - that is turn order, "
        f"not play"
    )
