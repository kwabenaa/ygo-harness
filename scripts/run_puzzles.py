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

from agents.llm_agent import NoAnswer
from agents.random_legal import RandomLegal
from engine.carddb import CardDB
from engine.duel import Duel
from engine.puzzle import iter_puzzles

#: Generous, but bounded. A puzzle is a single turn; a run that needs more
#: steps than this is looping rather than playing.
MAX_STEPS = 30_000

SOLVED, UNSOLVED, STALLED, ERROR, SKIPPED, INVALID = (
    "solved", "unsolved", "stalled", "error", "skipped", "invalid"
)
#: Outcomes that indict the harness rather than the policy.
HARNESS_FAULTS = (STALLED, ERROR)
#: Not a loss. The agent never produced a usable answer, so the duel says
#: nothing about how well it plays - and the alternative, picking a move on
#: its behalf, is how one puzzle got thrown by an auto-activated Raigeki
#: Break that the model never chose.
NOT_A_RESULT = (INVALID,)


def write_conversation(path: Path, *, title: str, header: list[str],
                       system: str, trace: list) -> None:
    """The full exchange with the model: system prompt, then every decision.

    Dumped verbatim rather than summarised. The point of reading one of these
    is to see exactly what the agent was told - a summary would hide the
    rendering bugs worth finding, which is how a face-down defence monster
    was described as being in attack position for as long as it was.

    The system prompt is printed once because it is *sent* once: it is the
    cached prefix, built per duel and reused at every decision. It is also the
    only place the card data appears, so a record without it reads as though
    the agent had been shown nothing but card names.
    """
    lines = [f"# {title}", ""] + header + [""]
    if system:
        lines += [
            "=" * 72,
            "SYSTEM PROMPT  (sent once, cached, reused for every decision)",
            "=" * 72,
            system,
            "",
        ]
    for step in trace:
        lines += [
            "=" * 72,
            f"DECISION {step['n']}   (model: {step['model']})",
            "=" * 72,
            "--- sent to the model ---",
            step["shown"],
            "",
        ]
        # Untruncated on purpose. A record kept for diagnosis that elides the
        # model's own words is missing the half that explains the choice.
        if step.get("reasoning"):
            lines += ["--- model reasoning ---", step["reasoning"].strip(), ""]
        lines += [
            "--- model replied ---",
            step["reply"].strip() or "(empty)",
            "",
            f"--> harness took option: {step['chose']}",
            "",
        ]
    path.write_text("\n".join(lines))


