#!/usr/bin/env python3
"""Measure planner/executor split rules without buying a single token.

    python scripts/deliberation_report.py -n 20

When to deliberate depends on the duel's counters and the board, not on what
the models answer, so a random-legal duel exercises every rule exactly as an
LLM duel would - deterministically, and for free. That matters: the split is
a cost decision, and a cost decision measured once by hand on a paid run is a
cost decision nobody re-measures.

**Read the absolute counts, not the percentage.** Random play makes worse
choices, so its duels run longer and pile up far more near-forced executor
decisions than an agent's do. That inflates the denominator: the same rule
that reads as 64% planner over an LLM duel reads as ~19% here. Planner calls
*per duel* is the number that transfers.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.deliberation import Deliberation
from agents.random_legal import RandomLegal
from engine.board import board_signature
from engine.carddb import CardDB, ScriptProvider
from engine.constants import DECISION_MESSAGES
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"


class Rule(Deliberation):
    """Everything shares the turn-start and opponent-chained edges; the
    variants differ only in what they do at a chain resolution."""

    label = "?"

    def at_chain_end(self, duel, viewer) -> str | None:
        raise NotImplementedError

    def why(self, duel, viewer, cmd=None):
        if duel.turn_count != self._turn:
            self._turn = duel.turn_count
            self._chain = duel.chain_count
            self._chain_end = duel.chain_end_count
            if duel.turn_player == viewer:
                return "our turn start"
        if duel.chain_count != self._chain:
            self._chain = duel.chain_count
            if duel.last_chain_player != viewer:
                return "opponent chained"
        if duel.chain_end_count != self._chain_end:
            self._chain_end = duel.chain_end_count
            return self.at_chain_end(duel, viewer)
        return None


class Always(Rule):
    label = "any chain resolves (before)"

    def at_chain_end(self, duel, viewer):
        return "chain resolved"


class BoardChanged(Rule):
    label = "...and the board changed"

    def at_chain_end(self, duel, viewer):
        return ("chain changed the board"
                if board_signature(duel, viewer) != self._planned_sig else None)


class OpponentInvolved(Rule):
    label = "...and the opponent was in the chain"

    def at_chain_end(self, duel, viewer):
        return ("opponent's chain resolved"
                if duel.last_chain_player != viewer else None)


class Both(Rule):
    label = "...both conditions  <- in use"

    def at_chain_end(self, duel, viewer):
        if duel.last_chain_player == viewer:
            return None
        return ("opponent's chain changed the board"
                if board_signature(duel, viewer) != self._planned_sig else None)


class NoChainEdge(Rule):
    label = "...never (turn start + opponent chained only)"

    def at_chain_end(self, duel, viewer):
        return None


class Shape(Both):
    """The in-use chain edges, plus the menu-shape triggers.

    The counter edges only fire when something *happens* - a turn begins, an
    interruption lands - so a long combo turn was one planner call followed
    by a run of executor calls, whatever those decisions were worth. These
    triggers ask what is on the menu instead. They read only the menu, never
    the model's answer, so this stays a free measurement.
    """

    label = "...plus menu-shape triggers  <- new"

    def why(self, duel, viewer, cmd=None):
        return super().why(duel, viewer, cmd) or self.shape_of(cmd)


VARIANTS = [Always, BoardChanged, OpponentInvolved, Both, NoChainEdge, Shape]


def _menu(msg):
    """The action menu for a decision, where one can be parsed cheaply.

    Only the menus the shape triggers actually look at. Anything else scores
    as "no menu", which is the conservative reading - it can only undercount
    planner calls, never invent them.
    """
    from engine.constants import MSG_SELECT_BATTLECMD, MSG_SELECT_CHAIN, MSG_SELECT_IDLECMD
    from engine.messages import (
        parse_idlecmd, parse_select_battlecmd, parse_select_chain,
    )
    try:
        if msg.id == MSG_SELECT_IDLECMD:
            return parse_idlecmd(msg.payload)
        if msg.id == MSG_SELECT_BATTLECMD:
            return parse_select_battlecmd(msg.payload)
        if msg.id == MSG_SELECT_CHAIN:
            ch = parse_select_chain(msg.payload)
            if ch.options:
                class _Chain:
                    deliberate = True
                    def actions(self):
                        return list(ch.options)
                return _Chain()
    except Exception:
        return None
    return None


class Counting:
    """Plays randomly, but scores every rule at each decision it owns."""

    def __init__(self, seed, viewer, rules):
        self.inner = RandomLegal(seed=seed)
        self.viewer = viewer
        self.rules = rules

    def __call__(self, msg, duel) -> bytes:
        if msg is not None and msg.id in DECISION_MESSAGES:
            cmd = _menu(msg)
            for r in self.rules:
                r.note(duel, self.viewer, r.why(duel, self.viewer, cmd))
        return self.inner(msg, duel)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=100)
    args = ap.parse_args()

    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    rules = [v() for v in VARIANTS]

    for k in range(args.n):
        seed = args.seed + k
        with Duel((seed + 1, seed + 7, seed + 13, seed + 29),
                  lib=lib, carddb=db, scripts=sp) as d:
            d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed)
            d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed + 500)
            d.start()
            d.run(Counting(seed, 0, rules), max_steps=300_000, retry_limit=400,
                  policy1=RandomLegal(seed=seed + 1000))

    n = args.n
    base = rules[0].planned
    print(f"{n} duels, player 0's decisions only "
          f"({rules[0].total // n} decisions/duel)\n")
    print(f"  {'rule':46s} {'planner/duel':>13s} {'vs before':>10s}")
    for r in rules:
        delta = "" if r.planned == base else f"{100*(r.planned-base)/base:+.0f}%"
        print(f"  {r.label:46s} {r.planned/n:13.1f} {delta:>10s}")
    print()
    for r in rules:
        print(f"  {r.label:46s} {r.triggers}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
