"""The agent must never see what a player could not see.

The query API returns the opponent's hand and the contents of their set cards
without complaint. Rendering either would leak perfect information into the
prompt and quietly invalidate every number this benchmark produces - a failure
that would not raise, crash, or look wrong in the output.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.board import read_board
from engine.carddb import CardDB, ScriptProvider
from engine.constants import MSG_SELECT_IDLECMD
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load
from engine.render import render_state

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"


def snapshots(viewer=0, stop_at=(2, 9, 17)):
    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    out = []

    class Probe(RandomLegal):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.k = 0

        def __call__(self, msg, duel):
            if msg is not None and msg.id == MSG_SELECT_IDLECMD:
                self.k += 1
                if self.k in stop_at:
                    out.append((
                        render_state(duel, db, viewer=viewer),
                        read_board(duel, 1 - viewer),
                    ))
            return super().__call__(msg, duel)

    with Duel((11, 22, 33, 44), lib=lib, carddb=db, scripts=sp) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=7)
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=8)
        d.start()
        d.run(Probe(seed=4), max_steps=300_000, retry_limit=300)
    return out, db


def opp_section(text: str) -> str:
    """Just the opponent's lines.

    Scoping matters: both players run the same deck here, so a whole-text
    substring search cannot tell "leaked their Ash Blossom" from "named my
    own Ash Blossom" and reports false leaks.
    """
    lines = text.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("OPP"))
    return "\n".join(lines[start:])


def test_opponent_hand_is_never_named():
    snaps, db = snapshots()
    assert snaps, "probe captured nothing"
    for text, opp in snaps:
        section = opp_section(text)
        for c in opp.hand:
            if c and c.code:
                assert db.name(c.code) not in section, (
                    f"leaked opponent hand card: {db.name(c.code)}"
                )
        assert "Hand:" in section, "opponent hand should be a count only"


def test_opponent_face_down_cards_are_masked():
    snaps, db = snapshots()
    for text, opp in snaps:
        section = opp_section(text)
        for c in list(opp.spells) + list(opp.monsters):
            if c and c.face_down and c.code:
                assert db.name(c.code) not in section, (
                    f"leaked opponent set card: {db.name(c.code)}"
                )


def test_masking_functions_directly():
    """Unambiguous check of the masking primitives - no mirror-match ambiguity."""
    from engine.board import CardInfo
    from engine.constants import POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK
    from engine.render import card_label, monster_label

    _, db = snapshots(stop_at=(1,))
    ENGAGE = 63166095
    face_down = CardInfo(code=ENGAGE, position=POS_FACEDOWN_DEFENSE)
    face_up = CardInfo(code=ENGAGE, position=POS_FACEUP_ATTACK, attack=1500)

    assert card_label(db, face_down, reveal=False) == "[set]"
    assert "Engage" in card_label(db, face_down, reveal=True)
    assert "Engage" in card_label(db, face_up, reveal=False), (
        "face-up cards are public - masking them would be wrong"
    )
    assert monster_label(db, face_down, reveal=False) == "[set]"
    assert card_label(db, None, reveal=True) == "-"


def test_own_information_is_visible():
    """The masking must not be so aggressive it hides the agent's own board."""
    snaps, _ = snapshots()
    later = snaps[-1][0]
    assert "Hand (" in later, "own hand should be enumerated"
    assert "LP you" in later, "life points should be shown"
