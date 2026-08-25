#!/usr/bin/env python3
"""Find the battle phases where a policy could have won and did not.

    python scripts/lethal_audit.py --agent random -n 20
    python scripts/lethal_audit.py --agent llm --seed 100 -n 1

`docs/PLAN.md` records that the agent "plays real lines but does not yet close
games" - it wins by deck-out rather than damage. That is a symptom, and this
locates the cause: every battle-phase decision is scored against the board the
engine reports, so a declined attack, or a declined *lethal*, is a fact rather
than an impression.

Output names the seed and turn of each miss, which is the point. Duels export
to `.yrp`, so a miss here is something you can go and watch: open
`runs/duel-<seed>.yrp` in EDOPro and scrub to that turn.

A "lethal window" is deliberately conservative - the opponent controls no
monsters, so every attack is direct, and our attackers' current ATK sums to at
least their life points. No trample maths, no assumption about what they hold.
It undercounts, which is the right direction for a number meant to prove a
problem exists.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.random_legal import RandomLegal
from engine.board import query_field, read_board
from engine.carddb import CardDB, ScriptProvider
from engine.constants import MSG_SELECT_BATTLECMD, MSG_WIN
from engine.deck import Deck
from engine.duel import Duel
from engine.messages import BATTLE_ATTACK, parse_select_battlecmd
from engine.ocgapi import load

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"

#: MSG_WIN's second byte (processor.cpp, where `rea` is assigned).
WIN_REASON = {0: "effect", 1: "life points", 2: "deck-out"}


class Audit:
    """Wraps a policy and scores its battle-phase decisions."""

    def __init__(self, inner, viewer=0):
        self.inner = inner
        self.viewer = viewer
        self.battles = 0
        self.declined = 0
        self.lethal_windows = 0
        self.lethal_declined = 0
        self.misses: list[tuple[int, int, int]] = []   # turn, damage, their LP
        self.reasons = Counter()

    def __call__(self, msg, duel) -> bytes:
        resp = self.inner(msg, duel)
        if msg is None or msg.id != MSG_SELECT_BATTLECMD:
            return resp
        cmd = parse_select_battlecmd(msg.payload)
        if cmd.player != self.viewer or not cmd.attackable:
            return resp

        self.battles += 1
        chose_attack = (int.from_bytes(resp, "little", signed=True) & 0xFFFF
                        ) == BATTLE_ATTACK
        if not chose_attack:
            self.declined += 1

        fi = query_field(duel)
        theirs = read_board(duel, 1 - self.viewer)
        ours = read_board(duel, self.viewer)
        if fi is None or any(theirs.monsters):
            self.reasons["they had a monster"] += 0 if chose_attack else 1
            return resp

        # Open field: every attackable monster hits directly.
        atk = 0
        for ref in cmd.attackable:
            card = (ours.monsters[ref.sequence]
                    if ref.sequence < len(ours.monsters) else None)
            if card and not card.defense_position:
                atk += card.attack
        their_lp = fi.lp[1 - self.viewer]
        if atk >= their_lp > 0:
            self.lethal_windows += 1
            if not chose_attack:
                self.lethal_declined += 1
                self.misses.append((duel.turn_count, atk, their_lp))
        elif not chose_attack:
            self.reasons["open field, not lethal"] += 1
        return resp


def make(kind, db, deck, seed):
    if kind == "random":
        return RandomLegal(seed=seed), None
    from agents.hierarchical import HierarchicalAgent
    from llm.provider import from_config
    planner, executor = from_config("planner"), from_config("executor")
    return HierarchicalAgent(planner, executor, db, deck.main + deck.extra), \
        (planner, executor)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="random", choices=["random", "llm"])
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=100)
    args = ap.parse_args()

    deck = Deck.from_ydk(DECK)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    totals = Audit(None)
    per_seed = []
    endings = Counter()

    for k in range(args.n):
        seed = args.seed + k
        inner, _ = make(args.agent, db, deck, seed)
        audit = Audit(inner, viewer=0)
        with Duel((seed + 1, seed + 7, seed + 13, seed + 29),
                  lib=lib, carddb=db, scripts=sp) as d:
            d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed)
            d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed + 500)
            d.start()
            r = d.run(audit, max_steps=300_000, retry_limit=400,
                      policy1=RandomLegal(seed=seed + 1000))
        rea = next((m.payload[1] for m in r["messages"]
                    if m.id == MSG_WIN and len(m.payload) > 1), None)
        endings[(r["winner"], WIN_REASON.get(rea, rea))] += 1
        print(f"  seed {seed:<5} winner P{r['winner']} by "
              f"{WIN_REASON.get(rea, rea)}  "
              f"{audit.battles} battle decisions, {audit.declined} declined, "
              f"{len(audit.misses)} lethal declined")
        for f in ("battles", "declined", "lethal_windows", "lethal_declined"):
            setattr(totals, f, getattr(totals, f) + getattr(audit, f))
        totals.reasons.update(audit.reasons)
        for turn, atk, lp in audit.misses:
            per_seed.append((seed, turn, atk, lp))

    print(f"\n{args.n} duels, {args.agent} as P0\n")
    for (w, why), n in sorted(endings.items(), key=lambda x: -x[1]):
        print(f"  P{w} won by {why:12s} x{n}")
    print()
    print(f"  battle decisions with an attack available   {totals.battles}")
    print(f"  ...where it declined to attack              {totals.declined}"
          f"  ({100*totals.declined/max(totals.battles,1):.0f}%)")
    print(f"  lethal on board (open field, ATK >= their LP) {totals.lethal_windows}")
    print(f"  ...declined                                 {totals.lethal_declined}")
    if per_seed:
        print("\n  go watch these:")
        for seed, turn, atk, lp in per_seed[:15]:
            print(f"    runs/duel-{seed}.yrp   turn {turn:<3} "
                  f"{atk} ATK on the board vs {lp} LP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
