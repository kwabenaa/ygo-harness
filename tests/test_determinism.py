"""The property everything else stands on.

Replay-based state restore - which the search layer needs, and which the .yrp
export reuses - is only sound if (seed, response log) fully determines a duel.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.deck import Deck
from engine.duel import Duel
from scripts.smoke_duel import always_pass

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"
SEED_A = (0x123456789ABCDEF0, 0x0FEDCBA987654321, 0xDEADBEEFCAFEBABE, 42)
SEED_B = (1, 2, 3, 4)


def stream(seed):
    deck = Deck.from_ydk(DECK)
    with Duel(seed) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed[0])
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed[1])
        d.start()
        r = d.run(always_pass, max_steps=200_000)
    return r, b"".join(bytes([m.id]) + m.payload for m in r["messages"])


def test_same_seed_is_byte_identical():
    _, a = stream(SEED_A)
    _, b = stream(SEED_A)
    assert a == b, "same seed produced a different message stream"


def test_different_seed_diverges():
    _, a = stream(SEED_A)
    _, b = stream(SEED_B)
    assert a != b, "seed is not affecting the duel - is the deck being shuffled?"


def test_duel_completes_without_retries():
    r, _ = stream(SEED_A)
    assert r["retries"] == 0, f"invalid responses: {r['retries']} retries"
    assert r["winner"] is not None, "duel did not reach a result"


def test_no_missing_card_scripts():
    r, _ = stream(SEED_A)
    assert not r["missing_scripts"], f"missing: {r['missing_scripts']}"