def write_transcript(path: Path, puzzle, result: dict, trace: list,
                     system: str = "") -> None:
    """The conversation for one puzzle, prefixed with the puzzle's own text."""
    header = [
        f"file:      {puzzle.path.name}",
        f"objective: {puzzle.objective or '(none stated)'}",
        f"ruleset:   Master Rule {puzzle.rule}",
        f"complexity: {puzzle.complexity or '?'}/10",
        f"life:      you {puzzle.lp.get(0, '?')}  /  opponent {puzzle.lp.get(1, '?')}",
        f"outcome:   {result['outcome'].upper()}"
        f"  ({result.get('detail') or 'played to a verdict'})",
        f"decisions: {result.get('asked', 0)}",
    ]
    if puzzle.message:
        header += ["", "## Puzzle text", "", puzzle.message]
    write_conversation(path, title=puzzle.name, header=header, system=system,
                       trace=trace)


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
            inner = getattr(pol, "mechanical", None)
            if inner is not None:
                unhandled.update(getattr(inner, "unhandled", {}) or {})
        result["unhandled"] = dict(unhandled)
        split = getattr(p0, "split", None)
        if split is not None:
            result["planner_calls"] = split.planned
            result["executor_calls"] = split.executed
        stats = getattr(p0, "stats", None)
        if stats is not None:
            result["asked"] = stats.asked
            result["fallbacks"] = (stats.fallbacks + stats.unparseable
                                   + stats.out_of_range)
            result["truncated"] = stats.truncated
            result["reasked"] = stats.unparseable + stats.out_of_range
            result["no_plan"] = stats.no_plan
            tracker = getattr(p0, "tracker", None)
            if tracker is not None:
                result["skipped_ahead"] = tracker.skipped_ahead
                result["plan_steps"] = len(tracker.steps)
                result["plan_done"] = sum(1 for st in tracker.steps if st.done)
            result["unchecked_plans"] = stats.unchecked_plans
        result["_trace"] = getattr(p0, "trace", [])
        result["_system"] = getattr(p0, "system", "")
    except NoAnswer as exc:
        result.update(outcome=INVALID, detail=str(exc)[:200])
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
    ap.add_argument("--agent", default="random", choices=["random", "llm"],
                    help="random costs nothing and is the right one for "
                         "finding decoder bugs; llm actually tries to solve")
    ap.add_argument("--rule", type=int, default=None,
                    help="only puzzles declaring this Master Rule")
    ap.add_argument("--root", default=None, help="puzzle directory")
    ap.add_argument("--filter", default=None, help="substring match on filename")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--hardest", type=int, default=None, metavar="N",
                    help="only the N hardest puzzles, by the author's declared "
                         "complexity. Use --hardest 1 when debugging: a simple "
                         "puzzle is three decisions and proves nothing")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=MAX_STEPS)
    ap.add_argument("--json", default=None, help="write full results here")
    ap.add_argument("--transcript", default=None, metavar="DIR",
                    help="write one readable file per puzzle showing exactly "
                         "what the agent was shown and what it chose")
    ap.add_argument("--no-plan", action="store_true",
                    help="skip the per-turn planning call")
    ap.add_argument("--cheap", action="store_true",
                    help="use the normal duel routing instead of sending every "
                         "puzzle decision to the planner")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    db = CardDB() if args.agent == "llm" else None

    def policy_factory(puzzle):
        """Build the pair of policies for one puzzle.

        The solver is always player 0; player 1 stays random, because a puzzle
        opponent is not supposed to be playing - most of these set
        DUEL_SIMPLE_AI and the duel ends before the opponent's turn.
        """
        if args.agent == "random":
            return lambda player: RandomLegal(seed=args.seed + player * 1000)

        from agents.deliberation import Deliberation
        from agents.hierarchical import HierarchicalAgent
        from llm.provider import from_config
        from llm.prompt import puzzle_system_prompt

        codes = sorted({c.code for c in puzzle.cards})
        system = puzzle_system_prompt(db, codes, puzzle.objective)

        def build(player: int):
            if player == 1:
                return RandomLegal(seed=args.seed + 1000)
            return HierarchicalAgent(
                from_config("planner"), from_config("executor"), db, codes,
                viewer=0, system=system, verbose=args.verbose,
                # Everything to the planner. A puzzle is a single turn where
                # every choice is irreversible and there is no later turn to
                # recover in, so the turn-start edge would fire once and hand
                # the whole solve to the cheap model.
                split=Deliberation(always=not args.cheap),
                # One long think about the whole line before the first
                # action. A combo cannot be re-derived one decision at a
                # time: step three looks pointless unless you already know
                # steps four and five.
                planning=not args.no_plan,
                objective=puzzle.objective,
            )
        return build

    puzzles = [p for p in iter_puzzles(args.root)
               if (not args.filter or args.filter.lower() in p.path.name.lower())
               and (args.rule is None or p.rule == args.rule)]
    if args.hardest:
        puzzles = sorted(puzzles, key=lambda p: p.difficulty,
                         reverse=True)[:args.hardest]
    if args.limit:
        puzzles = puzzles[:args.limit]
    if not puzzles:
        print("no puzzles matched", file=sys.stderr)
        return 2

    results, tally = [], Counter()
    unhandled_total: Counter = Counter()
    missing_total: Counter = Counter()

    for i, puz in enumerate(puzzles, 1):
        r = run_one(puz, policy_factory(puz), args.max_steps)
        trace = r.pop("_trace", [])
        system = r.pop("_system", "")
        if args.transcript and trace:
            tdir = Path(args.transcript)
            tdir.mkdir(parents=True, exist_ok=True)
            write_transcript(tdir / f"{puz.path.stem}.txt", puz, r, trace, system)
        results.append(r)
        tally[r["outcome"]] += 1
        unhandled_total.update(r["unhandled"])
        missing_total.update(r["missing_scripts"])
        if args.verbose or r["outcome"] in HARNESS_FAULTS + NOT_A_RESULT:
            print(f'{i:>4}/{len(puzzles)}  {r["outcome"]:<8} {r["puzzle"][:56]:<58}'
                  f'{r["detail"]}')

    ran = sum(tally[k] for k in (SOLVED, UNSOLVED, STALLED, ERROR, INVALID))
    faults = sum(tally[k] for k in HARNESS_FAULTS)

    print("\n" + "=" * 68)
    print(f'  attempted     {ran}    (skipped {tally[SKIPPED]})')
    print(f'  ran clean     {ran - faults}'
          f'{"" if not ran else f"    {(ran - faults) / ran:.1%}"}   <- the harness number')
    print(f'  harness fault {faults}    ({tally[ERROR]} error, {tally[STALLED]} stalled)')
    print(f'  no answer     {tally[INVALID]}    (not losses - the model never chose)')
    print(f'  solved        {tally[SOLVED]}    <- the agent number, not a harness result')
    marathons = sum(1 for r in results if r.get("marathon"))
    if marathons:
        print(f'  of which {marathons} have no engine-enforced win condition '
              f'(no aux.BeginPuzzle)')

    forced = sum(r.get("reasked", 0) for r in results)
    asked = sum(r.get("asked", 0) for r in results)
    truncated = sum(r.get("truncated", 0) for r in results)
    if asked:
        print(f"\n  model decisions {asked}")
        print(f"  cut off mid-reasoning {truncated}  (retried with a budget)")
        # This is the number that invalidates a run. Option 0 is arbitrary,
        # so a run full of forced defaults measures the fallback, not the
        # model - and it looks exactly like an agent playing badly.
        print(f"  re-asked for a bare number {forced}")
        blind = sum(r.get("no_plan", 0) for r in results)
        unchecked = sum(r.get("unchecked_plans", 0) for r in results)
        if blind:
            print(f"  turns played with NO plan {blind}   <- planning failed")
        if unchecked:
            print(f"  plans with no damage total {unchecked}  (nothing to check)")
        steps = sum(r.get("plan_steps", 0) for r in results)
        if steps:
            done = sum(r.get("plan_done", 0) for r in results)
            skipped = sum(r.get("skipped_ahead", 0) for r in results)
            print(f"  plan steps carried out {done}/{steps}")
            print(f"  taken out of order {skipped}"
                  f"{'   <- the sequencing failure' if skipped else ''}")

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
