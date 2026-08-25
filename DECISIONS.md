# Decisions and deferrals

Running record of choices that would otherwise be re-litigated, and of work
deliberately put off. Newest first.

---

## Deferred: WindBot as an opponent

**Status:** not in v1. Revisit after M2.

[WindBot](https://github.com/IceYGO/windbot) is the community's rule-based bot:
C#, per-deck `Executor` classes, speaks the YGOPro network protocol over TCP.
It never links the core.

It was going to be the fixed-skill baseline. Dropped for now because a baseline
is only useful once there is an agent worth measuring, and the human-vs-agent
test covers the same ground earlier and more cheaply.

When it comes back, there are two options and they are not equivalent:

- **Real WindBot over a local server.** True external baseline, no
  reimplementation risk. Costs a network transport (see below).
- **A Python rule-based opponent in-process**, informed by WindBot's Sky
  Striker executor. Cheaper, works with everything, but it is our
  interpretation of the baseline rather than the baseline.

---

## No rollback at play time

**Status:** decided.

The agent commits to its actions. It does not explore and undo during a duel.

This was previously muddled with search, so, precisely:

| | Runs | Needs rollback | Works over a network |
|---|---|---|---|
| Search as **referee** (computes `V*` for the regret metric) | Offline, after the duel | Yes, offline | **Yes** |
| Search as **agent** (plays stronger by exploring branches) | Online, mid-duel | Yes, during play | No |

Only search-as-agent needs rollback while playing, and that is M3+. The referee
replays a recorded `(seed, response log)` in a fresh in-process duel after the
fact, so duels played over a network - against WindBot, or against a human in
EDOPro - can still be scored by search afterwards.

**Consequence:** keep recording `(seed, response log)` for every duel
regardless. Not for rollback - it is what makes replay, offline scoring, and
`.yrp` export possible, and it is nearly free.

---

## Deferred: YGOPro network transport

**Status:** not in v1. Required by both WindBot-as-opponent and
human-vs-agent-in-EDOPro.

Everything in this ecosystem is a network client - EDOPro, WindBot, Neos. To
play against any of them live, the agent has to speak the YGOPro protocol
rather than drive the core in-process.

Cost is real but bounded: the *duel* half of that protocol is the `MSG_*`
stream we already decode. What is missing is the lobby half - handshake, deck
exchange, player slots, rematch. Estimate one to two days, not an afternoon.

Do not start this before there is an agent worth playing against.

---

## Win rate is not a skill signal without turn-order control

**Status:** empirical, measured at M0.

40/40 random-vs-random duels were won by player 0. Not a bug: random play
almost never deals lethal, so games become deck-out races, and the player going
second draws one extra card over the game and decks out first. The result is
deterministic and has nothing to do with play quality.

**Consequence:** every win-rate number this project reports must be split by
going first vs. going second. It is also direct evidence for the plan's
argument that regret-against-achievable-value is the better primary metric -
"did you win" is a weak signal in this game.
