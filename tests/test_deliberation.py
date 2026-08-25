"""The planner/executor split rule.

Cheap to test because it does not depend on what the models answer - only on
the duel's counters and the board - so a random-legal duel exercises it
exactly as an LLM duel would, and for free.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.deliberation import Deliberation
from agents.random_legal import RandomLegal
from engine.carddb import CardDB, ScriptProvider
from engine.constants import DECISION_MESSAGES
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load
from scripts.deliberation_report import Always, Both

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"


def run(rules, seed=100):
    deck = Deck.from_ydk(DECK)
    with Duel((seed + 1, seed + 7, seed + 13, seed + 29),
              lib=load(), carddb=CardDB(), scripts=ScriptProvider()) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed)
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed + 500)
        d.start()
        inner = RandomLegal(seed=seed)

        def policy(msg, duel):
            if msg is not None and msg.id in DECISION_MESSAGES:
                for r in rules:
                    r.note(duel, 0, r.why(duel, 0))
            return inner(msg, duel)

        d.run(policy, max_steps=300_000, retry_limit=400,
              policy1=RandomLegal(seed=seed + 1000))
    return rules


def test_shipped_rule_is_the_one_the_report_measures():
    """`scripts/deliberation_report.py` justifies the rule with a table. If
    the shipped rule and the table's winner drift apart, the justification is
    for something that is no longer running."""
    shipped, measured = run([Deliberation(), Both()])
    assert shipped.planned == measured.planned
    assert shipped.executed == measured.executed


def test_gate_only_ever_removes_planner_calls():
    """The gate is a cost fix. It must be a strict subset of the old rule -
    a variant that plans somewhere the old one did not is a different change
    wearing the same name."""
    shipped, always = run([Deliberation(), Always()])
    assert shipped.planned < always.planned, "gate had no effect at all"
    assert shipped.total == always.total, "the two saw different decisions"
    for edge in ("our turn start", "opponent chained"):
        assert shipped.triggers.get(edge) == always.triggers.get(edge), \
            f"{edge} must be untouched - only the chain edge was gated"


def test_our_own_uncontested_chain_does_not_replan():
    """The dominant waste: half of all chain resolutions were our own, with
    nobody interfering. That is the plan working, not news."""
    shipped, always = run([Deliberation(), Always()])
    ours = always.triggers["chain resolved"] - shipped.triggers.get(
        "opponent's chain changed the board", 0)
    assert ours > 0.3 * always.triggers["chain resolved"], (
        "expected our own chains to dominate resolutions; if this fell, the "
        "measurement behind the rule is stale"
    )
