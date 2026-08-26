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

    # Activating and setting the same card are different plays, and the step
    # says which one. This assertion used to expect None: before steps carried
    # a verb the tracker could not tell them apart, so it declined and paid for
    # a model call to be told what the plan already said. Declining here was
    # caution about a thing that was never ambiguous - the safety property is
    # that we never take an action the plan did not name, and "set" is not
    # named anywhere in this plan.
    assert tracker.choose(["activate: Fiend's Sanctuary",
                           "set spell/trap: Fiend's Sanctuary"]) == 0

    # Genuinely ambiguous: same card, same verb, two ways to reach it. The
    # plan does not distinguish them, so the model must.
    assert tracker.choose(["activate: Fiend's Sanctuary",
                           "activate: Fiend's Sanctuary"]) is None
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


def test_own_deck_is_listed_but_not_in_draw_order():
    """You know your decklist; you do not know the order.

    The Deck was rendered as a bare count, so a card sitting in it was
    invisible. On Seto VS Ishizu every plan called for Normal Summoning
    Obelisk the Tormentor - which is in the Deck and cannot be summoned from
    there - because nothing on the board said where it was, while its card
    text sat in the corpus reading as playable.

    The order matters as much as the contents: the engine holds the Deck in
    draw order, so printing it verbatim would hand over the next draw. Sorted
    output carries the list and not the sequence.
    """
    from engine.board import Board, CardInfo
    from engine.carddb import CardDB
    from engine.render import render_side

    db = CardDB()
    # Deliberately not in alphabetical order: Obelisk sits third in the engine's
    # list, and must not come out third.
    codes = [89631139, 89631139, 10000000, 42534368]   # BEWD, BEWD, Obelisk, Silent Doom
    b = Board(player=0, deck=[CardInfo(code=c) for c in codes], deck_count=len(codes))
    line = " ".join(render_side(db, b, viewer=0, label="YOU"))

    assert "Obelisk the Tormentor" in line, f"deck contents hidden:\n{line}"
    assert "order unknown" in line, "must not imply the order is meaningful"
    names = [db.name(c) for c in codes]
    shown = [n for n in sorted(set(names)) if n in line]
    assert len(shown) == len(set(names)), line
    # Sorted, so Obelisk cannot be read as "the third card you will draw".
    assert line.index("Blue-Eyes") < line.index("Obelisk") < line.index("Silent Doom")

    # The opponent's decklist is not public.
    opp = Board(player=1, deck=[CardInfo(code=c) for c in codes], deck_count=4)
    assert "Obelisk" not in " ".join(render_side(db, opp, viewer=0, label="OPP"))


def test_the_planner_is_shown_what_is_legal():
    """A plan written against the board alone can start with an illegal move.

    Every Seto plan opened by summoning a card the first menu did not offer.
    Absence from a twelve-item list is a far louder signal than inferring it
    from where a card is not.
    """
    from llm.prompt import plan_prompt

    out = plan_prompt("BOARD", "Win this turn.",
                      "   0) summon: Zanki\n   1) activate: Raigeki Break")
    assert "What you can legally do right now" in out
    assert "summon: Zanki" in out
    assert "cannot start" in out
    # Still works with no menu available (e.g. a mid-turn rebuild before one).
    assert "What you can legally do" not in plan_prompt("BOARD", "Win.")


def test_a_verbose_answer_is_still_readable():
    """Reading the first integer in a reply is not good enough.

    Claude Sonnet 5 answered a menu with "I'll start by clearing the
    opponent's board using my removal" - prose, no digits at all - after
    12,575 characters of reasoning, and both puzzles were abandoned as
    `invalid`. Models that explain themselves also scatter numbers through the
    explanation, where the first one ("Level 4 Cyberse") is rarely the answer.

    So: the marker the prompt asks for, then the last in-range number, then
    the first. Never the first integer anywhere.
    """
    from agents.llm_agent import LLMAgent
    from engine.carddb import CardDB

    class Stub:
        model = "stub"
        def complete(self, *a, **k):
            return "0"

    agent = LLMAgent(Stub(), CardDB(), [], system="stub")

    # The marker wins even with other numbers in the prose.
    assert agent._read_choice(
        "Zanki is Level 4 with 1500 ATK, so I will summon it.\nANSWER: 2", 6) == 2

    # No marker: the conclusion is at the end, not the beginning.
    assert agent._read_choice(
        "Level 4 Cyberse, 1800 ATK... therefore I choose 3", 6) == 3

    # An out-of-range marker is a refusal, not something to salvage.
    assert agent._read_choice("ANSWER: 11", 6) is None

    # Prose with no digits at all is unreadable, and must say so.
    before = agent.stats.unparseable
    assert agent._read_choice(
        "I'll start by clearing the opponent's board using my removal", 6) is None
    assert agent.stats.unparseable == before + 1


