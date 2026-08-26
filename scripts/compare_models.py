#!/usr/bin/env python3
"""Run the same puzzles against several models, in parallel, and tabulate.

    python scripts/compare_models.py --filter Home_of_the_Fiends
    python scripts/compare_models.py --models qwen/qwen3.7-flash,google/gemini-3.7-flash \
        --filter Seto_VS_Ishizu --transcript

Runs are independent processes against different providers, so they fan out.
Doing this sequentially was costing twenty minutes for what takes five, and
the only thing that ever forced serialisation was a bug: `--transcript` names
its file after the *puzzle*, so a fan-out had every model writing to the same
path. Each model gets its own transcript directory here, which removes the
reason to serialise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_MODELS = [
    "qwen/qwen3.7-flash",
    "google/gemini-3.7-flash",
    "anthropic/claude-haiku-4.5",
]

#: Per 1M tokens, OpenRouter, checked 2026-08-25. Drifts - see
#: docs/EXPERIMENTS.md. Unknown models are reported without a cost.
PRICES = {
    "qwen/qwen3.7-flash": (0.030, 0.130),
    "google/gemini-3.7-flash": (0.375, 1.875),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "anthropic/claude-sonnet-5": (2.00, 10.00),
    "openai/gpt-5.2": (1.75, 14.00),
    "mistralai/mistral-nemo": (0.019, 0.030),
}


def slug(model: str) -> str:
    return model.replace("/", "_").replace(".", "_")


def run_one(model: str, args, out: Path) -> tuple[str, dict | None, str]:
    cmd = [sys.executable, "scripts/run_puzzles.py", "--agent", "llm",
           "--model", model, "--json", str(out / f"{slug(model)}.json")]
    if args.filter:
        cmd += ["--filter", args.filter]
    if args.rule is not None:
        cmd += ["--rule", str(args.rule)]
    if args.hardest:
        cmd += ["--hardest", str(args.hardest)]
    if args.transcript:
        # One directory per model. Sharing one is what made a fan-out unsafe.
        d = out / slug(model) / "transcripts"
        d.mkdir(parents=True, exist_ok=True)
        cmd += ["--transcript", str(d)]
    log = out / f"{slug(model)}.log"
    with log.open("w") as fh:
        rc = subprocess.call(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT)
    path = out / f"{slug(model)}.json"
    if not path.exists():
        return model, None, f"no results (exit {rc}) - see {log}"
    return model, json.load(path.open()), ""


def cost_of(model: str, r: dict) -> float | None:
    if model not in PRICES:
        return None
    pin, pout = PRICES[model]
    tin = sum(r.get(f"{x}_in", 0) for x in ("planner", "executor"))
    tc = sum(r.get(f"{x}_cached", 0) for x in ("planner", "executor"))
    tw = sum(r.get(f"{x}_write", 0) for x in ("planner", "executor"))
    to = sum(r.get(f"{x}_out", 0) for x in ("planner", "executor"))
    return (max(tin - tc - tw, 0) / 1e6 * pin + tw / 1e6 * pin * 1.25
            + tc / 1e6 * pin * 0.1 + to / 1e6 * pout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--filter", default=None)
    ap.add_argument("--rule", type=int, default=5)
    ap.add_argument("--hardest", type=int, default=None)
    ap.add_argument("--transcript", action="store_true")
    ap.add_argument("--jobs", type=int, default=0,
                    help="concurrent runs (default: all of them)")
    ap.add_argument("--out", default="runs/compare")
    a = ap.parse_args()

    models = [m.strip() for m in a.models.split(",") if m.strip()]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = a.jobs or len(models)

    print(f"{len(models)} models, {jobs} at a time -> {out}\n")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda m: run_one(m, a, out), models))

    print(f"{'model':<30} {'solved':>7} {'clean':>6} {'secs':>6} {'out tok':>9} {'cost':>9}")
    for model, data, err in results:
        if data is None:
            print(f"{model:<30} {'-':>7} {'-':>6}   {err}")
            continue
        rs = data["results"]
        solved = sum(1 for r in rs if r["outcome"] == "solved")
        clean = sum(1 for r in rs if r["outcome"] in ("solved", "unsolved"))
        secs = sum(r.get("seconds", 0) for r in rs)
        tok = sum(sum(r.get(f"{x}_out", 0) for x in ("planner", "executor")) for r in rs)
        costs = [cost_of(model, r) for r in rs]
        total = sum(c for c in costs if c is not None) if all(
            c is not None for c in costs) else None
        print(f"{model:<30} {solved:>3}/{len(rs):<3} {clean:>3}/{len(rs):<2} "
              f"{secs:>6.0f} {tok:>9,} "
              + (f"${total:>8.4f}" if total is not None else f"{'?':>9}"))
    print(f"\nRecord anything worth keeping in docs/EXPERIMENTS.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
