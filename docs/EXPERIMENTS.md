# Experiments

Running log of what has actually been measured. Newest first.

Rules for this file, so it stays worth reading:

- **Record the conditions, not just the number.** A solve rate without the
  model, the puzzle and the harness commit is not a result.
- **Record failures and dead ends too.** Most of the entries below are things
  that did not work, and they are the reason the next person does not retry
  them.
- **Say the sample size.** Almost everything here is n=1. Say so, and do not
  write conclusions a single run cannot support.

---

## Model comparison on Master Rule 5 puzzles (2026-08-25)

Three models, both roles on one model per run, thinking left at each model's
default. `scripts/run_puzzles.py --model <id> --filter <puzzle>`.

### Home of the Fiends (2/10) — one run each, sequential

| model | result | secs | decisions | plan | re-plans | out tok | cost |
|---|---|---|---|---|---|---|---|
| `google/gemini-3.7-flash` | **solved** | 254 | 17 | 5/7 | 2 | 35,818 | $0.085 |
| `anthropic/claude-haiku-4.5` | unsolved | 144 | 13 | 4/22 | 0 | 13,776 | $0.138 |
| `qwen/qwen3.7-flash` | unsolved | 532 | 12 | 3/5 | 2 | 112,617 | $0.015 |

### Seto VS Ishizu (4/10) — one run each, before the deck/menu fixes

| model | result | secs | decisions | plan | re-plans | out tok | cost |
|---|---|---|---|---|---|---|---|
| `anthropic/claude-haiku-4.5` | unsolved | 199 | 25 | 3/8 | 2 | 18,482 | $0.208 |
| `google/gemini-3.7-flash` | unsolved | 359 | 38 | 7/8 | 2 | 31,510 | $0.109 |
| `qwen/qwen3.7-flash` | unsolved | 768 | 16 | 3/4 | 2 | 154,092 | $0.021 |

**What these support, and what they do not.** n=1 per cell, and run-to-run
variance is known to be large - qwen solved Home of the Fiends earlier the
same day under a bounded reasoning budget and failed it here. So:

- Supported: gemini produced a solve on the first attempt where the others did
  not; qwen is 5-10x cheaper than either; nothing solved Seto.
- **Not** supported: any ranking of these models by capability. Three runs are
  three anecdotes.

**Cost is not capability.** qwen wins cost by an order of magnitude and is the
only one that caches at these prompt sizes, but it also generated 3-8x more
output than the others and lost both puzzles. Choosing it is a cost decision,
and should be written down as one.

---

## Prompt caching by model (2026-08-25)

Two identical calls through OpenRouter, checking `cache_write_tokens` and
`cached_tokens`. **The harness sends an Anthropic-style `cache_control`
breakpoint on the system prompt** (`Provider.cache_system`); without it
nothing is written to cache at all.

| model | ~1.5k tok | ~3k | ~5k | ~9.9k |
|---|---|---|---|---|
| `qwen/qwen3.7-flash` | caches | caches | caches | caches |
| `google/gemini-3.7-flash` | no | no | no | no |
| `anthropic/claude-haiku-4.5` | no | no | no | caches |

Measured economics on a 9,926-token system prompt:

| | first call | second call |
|---|---|---|
| haiku | $0.012429 (write) | **$0.001030** (read) |
| qwen | $0.000335 (write) | **$0.0000291** (read) |

**Consequence for reading any cost number here.** Puzzle system prompts are
small - Home of the Fiends builds 1,497 tokens, Seto 2,330 - so gemini and
haiku costs in this file are entirely uncached and will stay that way until
the card corpus is much larger. The Sky Striker duel corpus (~3,900 tokens)
is the case where this starts to matter.

---

## Provider prices, OpenRouter, 2026-08-25

Fetched live from `/api/v1/models`, per 1M tokens. These drift; refetch rather
than trusting this table.

| model | in | out |
|---|---|---|
| `mistralai/mistral-nemo` | $0.019 | $0.030 |
| `qwen/qwen3.7-flash` | $0.030 | $0.130 |
| `google/gemini-3.7-flash` | $0.375 | $1.875 |
| `anthropic/claude-haiku-4.5` | $1.00 | $5.00 |
| `anthropic/claude-sonnet-5` | $2.00 | $10.00 |
| `openai/gpt-5.2` | $1.75 | $14.00 |
| `anthropic/claude-opus-5` | $5.00 | $25.00 |

Output dominates: a puzzle runs roughly 25k in / 30k out, so the output rate
is what decides cost.

---

## Things tried that did not work

**Unbounded planner reasoning made qwen worse.** Removing the 256-token budget
was meant to help it find multi-step lines. It produced 112k-154k output
tokens per puzzle, ran 2-3x longer, and lost a puzzle it had previously
solved. More thinking was not better.

**Routing every decision to the planner cost 14 minutes a puzzle** and did not
change the plan, which is where the reasoning actually happens. Reverted to
the hierarchical split; a puzzle now runs 2-5 minutes.

**A rules primer was argued against on the strength of a bad scan.** A scan of
368k characters of reasoning classified the model's mechanics claims as
correct and concluded rules knowledge was not the gap. It sampled claims and
never checked *turn structure*, which was exactly what was broken - the agent
planned an attack from Main Phase 2. The primer helped. Sampling a category
you did not think to look for proves nothing about it.
