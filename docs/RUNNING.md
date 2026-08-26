# Running things

## Free, no tokens

```bash
python scripts/run_puzzles.py                 # random-legal over the whole pool
python scripts/coverage_report.py             # what the engine can report vs what we use
python scripts/deliberation_report.py -n 12   # planner/executor routing rules
```

Read the **"ran clean"** line, not the solved count. Random play solving
nothing is expected; random play *crashing* is a bug in `engine/`.

## With a model

```bash
set -a; . ./.env; set +a
python scripts/run_puzzles.py --rule 5 --agent llm --filter Home_of_the_Fiends
```

Useful flags:

| flag | what |
|---|---|
| `--model ID` | override **both** roles with one model |
| `--filter NAME` | substring match on the puzzle filename |
| `--hardest N` | the N hardest by the author's declared complexity |
| `--rule N` | only puzzles declaring that Master Rule |
| `--transcript DIR` | write the full conversation per puzzle |
| `--json FILE` | machine-readable results, including per-role tokens |
| `-v` | print each decision as it happens |

**Iterate on one puzzle, not the set.** A full Master Rule 5 run is twenty
puzzles and half an hour, and answers a question one puzzle already answers.
Run the set only to confirm an additional solve.

## Watching a run

Terminal output goes to whoever ran the command. To read a run afterwards:

```bash
python scripts/transcript_html.py runs/puzzles/<name>.txt -o out.html
```

That renders the system prompt, the plan, and every decision with the board,
the menu, the choice and the reasoning behind a disclosure. It is the fastest
way to see what the agent was actually shown — which has been the cause of
five separate "the model reasoned badly" findings.

## Comparing models

`--model` overrides **both** roles on purpose. Two families cannot share a
prompt cache, so changing only the planner would also change cache behaviour
underneath the comparison.

**Run comparisons in parallel** — the runs are independent processes and six
concurrent is nothing:

```bash
for m in qwen/qwen3.7-flash google/gemini-3.7-flash anthropic/claude-haiku-4.5; do
  tag=$(echo "$m" | tr '/.' '__')
  python scripts/run_puzzles.py --rule 5 --agent llm --model "$m" \
    --filter Home_of_the_Fiends --json "out/$tag.json" &
done; wait
```

**But not with `--transcript`.** The transcript filename comes from the
*puzzle*, not the model, so a fan-out has every run writing to
`runs/puzzles/<puzzle>.txt` and clobbering the others. Either run sequentially
when you want transcripts, or give each model its own `--transcript` directory.

Record what you find in `docs/EXPERIMENTS.md`, with the conditions and the
sample size.

## Things that will bite

**Spend limits.** OpenRouter keys carry a per-key cap. A spent key returns 403
on every call; the harness now stops immediately and says so rather than
retrying. Check with:

```bash
curl -s -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  https://openrouter.ai/api/v1/key
```

**`max_tokens` is the real limiter on reasoning models**, not the reasoning
setting — see `docs/EXPERIMENTS.md`. Too low and the model is cut off
mid-thought and returns *empty content*, which reads as a bad answer rather
than a truncated one. `stats.truncated` counts it.

**Backgrounded runs and their watchers.** A puzzle takes 2-13 minutes, past
most command timeouts. Launch detached, and write the watcher's exit condition
against *the artefact you want* (the JSON appearing), never against "the
driver process is gone" — killing the driver yourself then reads as success.
