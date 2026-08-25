#!/usr/bin/env python3
"""Play a duel and write a readable transcript.

    python scripts/play.py --agent llm --opponent random --seed 7
    python scripts/play.py --agent random --opponent random -n 5

Writes runs/duel-<seed>.txt unless --out says otherwise.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.hierarchical import HierarchicalAgent
from agents.random_legal import RandomLegal
from engine.board import query_field, read_board
from engine.carddb import CardDB, ScriptProvider
from engine.deck import Deck
from engine.duel import Duel
from engine.ocgapi import load
from viz.duel_log import DuelLog
from viz.replay import write_yrp

DECK = Path(__file__).parent.parent / "data" / "decks" / "sky_striker_pulp6.ydk"


def make_policy(kind, db, deck, seed):
    if kind == "random":
        return RandomLegal(seed=seed), None
    from llm.provider import from_config
    planner, executor = from_config("planner"), from_config("executor")
    agent = HierarchicalAgent(planner, executor, db, deck.main + deck.extra)
    return agent, (planner, executor)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="random", choices=["random", "llm"])
    ap.add_argument("--opponent", default="random", choices=["random", "llm"])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("-n", type=int, default=1, help="number of duels")
    ap.add_argument("--out", default=None)
    ap.add_argument("--deck", default=str(DECK))
    args = ap.parse_args()

    deck = Deck.from_ydk(args.deck)
    lib, db, sp = load(), CardDB(), ScriptProvider()
    outdir = Path(args.out or "runs")
    outdir.mkdir(exist_ok=True)

    for k in range(args.n):
        seed = args.seed + k
        p0, prov0 = make_policy(args.agent, db, deck, seed)
        p1, _ = make_policy(args.opponent, db, deck, seed + 1000)
        log = DuelLog(db, names=(f"{args.agent} (P0)", f"{args.opponent} (P1)"))

        t0 = time.perf_counter()
        with Duel((seed + 1, seed + 7, seed + 13, seed + 29),
                  lib=lib, carddb=db, scripts=sp) as d:
            d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed)
            d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed + 500)
            d.start()
            r = d.run(p0, max_steps=300_000, retry_limit=400, policy1=p1)
            fi = query_field(d)
            boards = (read_board(d, 0), read_board(d, 1))
            yrp = write_yrp(
                outdir / f"duel-{seed}.yrp",
                seed=(seed + 1, seed + 7, seed + 13, seed + 29),
                decks=d.dealt, responses=d.responses, duel_flags=d.flags,
                names=(f"{args.agent}", f"{args.opponent}"),
                start_lp=d.starting_lp, start_hand=d.starting_draw,
                draw_count=d.draw_per_turn,
            )
        dt = time.perf_counter() - t0

        for m in r["messages"]:
            log.feed(m)

        log.lines.append("")
        log.lines.append("--- final boards ---")
        for i, b in enumerate(boards):
            mon = [db.name(c.code) for c in b.monsters if c] or ["empty"]
            st = [db.name(c.code) for c in b.spells if c] or ["empty"]
            log.lines.append(f"  {log.names[i]}: LP {fi.lp[i] if fi else '?'}")
            log.lines.append(f"     M: {', '.join(mon)}")
            log.lines.append(f"     S: {', '.join(st)}")
        if prov0:
            log.lines.append("")
            log.lines.append(f"--- agent ---")
            log.lines.append(f"  planner:  {prov0[0].usage}")
            log.lines.append(f"  executor: {prov0[1].usage}")
            cost = (prov0[0].usage.cost(0.03, 0.13, 0.006)
                    + prov0[1].usage.cost(0.019, 0.030))
            log.lines.append(f"  cost:     ${cost:.4f}   wall: {dt:.0f}s")

        path = outdir / f"duel-{seed}.txt"
        log.save(str(path))
        print(f"seed {seed}: winner P{r['winner']}  turns {log.turn}  "
              f"{dt:.0f}s\n           transcript {path}\n           replay     {yrp}")


if __name__ == "__main__":
    raise SystemExit(main())
