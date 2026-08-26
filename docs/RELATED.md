# Related work, and where this differs

Written 2026-08-25. The comparison matters because one of these projects is
building the same thing on the same engine, and `docs/PLAN.md` claimed for
months that nobody was.

## YGO-Bench — the same idea, independently

[erwinmsmith/YGO-Bench](https://github.com/erwinmsmith/YGO-Bench) vendors
**ocgcore with CardScripts and BabelCDB** - the same engine and the same
pinned card data as this project. It runs puzzles *and* full duels, ships
passive / random / ReAct agents, and reports solve rate, swap-side win rate,
Glicko-2 and illegal-action rate. Early (5 commits, no paper, no leaderboard),
but it exists.

This retires the plan's original novelty claim, which named ygo-agent as the
only serious attempt. The remaining honest claim is narrower and still worth
making: **regret against engine-computed achievable value** as the primary
metric, and interruption schedules as a controlled variable. Neither appears
in YGO-Bench's metric list.

## How each harness talks to its model

| | **ygo-harness (this)** | **YGO-Bench** | **Claude Plays Pokémon** | **Continual Harness** |
|---|---|---|---|---|
| Engine | ocgcore, pinned | ocgcore, pinned | mGBA + RAM dump | mGBA / PyBoy |
| Model acts by | replying with an **index** | **tool call** per decision type | **tool calls** (buttons, navigator) | tools registry |
| Card knowledge | whole corpus in cached system prompt | **`inspect_card` tool**, on demand (≤8/decision) | screenshot + RAM | game state |
| Calls per decision | **1** (0 when one option) | 1–11 | 1 | 1 + periodic refiner |
| Loop within a decision | none | messages accumulate | n/a | n/a |
| Across decisions | plan + engine events + action log | none | **summary every ~30 actions** | trajectory window |
| Across episodes | none | none | **knowledge base the model edits** | **memory persists** |
| Planning | plan/turn, damage checked against engine LP | "N-attempt plans" | emergent | skills as code |
| Model routing | **two roles, planner/executor** | one | one | one |
| Self-modifying | no | no | knowledge content only | **`evolve_harness`** |
| On bad output | retry, then abort as `invalid` | forced retry | — | — |

## Three choices here that are deliberate

**Whole card corpus in the cached prompt, not an `inspect_card` tool.**
Measured at ~3,900 tokens for the Sky Striker corpus and 1,500–8,400 for
puzzles. YGO-Bench pays up to 8 extra round trips per decision to fetch the
same text. Ours is cheaper and complete at these pool sizes; theirs is what
scales to a 13k-card pool. If the card pool ever becomes the whole database,
this trade flips.

**No self-modifying scaffolding.** `docs/PLAN.md` cites
[Continual Harness](https://arxiv.org/html/2605.09998) and reaches the
opposite conclusion on purpose: fix the harness across all models, never tune
per model, and *ablate* it. Self-modification makes a result un-attributable
to either the model or the harness.

**No retracing, ever.** See `DECISIONS.md`, "The agent never retraces".
Search-as-executor would make plan adherence redundant, and is stronger - but
rolling back means undoing an opponent's negations, which is not a thing you
can ask a person for, and does not work over a network at all. Search stays
as an offline referee.

## The one gap worth acknowledging

We ask for a number and parse it. That is why `NoAnswer`, the re-ask path and
truncation handling exist at all. YGO-Bench uses tool calling, where a
malformed answer is a schema error rather than a parsing problem - though it
still needs forced retries, so structured output would shrink that class
rather than remove it. Not currently planned; recorded so it is not
rediscovered as a novel idea.
