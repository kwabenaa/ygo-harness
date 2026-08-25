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