def test_step_separates_what_it_uses_from_what_it_spends():
    """A step names three cards and only one of them is the action.

    This is the bug that kept the plan advisory. "Activate Raigeki Break,
    discarding Night Assailant, destroying Dark Jeroid" hits three options in
    a Main Phase menu when matched card-by-card, reads as ambiguous, and goes
    to the model - so the more precisely a plan described itself, the less it
    was ever used.
    """
    from agents.plan_tracker import PlanTracker

    cards = ["Raigeki Break", "Night Assailant", "Dark Jeroid", "Zanki",
             "La Jinn the Mystical Genie of the Lamp"]
    tracker = PlanTracker.parse(
        "1. Activate Raigeki Break, discarding Night Assailant, "
        "destroying Dark Jeroid.\n"
        "2. Tribute Summon Zanki by Tributing "
        "La Jinn the Mystical Genie of the Lamp.",
        cards)

    one, two = tracker.steps
    assert one.actor == ("Raigeki Break",)
    assert set(one.operands) == {"Night Assailant", "Dark Jeroid"}

    # "Tribute Summon" is the action, not the cost - the split has to happen
    # at the second "Tribut-", or the step loses its own actor.
    assert two.actor == ("Zanki",), two.actor
    assert two.operands == ("La Jinn the Mystical Genie of the Lamp",)

    # The whole point: a Main Phase menu offering all three now resolves.
    menu = ["activate: Raigeki Break", "summon: Night Assailant",
            "set monster: Night Assailant", "to battle phase"]
    assert tracker.choose(menu) == 0


def test_named_operands_are_carried_out_without_a_model_call():
    """The discard and target menus are where most of the calls went.

    Twelve of nineteen calls in a measured run were the executor answering
    sub-decisions, at 9s each. When the plan names the answer there is nothing
    left to decide.
    """
    from agents.plan_tracker import PlanTracker

    cards = ["Monster Reincarnation", "Lava Golem", "Dark Necrofear"]
    tracker = PlanTracker.parse(
        "1. Activate Monster Reincarnation, discarding Lava Golem, "
        "adding Dark Necrofear from the GY to hand.", cards)

    # Nothing is active until an action has actually been taken.
    assert tracker.choose_operand(["Lava Golem", "Zanki"]) is None

    menu = ["activate: Monster Reincarnation", "to battle phase"]
    assert tracker.choose(menu) == 0
    tracker.note_choice(menu[0], menu)

    # The discard menu lists the hand; only one operand is in it.
    assert tracker.choose_operand(["Zanki", "Lava Golem", "Upstart Goblin"]) == 1
    # The add-from-GY menu lists the GY; the spent operand is not reused.
    assert tracker.choose_operand(["Dark Necrofear", "Lava Golem"]) == 0
    # Both operands spent - anything further is not something the plan named.
    assert tracker.choose_operand(["Zanki", "Upstart Goblin"]) is None


def test_a_step_is_dead_on_its_action_not_on_a_mentioned_card():
    """is_dead used to read a step as alive because its *target* was listed.

    That is how a plan stayed "alive" while the thing it wanted to do was
    unavailable, and it is the likeliest source of the replans seen on every
    run of Home_of_the_Fiends.
    """
    from agents.plan_tracker import PlanTracker

    tracker = PlanTracker.parse(
        "1. Activate Raigeki Break, destroying Dark Jeroid.",
        ["Raigeki Break", "Dark Jeroid"])

    # Dark Jeroid is named, but nothing here activates Raigeki Break.
    assert tracker.is_dead(["summon: Dark Jeroid", "to end phase"]) is True
    assert tracker.is_dead(["activate: Raigeki Break"]) is False


def test_the_agent_answers_a_named_discard_without_calling_the_model():
    """Assert on the positive: the mechanism must actually fire.

    A test that only proved "no wrong action was taken" would pass against
    auto-execution that never triggers at all - which is what the tracker did
    before steps carried roles, at 1 auto-taken decision in 19.
    """
    from agents.llm_agent import LLMAgent, _CardMenu
    from agents.plan_tracker import PlanTracker
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
    agent.tracker = PlanTracker.parse(
        "1. Activate Monster Reincarnation, discarding Lava Golem.",
        ["Monster Reincarnation", "Lava Golem"])

    menu = ["activate: Monster Reincarnation", "to end phase"]
    agent.tracker.note_choice(menu[0], menu)

    class Discard:
        operand_menu = True
        deliberate = True

        def actions(self):
            return [(99, 0, None), (99, 1, None)]

    # A card menu whose labels the agent builds itself; stub _labels so the
    # test exercises the routing rather than the card database.
    agent._labels = lambda cmd, names: ["Zanki", "Lava Golem"]

    assert agent._ask(None, Discard(), 2) == 1
    assert provider.calls == 0, "asked the model something the plan already said"
    assert agent.stats.from_plan_operand == 1


def test_a_discard_the_plan_did_not_name_is_not_auto_taken():
    """The safety property, unchanged: never commit to an unnamed action.

    Scoped to the gate's own decision rather than a full `_ask`. Past the gate
    the code builds an event log and a board render, which needs a real duel;
    stubbing one out here would test the stub. The early return above it is
    covered by the positive test - it fires only when this is not None.
    """
    from agents.plan_tracker import PlanTracker

    tracker = PlanTracker.parse(
        "1. Activate Monster Reincarnation.", ["Monster Reincarnation"])
    menu = ["activate: Monster Reincarnation", "to end phase"]
    tracker.note_choice(menu[0], menu)

    # The step named no cost, so nothing in this menu is a plan instruction.
    assert tracker.choose_operand(["Zanki", "Lava Golem"]) is None

    # And a step that names two, both offered at once, is ambiguous - the
    # plan does not say which menu is which.
    two = PlanTracker.parse(
        "1. Activate Raigeki Break, discarding Zanki, destroying Lava Golem.",
        ["Raigeki Break", "Zanki", "Lava Golem"])
    m2 = ["activate: Raigeki Break", "to end phase"]
    two.note_choice(m2[0], m2)
    assert two.choose_operand(["Zanki", "Lava Golem"]) is None
