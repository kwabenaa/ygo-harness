#!/usr/bin/env python3
"""Run EDOPro puzzles through the harness and report what happened.

A puzzle is won or lost by the engine's own verdict: `aux.BeginPuzzle()`
registers an EVENT_TURN_END effect that sets the solver's life points to zero,
so surviving the turn *is* losing. That makes "solved" a fact rather than a
judgement, with no value function and no authored solution to diff against.

The number that matters here is NOT how many puzzles were solved. It is how
many the harness could *run*. A puzzle the agent loses is a puzzle the agent
lost; a puzzle that raises, stalls or hits an unhandled message is a bug in
`engine/`. Those two are reported separately and must never be added together.

    python scripts/run_puzzles.py --agent random
    python scripts/run_puzzles.py --filter Infernity -v
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.random_legal import RandomLegal
from engine.duel import Duel
from engine.puzzle import iter_puzzles

#: Generous, but bounded. A puzzle is a single turn; a run that needs more
#: steps than this is looping rather than playing.
MAX_STEPS = 30_000

SOLVED, UNSOLVED, STALLED, ERROR, SKIPPED = (
    "solved", "unsolved", "stalled", "error", "skipped"
)
#: Outcomes that indict the harness rather than the policy.
HARNESS_FAULTS = (STALLED, ERROR)


def run_one(puzzle, make_policy, max_steps: int = MAX_STEPS) -> dict:
    started = time.perf_counter()
    result = {
        "puzzle": puzzle.path.name,
        "name": puzzle.name,
        "rule": puzzle.rule,
        "outcome": None,
        "detail": "",
        "steps": 0,
        "unhandled": {},
        "missing_scripts": [],
        "marathon": puzzle.is_marathon,
    }

    reason = puzzle.skip_reason()
    if reason:
        result.update(outcome=SKIPPED, detail=reason)
        return result

    duel = None
    try:
        duel = Duel.from_puzzle(puzzle)
        duel.start()
        p0, p1 = make_policy(0), make_policy(1)
        out = duel.run(p0, max_steps=max_steps, policy1=p1)
        # The solver is always player 0. No winner means the loop ran out of
        # steps rather than the duel ending, which is a stall, not a loss.
        if out["winner"] is None:
            # A puzzle with no aux.BeginPuzzle() has no engine-enforced end,
            # so running out of steps means the policy did not win a full
            # duel - a loss, not a harness failure. Only the enforced ones
            # can genuinely stall, because PuzzleOp ends them at turn end.
            if puzzle.is_marathon:
                result.update(outcome=UNSOLVED,
                              detail="no win condition enforced (full duel)")
            else:
                result.update(outcome=STALLED,
                              detail=f"no winner in {max_steps} steps")
        else:
            result["outcome"] = SOLVED if out["winner"] == 0 else UNSOLVED
        result["steps"] = out["steps"]
        result["missing_scripts"] = out["missing_scripts"]
        unhandled: Counter = Counter()
        for pol in (p0, p1):
            unhandled.update(getattr(pol, "unhandled", {}) or {})
        result["unhandled"] = dict(unhandled)
    except Exception as exc:                        # noqa: BLE001 - reported, not swallowed
        result.update(outcome=ERROR, detail=f"{type(exc).__name__}: {exc}"[:200])
    finally:
        if duel is not None:
            duel.close()

    result["seconds"] = round(time.perf_counter() - started, 3)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--agent", default="random", choices=["random"],
                    help="policy to solve with (random costs nothing and is "
                         "the right one for finding decoder bugs)")
    ap.add_argument("--root", default=None, help="puzzle directory")
    ap.add_argument("--filter", default=None, help="substring match on filename")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    ap.add_argument("--json", default=None, help="write full results here")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    def make_policy(player: int):
        return RandomLegal(seed=args.seed + player * 1000)

    puzzles = [p for p in iter_puzzles(args.root)
               if not args.filter or args.filter.lower() in p.path.name.lower()]
    if args.limit:
        puzzles = puzzles[:args.limit]
    if not puzzles:
        print("no puzzles matched", file=sys.stderr)
        return 2

    results, tally = [], Counter()
    unhandled_total: Counter = Counter()
    missing_total: Counter = Counter()

    for i, puz in enumerate(puzzles, 1):
        r = run_one(puz, make_policy, args.max_steps)
        results.append(r)
        tally[r["outcome"]] += 1
        unhandled_total.update(r["unhandled"])
        missing_total.update(r["missing_scripts"])
        if args.verbose or r["outcome"] in HARNESS_FAULTS:
            print(f'{i:>4}/{len(puzzles)}  {r["outcome"]:<8} {r["puzzle"][:56]:<58}'
                  f'{r["detail"]}')

    ran = sum(tally[k] for k in (SOLVED, UNSOLVED, STALLED, ERROR))
    faults = sum(tally[k] for k in HARNESS_FAULTS)

    print("\n" + "=" * 68)
    print(f'  attempted     {ran}    (skipped {tally[SKIPPED]})')
    print(f'  ran clean     {ran - faults}'
          f'{"" if not ran else f"    {(ran - faults) / ran:.1%}"}   <- the harness number')
    print(f'  harness fault {faults}    ({tally[ERROR]} error, {tally[STALLED]} stalled)')
    print(f'  solved        {tally[SOLVED]}    <- the agent number, not a harness result')
    marathons = sum(1 for r in results if r.get("marathon"))
    if marathons:
        print(f'  of which {marathons} have no engine-enforced win condition '
              f'(no aux.BeginPuzzle)')

    if unhandled_total:
        print("\n  unhandled decision messages (each one is a missing decoder):")
        for mid, n in unhandled_total.most_common():
            print(f"    MSG id {mid}: {n}")
    if missing_total:
        print(f"\n  missing card scripts: {len(missing_total)} distinct")
        for name, n in missing_total.most_common(10):
            print(f"    {name}: {n}")

    if args.json:
        Path(args.json).write_text(json.dumps(
            {"summary": dict(tally), "unhandled": dict(unhandled_total),
             "missing_scripts": dict(missing_total), "results": results},
            indent=2))
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
