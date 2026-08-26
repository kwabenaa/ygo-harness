# How the agent actually works

Written 2026-08-25, because the question "is this ReAct? LangGraph?" had no
answer anywhere in the repo.

## It is a policy callable, not a framework

No agent framework. No LangChain, no LangGraph, no ReAct loop.

```
ocgcore emits MSG_SELECT_*  ->  policy(msg, duel) -> response bytes  ->  ocgcore
```

`Duel.run(policy)` drives everything. The engine decides when the agent is
asked and what the legal answers are; the policy returns an index into a menu
the engine built. An illegal move has no channel through which it could be
expressed — that is the project's founding bet, and it is why there is no
"illegal action rate" metric here.

**Not ReAct.** ReAct interleaves thought / action / observation in one growing
context with tools the model chooses to call. Here the model never chooses
when to act, never calls a tool, and context does not accumulate.

**Should it use a framework?** No, and deliberately. The control flow belongs
to ocgcore — a framework would wrap a loop we do not own, and this repo's
reproducibility story is pinned commit hashes and explicit dependencies. The
pattern worth naming is **plan-and-execute**; the library is not.

## Each decision is stateless, and that is on purpose

Every call is `[stable system prompt][one volatile user message]`. Nothing
accumulates. Two reasons:

- **Caching.** A prefix cache is a prefix match, and a system prompt identical
  on every call is the ideal shape. A growing conversation is ~4x more
  expensive per call even with perfect caching, because cache reads are ~10%
  of input price and not free.
- **Signal.** Reasoning traces run 3-30k characters and were measured to be
  roughly half self-correction ("wait, actually, no"). Replaying fifteen of
  those feeds superseded deliberation forward. Stale boards are worse — the
  field changes every action.

State is carried *curated* instead of raw:

| what | where | scope |
|---|---|---|
| intent | the plan | one turn |
| progress through the plan | `PlanTracker` | one turn |
| what the engine did | `llm/events.py` | since last decision |
| what the agent did | `history` | last 60 |

## The pieces

**Planner / executor split** (`agents/deliberation.py`). Two provider objects,
chosen per decision. The planner fires on turn start, on an opponent's
interruption, on interrupt windows, on menus offering an activation, and on
menus at least six options wide. Everything else is execution. All the
triggers read the *menu*, never the model's answer, so the rule can be
measured for free on random duels — `scripts/deliberation_report.py`.

**The plan** (`llm/prompt.py`, `plan_prompt`). One call per turn produces a
numbered line to lethal, naming the cards each step touches. It is checked
against the opponent's life total from the engine before use; a plan that
cannot reach lethal is re-planned once.

**The tracker** (`agents/plan_tracker.py`). Parses the plan into ordered
steps, matches them against the live menu, and *carries out* a step when
exactly one option matches — zero model calls. Ambiguity, interrupts and
unnamed sub-decisions escalate to the model. A step whose card the menu cannot
offer marks the plan dead and triggers a rebuild.

**No retracing.** See `DECISIONS.md`. The agent commits to every action.
Rolling back would mean undoing an opponent's negations, which is not
something you can ask a person for and does not work over a network at all.
Search remains available as an *offline referee*, never as the player.

## The failure taxonomy

These are different facts and the runner never merges them:

| outcome | means | whose fault |
|---|---|---|
| `solved` / `unsolved` | the duel reached a verdict | the agent |
| `error` / `stalled` | the harness raised or looped | **ours** |
| `invalid` | the model never produced a usable answer | neither — no data |
| `skipped` | out of scope (Rush Duel, unknown flags) | n/a |

`invalid` exists because the alternative — picking option 0 — is not neutral.
In a chain window option 0 is *activate*. One such fallback auto-activated
Raigeki Break, destroyed the agent's own only monster, made the puzzle
unwinnable, and the run reported `unsolved` as though the agent had played it
out and lost.

**Read the "ran clean" number, not the solved count.** A puzzle the agent
loses is a puzzle the agent lost; a puzzle that raises is a bug in `engine/`.
