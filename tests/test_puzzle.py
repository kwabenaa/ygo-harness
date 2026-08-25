"""EDOPro puzzle loading, parsing, and field construction.

The expected values here are transcribed from the puzzle's own Lua source,
not produced by engine/puzzle.py. That matters: a test whose input our own
parser generated cannot fail for the interesting reason - our reader would
simply agree with our reader, exactly the way the .yrp writer agreed with the
.yrp parser for two commits while the file would not open.

The puzzle pinned below is data/Puzzles/Miscellaneous/Puzzle_13_Infernity_Combo.lua.
Its counts were read with grep over the file, and the whole test module skips
when the collection has not been fetched.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import board
from engine.constants import (
    LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND,
    LOCATION_MZONE, LOCATION_SZONE, MSG_SELECT_IDLECMD,
)
from engine.duel import Duel
from engine.messages import parse_idlecmd
from engine.puzzle import Puzzle, iter_puzzles

PINNED = "Puzzle_13_Infernity_Combo.lua"

#: Transcribed from the file, per (player, location).
PINNED_FIELD = {
    (0, LOCATION_DECK): 10,
    (0, LOCATION_EXTRA): 16,
    (0, LOCATION_GRAVE): 9,
    (0, LOCATION_HAND): 1,
    (1, LOCATION_HAND): 1,
    (1, LOCATION_MZONE): 3,
    (1, LOCATION_SZONE): 1,
}
PINNED_LP = {0: 100, 1: 12000}
PINNED_RULE = 3


def _pool_available() -> bool:
    try:
        from engine.puzzle import find_pool
        find_pool()
        return True
    except FileNotFoundError:
        return False


pytestmark = pytest.mark.skipif(
    not _pool_available(),
    reason="puzzle collection not fetched - run scripts/fetch_data.sh",
)


@pytest.fixture(scope="module")
def pinned() -> Puzzle:
    for p in iter_puzzles():
        if p.path.name == PINNED:
            return p
    pytest.skip(f"{PINNED} not in the pinned collection")


def test_metadata_matches_source(pinned: Puzzle):
    assert pinned.rule == PINNED_RULE
    assert pinned.lp == PINNED_LP
    assert pinned.objective.startswith("Objective:")
    assert not pinned.unparsed_cards
    assert pinned.skip_reason() is None


def test_declared_field_matches_source(pinned: Puzzle):
    assert pinned.declared_counts() == PINNED_FIELD


def test_engine_builds_the_declared_field(pinned: Puzzle):
    """The field the core actually holds, not the one we parsed.

    Card counts read back through the query API, which is the same path the
    renderer uses - so this fails if placement is wrong OR if the query
    buffer's length prefix is mishandled (trap 4), which otherwise renders as
    an empty board rather than as an error.
    """
    with Duel.from_puzzle(pinned) as duel:
        duel.start()
        actual = {
            (player, loc): board.count(duel, player, loc)
            for player, loc in PINNED_FIELD
        }
    assert actual == PINNED_FIELD


def test_puzzle_offers_real_options(pinned: Puzzle):
    """Assert on a positive: the agent is actually given something to do.

    The engine fails quietly here. Without the global Lua scripts every card
    loses its effects and the idle menu collapses to summon/set only, which
    presents as a game where nothing has an ability rather than as an error
    (trap 1). An empty activatable list must fail this test, not pass it.
    """
    seen_idle = None
    with Duel.from_puzzle(pinned) as duel:
        duel.start()

        def capture(msg, _duel):
            nonlocal seen_idle
            if msg is not None and msg.id == MSG_SELECT_IDLECMD and seen_idle is None:
                seen_idle = parse_idlecmd(msg.payload)
            raise StopIteration

        try:
            duel.run(capture, max_steps=2000)
        except StopIteration:
            pass

    assert seen_idle is not None, "no idle decision was ever reached"
    assert seen_idle.actions(), "idle menu was empty"
    assert seen_idle.activatable, (
        "no activatable effects offered - the usual cause is that the shared "
        "Lua scripts did not load, leaving every card with no effects"
    )


def test_rush_puzzles_are_excluded():
    """Rush Duel is a different ruleset and card pool, and must not run here.

    Roughly half the collection is Rush. Silently attempting those would
    report a wall of harness faults that say nothing about the harness.
    """
    pool = list(iter_puzzles())
    assert len(pool) > 200, "collection looks truncated"
    rush = [p for p in pool if p.is_rush]
    assert rush, "no Rush puzzles found - did the collection change?"
    assert all(p.skip_reason() == "rush" for p in rush)
    assert all(not p.is_rush for p in pool if p.skip_reason() is None)


#: The puzzles that exposed the stale-pending bug, by name. Each one blocked
#: on a message missing from DECISION_MESSAGES - MSG_ANNOUNCE_RACE,
#: MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD or MSG_SELECT_SUM - and the failure
#: was reported against whatever question happened to be pending instead.
#: Plus the two genuine format bugs: SORT_CARD wanted a permutation, and
#: SELECT_SUM has a second "at least" mode.
REGRESSION_PUZZLES = [
    "AlphaKretin_07_Xyz_Change.lua",          # MSG_ANNOUNCE_RACE
    "RashFaustinho_01_Obliterate.lua",        # MSG_ANNOUNCE_ATTRIB
    "AlphaKretin_05_Lullaby.lua",             # MSG_ANNOUNCE_CARD
    "Gideons_Unbreakable_Board.lua",          # MSG_ANNOUNCE_CARD
    "Tutorial_Ritual_Advanced.lua",           # MSG_SELECT_SUM, exact mode
    "[WCS2006]33_Match Point.lua",            # MSG_SELECT_SUM, at-least mode
    "Puzzle_06_Tool_and_Offerings.lua",       # MSG_SORT_CARD permutation
]


@pytest.mark.parametrize("filename", REGRESSION_PUZZLES)
def test_previously_broken_puzzles_run_clean(filename):
    """Runs to a verdict without raising or stalling.

    Asserts a *winner exists*, not that the puzzle was solved - random play
    losing is the expected outcome and says nothing about the harness. What
    must not happen is an exception or an unanswered question.
    """
    from scripts.run_puzzles import run_one, HARNESS_FAULTS
    from agents.random_legal import RandomLegal

    puzzle = next((p for p in iter_puzzles() if p.path.name == filename), None)
    if puzzle is None:
        pytest.skip(f"{filename} not in the pinned collection")

    result = run_one(puzzle, lambda player: RandomLegal(seed=player * 1000))
    assert result["outcome"] not in HARNESS_FAULTS, result["detail"]
    assert not result["unhandled"], (
        f"answered {result['unhandled']} generically - that is a missing decoder"
    )


def test_face_down_defence_is_not_reported_as_attack():
    """Battle position must survive rendering, including face-down defence.

    `monster_label` used to test POS_FACEUP_DEFENSE alone, so a monster set
    face-down in defence - the normal way to set a monster - was described to
    the agent as being in attack position, with its ATK where its DEF should
    be. Nothing raised; the agent was simply told something false about the
    board, which is the failure mode this codebase specialises in.
    """
    from engine.board import CardInfo
    from engine.constants import (
        POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK, POS_FACEUP_DEFENSE,
    )
    from engine.render import monster_label

    class FakeDB:
        def name(self, code):
            return "Test Monster"

    db = FakeDB()

    def make(pos):
        # base_* must be set: the renderer reports a buff as the gap between
        # current and base, so a fixture leaving base at zero claims the whole
        # ATK is a buff. Real cards always carry both, because LIST_FLAGS and
        # FIELD_FLAGS both request them.
        return CardInfo(code=1, position=pos, attack=1000, defense=1500,
                        base_attack=1000, base_defense=1500)

    card = make(POS_FACEDOWN_DEFENSE)

    mine = monster_label(db, card, reveal=True)
    assert "DEF" in mine and "ATK" not in mine, mine
    assert "face-down" in mine, mine

    # The opponent's face-down stays masked - position included.
    assert monster_label(db, card, reveal=False) == "[set]"

    up_def = make(POS_FACEUP_DEFENSE)
    assert monster_label(db, up_def, reveal=True).endswith("DEF")

    up_atk = make(POS_FACEUP_ATTACK)
    up_atk_label = monster_label(db, up_atk, reveal=True)
    assert up_atk_label.endswith("ATK")
    # Both numbers are shown regardless of position: a position change makes
    # the other one immediately relevant.
    assert "1000/1500" in up_atk_label


def test_modified_stats_are_shown_as_modified():
    """A buffed monster must not read as its printed stats.

    Current ATK comes from the engine and the printed value from the card
    database, and when they disagree the engine is right. Showing only the
    current number leaves the agent unable to tell a 3200 ATK Link monster
    from one pumped to 3200, which changes whether the buff can be removed.
    """
    from engine.board import STATUS_DISABLED, CardInfo
    from engine.constants import POS_FACEUP_ATTACK
    from engine.render import monster_label

    class FakeDB:
        def name(self, code):
            return "Test Monster"

    buffed = CardInfo(code=1, position=POS_FACEUP_ATTACK, attack=3200,
                      defense=0, base_attack=3000, base_defense=0)
    label = monster_label(FakeDB(), buffed, reveal=True)
    assert "3200" in label and "base 3000" in label, label

    negated = CardInfo(code=1, position=POS_FACEUP_ATTACK, attack=1000,
                       defense=1000, base_attack=1000, base_defense=1000,
                       status=STATUS_DISABLED)
    assert "NEGATED" in monster_label(FakeDB(), negated, reveal=True)

    xyz = CardInfo(code=1, position=POS_FACEUP_ATTACK, attack=2500,
                   defense=2000, base_attack=2500, base_defense=2000,
                   rank=4, overlay=(11, 22))
    label = monster_label(FakeDB(), xyz, reveal=True)
    assert "Rk4" in label and "2 materials" in label, label


def test_select_card_candidates_are_real_cards():
    """Every card offered in a selection must resolve to a real card.

    MSG_SELECT_CARD writes a uint32 code followed by a full 10-byte loc_info
    per entry. Skipping 4 bytes instead of 10 desynchronised the list, so
    every candidate after the first was read out of the middle of the previous
    entry's location blob. Nothing raised - the agent picked an index, and the
    engine acts on the index rather than the name, so the duel ran on with the
    agent reasoning about cards that were not there.

    Asserting the codes resolve is the check that catches it: garbage codes
    are not in the database. The payloads come from the engine, not from us.
    """
    from engine.carddb import CardDB
    from engine.constants import MSG_SELECT_CARD
    from engine.messages import parse_select_card
    from agents.random_legal import RandomLegal

    db = CardDB()
    puzzle = next((p for p in iter_puzzles()
                   if p.path.name == "Banyspy_03_Absolute_Defense.lua"), None)
    if puzzle is None:
        pytest.skip("pinned puzzle not present")

    seen, bad = 0, []

    class Watch:
        def __init__(self, seed):
            self.inner = RandomLegal(seed=seed)

        def __call__(self, msg, duel):
            nonlocal seen
            if msg is not None and msg.id == MSG_SELECT_CARD:
                sc = parse_select_card(msg.payload)
                assert len(sc.places) == len(sc.codes)
                for code in sc.codes:
                    seen += 1
                    if db.name(code).startswith("<"):
                        bad.append(code)
            return self.inner(msg, duel)

    with Duel.from_puzzle(puzzle) as duel:
        duel.start()
        duel.run(Watch(0), max_steps=30_000, policy1=Watch(1000))

    assert seen, "no card selection was ever reached - the test proves nothing"
    assert not bad, f"{len(bad)} of {seen} candidates are not real cards: {bad[:5]}"


def test_every_puzzle_card_is_known():
    """Every card a playable puzzle places must resolve, and have its script.

    Static, so it covers the whole pool without running a duel. Two failures
    it catches, both silent:

    - A code missing from the loaded databases renders as a bare passcode.
      Only two of BabelCDB's thirteen files were loaded, so a puzzle using a
      pre-errata GOAT card showed the agent `<504700159>` and the model spent
      its reasoning guessing what that was.
    - A card script in a directory the provider does not search is not an
      error; the card simply has no effects (trap 1). goat/, rush/ and skill/
      were all unsearched, which is 3452 scripts.
    """
    from engine.carddb import CardDB, ScriptProvider
    from engine.constants import TYPE_NORMAL

    db, scripts = CardDB(), ScriptProvider()
    unknown, scriptless = set(), set()
    for puzzle in iter_puzzles():
        if puzzle.skip_reason():
            continue
        for card in puzzle.cards:
            row = db.row(card.code)
            if row is None:
                unknown.add(card.code)
            elif row[2]:
                # An alias is an alternate printing - different passcode, same
                # card - and the core resolves it to the original's script, so
                # there is correctly no cXXXXXXX.lua of its own.
                continue
            elif not (row[4] & TYPE_NORMAL) and scripts.read(f"c{card.code}.lua") is None:
                scriptless.add((card.code, db.name(card.code)))

    assert not unknown, f"{len(unknown)} codes not in any database: {sorted(unknown)[:8]}"
    assert not scriptless, (
        f"{len(scriptless)} effect cards have no script - they will have no "
        f"abilities and nothing will say so: {sorted(scriptless)[:8]}"
    )


def test_the_board_states_the_phase():
    """The agent must be told which phase it is in.

    `render_state` has always accepted a `phase`, and the agent never passed
    one, so the board read `LP you 1000 / opp 2400` and nothing more. Nothing
    else reports the phase either - the query API describes the field, not
    where in the turn you are - so the agent inferred it from the shape of its
    action menu.

    It inferred wrong, and the cost was the whole turn: on the 2/10 puzzle it
    planned "Main Phase 2, summon Zanki, attack with both", declined a free
    direct attack to carry that out, and lost. You cannot attack from Main
    Phase 2. This test pins the Battle Phase specifically, because that is the
    decision where being wrong is unrecoverable.
    """
    from engine.constants import MSG_SELECT_BATTLECMD, MSG_SELECT_IDLECMD
    from engine.carddb import CardDB
    from engine.messages import (
        BATTLE_TO_EP, BattleCmd, IDLE_TO_BP, IdleCmd, parse_idlecmd,
    )
    from engine.render import render_state
    from agents.random_legal import RandomLegal

    puzzle = next((p for p in iter_puzzles()
                   if "Home_of_the_Fiends" in p.path.name), None)
    if puzzle is None:
        pytest.skip("pinned puzzle not present")

    db = CardDB()
    headers = []

    class ToBattle:
        def __init__(self):
            self.inner = RandomLegal(seed=0)

        def __call__(self, msg, duel):
            if msg is not None and msg.id == MSG_SELECT_IDLECMD:
                cmd = parse_idlecmd(msg.payload)
                if cmd.to_bp:
                    return IdleCmd.encode(IDLE_TO_BP)
            if msg is not None and msg.id == MSG_SELECT_BATTLECMD:
                headers.append(render_state(duel, db, 0).splitlines()[0])
                return BattleCmd.encode(BATTLE_TO_EP)
            return self.inner(msg, duel)

    with Duel.from_puzzle(puzzle) as duel:
        duel.start()
        duel.run(ToBattle(), max_steps=30_000, policy1=RandomLegal(seed=1))

    assert headers, "never reached a battle-phase decision - the test proves nothing"
    assert all("Battle Phase" in h for h in headers), headers


def test_board_shows_every_zone_the_agent_can_use():
    """Graveyard in full, banished at all, and your own Extra Deck by name.

    Three zones were being read from the engine and then discarded before the
    agent saw them: the graveyard was truncated to its last six cards, the
    banished pile was never rendered, and the Extra Deck was a count. A count
    is useless - you cannot plan a Fusion, Synchro, Xyz or Link summon against
    the number 3 - and on the Mathmech puzzle the whole solution lives in
    those three cards.
    """
    from engine.carddb import CardDB
    from engine.render import render_state

    db = CardDB()
    puzzle = next((p for p in iter_puzzles() if "MathMech" in p.path.name), None)
    if puzzle is None:
        pytest.skip("pinned puzzle not present")

    with Duel.from_puzzle(puzzle) as duel:
        duel.start()
        state = render_state(duel, db, 0)

    own = [l for l in state.splitlines() if "Extra (" in l]
    assert own, f"own Extra Deck not listed by name:\n{state}"
    assert "Geomathmech Final Sigma" in state, (
        "Extra Deck contents missing - the agent cannot plan a summon it "
        f"cannot see:\n{state}")
    # The opponent's Extra Deck stays a count: it is not public information.
    assert any(re.search(r"Extra: \d+$", l) for l in state.splitlines()), state


def test_graveyard_is_not_truncated():
    """A revival effect reaches the whole graveyard, so the agent must see it."""
    from engine.board import Board, CardInfo
    from engine.carddb import CardDB
    from engine.render import render_side

    db = CardDB()
    # Ten distinct real cards in the graveyard; all ten must be named.
    codes = [46986414, 89631139, 27288416, 21844576, 58932615,
             28279543, 6368038, 4035199, 36211150, 32295838]
    b = Board(player=0, grave=[CardInfo(code=c) for c in codes])
    line = " ".join(render_side(db, b, viewer=0, label="YOU"))
    missing = [db.name(c) for c in codes if db.name(c) not in line]
    assert not missing, f"graveyard truncated, hiding: {missing}"


def test_plan_tracker_catches_the_ordering_failure():
    """Taking a later plan step while the next one is on the menu is the bug.

    On Seto VS Ishizu the agent had a correct lethal plan and ran step 4
    before step 3. Without the Token from step 3 it never had three tributes,
    so `summon: Obelisk` - the whole point of the plan - was never offered in
    a single menu afterwards. Both steps were legal at the moment it chose, so
    nothing in the prompt told it order mattered.

    The tracker reads only the legal-action menu the engine already provides.
    It never speculates and never asks for a rollback: see DECISIONS.md, "The
    agent never retraces".
    """
    from agents.plan_tracker import PlanTracker

    plan = (
        "1. Activate Fiend's Sanctuary to Special Summon a Metal Fiend Token.\n"
        "2. Activate The Monarchs Stormforth to tribute Kelbek.\n"
        "3. Normal Summon Obelisk the Tormentor.\n"
        "DAMAGE: 4000 = 4000"
    )
    cards = ["Fiend's Sanctuary", "The Monarchs Stormforth", "Obelisk the Tormentor"]
    menu = ["activate: Fiend's Sanctuary", "activate: The Monarchs Stormforth",
            "to battle phase"]

    # The DAMAGE line is commentary, not a step.
    assert len(PlanTracker.parse(plan, cards).steps) == 3

    out_of_order = PlanTracker.parse(plan, cards)
    out_of_order.note_choice("activate: The Monarchs Stormforth", menu)
    assert out_of_order.skipped_ahead == 1, "did not notice the skipped step"

    in_order = PlanTracker.parse(plan, cards)
    in_order.note_choice("activate: Fiend's Sanctuary", menu)
    assert in_order.skipped_ahead == 0
    assert in_order.steps[0].done

    # And the agent is told where it is, with the option number to use.
    rendered = in_order.render(menu)
    assert "NEXT" in rendered and "option 1" in rendered, rendered


def test_plan_tracker_says_when_a_step_is_unreachable():
    """A step the menu cannot offer is a dead plan, and must be called one.

    Without rollback the plan cannot be verified ahead of time - it can only
    be observed to have died. Saying so is the entire compensating mechanism.
    """
    from agents.plan_tracker import PlanTracker

    plan = "1. Normal Summon Obelisk the Tormentor."
    tracker = PlanTracker.parse(plan, ["Obelisk the Tormentor"])
    rendered = tracker.render(["to battle phase", "to end phase"])
    assert "NOT available" in rendered, rendered
    assert "the plan is dead" in rendered, rendered


def test_a_single_option_is_never_sent_to_the_model():
    """A menu with one option is not a decision.

    Asking anyway cost a full model call - at unbounded reasoning, tens of
    seconds - to be told the only thing that could be said. Across a puzzle
    that is minutes spent on questions with one answer.
    """
    from agents.llm_agent import LLMAgent
    from engine.carddb import CardDB

    class CountingProvider:
        model = "stub"

        def __init__(self):
            self.calls = 0

        def complete(self, system, user, **kw):
            self.calls += 1
            return "0"

    provider = CountingProvider()
    agent = LLMAgent(provider, CardDB(), [], system="stub")

    class OneOption:
        def actions(self):
            return [(7, 0, None)]

    # duel is only touched when a call is actually made, so None is safe here.
    assert agent._ask(None, OneOption(), 1) == 0
    assert provider.calls == 0, "asked the model a question with one answer"
    assert agent.stats.forced == 1


def test_plan_chooses_only_when_unambiguous():
    """The harness carries out a plan step, but never guesses at one.

    An index comes back only when exactly one option matches. Several matches
    or none go to the model. This is stricter than it needs to be on purpose:
    the agent cannot retrace, so a wrong auto-taken action is unrecoverable in
    a way a wrong branch in a search would not be.
    """
    from agents.plan_tracker import PlanTracker

    plan = ("1. Activate Fiend's Sanctuary to make a Token.\n"
            "2. Normal Summon Obelisk the Tormentor.")
    cards = ["Fiend's Sanctuary", "Obelisk the Tormentor"]
    tracker = PlanTracker.parse(plan, cards)

    assert tracker.choose(["activate: Fiend's Sanctuary", "to battle phase"]) == 0
    # Two ways to play the same card is a real choice, not a formality.
    assert tracker.choose(["activate: Fiend's Sanctuary",
                           "set spell/trap: Fiend's Sanctuary"]) is None
    assert tracker.choose(["to battle phase", "to end phase"]) is None

    # Nothing left to do means nothing to carry out.
    for step in tracker.steps:
        step.done = True
    assert tracker.choose(["activate: Fiend's Sanctuary"]) is None


def test_interrupts_are_never_auto_taken():
    """A chain window is exactly what the plan did not anticipate.

    `_ChainMenu` and `_CardMenu` both carry `deliberate`, and `_ask` checks it
    before consulting the tracker - so a plan step can never be used to answer
    an interrupt or a targeting decision on autopilot.
    """
    from agents.llm_agent import _CardMenu, _ChainMenu

    assert _ChainMenu.deliberate is True
    assert _CardMenu.deliberate is True


def test_a_dead_plan_is_detected():
    """A step naming a card the menu cannot act on is how a plan dies.

    Without rollback this is the only signal available - the plan cannot be
    verified ahead of time, only observed to have stopped working. Detecting
    it is what triggers a rebuild; telling the model in the prompt was not
    enough, since it read "step 3 is not available" and improvised on.

    One unavailable step is normal - it often needs something else first - so
    the caller requires it twice running before rebuilding.
    """
    from agents.plan_tracker import PlanTracker

    plan = "1. Declare a direct attack with Lava Golem."
    tracker = PlanTracker.parse(plan, ["Lava Golem"])

    # Lava Golem is summoned to the *opponent's* field, so it never appears as
    # something you may attack with. This is the real plan that lost a puzzle.
    assert tracker.is_dead(["to main phase 2", "to end phase"])
    assert not tracker.is_dead(["attack with: Lava Golem", "to end phase"])

    # A step naming no card cannot be judged either way.
    vague = PlanTracker.parse("1. Proceed to the Battle Phase.", ["Lava Golem"])
    assert not vague.is_dead(["to end phase"])
