# Decisions and deferrals

Running record of choices that would otherwise be re-litigated, and of work
deliberately put off. Newest first.

---

## .yrp export works in EDOPro

**Status:** closed. Two format bugs found and fixed; confirmed in the client.

The previous entry said the bytes round-tripped through our own parser and
that this proved self-consistency, not compatibility. That was right, and the
gap was real: the file **did not open**. Two fields were missing, both of them
required only because we set `REPLAY_NEWREPLAY`, and both silent:

- `Replay::ParseNames` reads a `uint32` player count per side *before* the
  names. Without it the client read the first four bytes of `"Player 1"` as a
  count of seven million players.
- `Replay::ParseDecks` reads a `uint32` custom-rule-card count immediately
  after the decks. Without it the client ate the first response byte as part
  of that count.

Neither could ever fail a round-trip test, because our reader agreed with our
writer about omitting them. The guard that does catch them is
`test_body_layout_matches_client_reading_order`, which pins byte offsets
transcribed from the client rather than from us.

The other suspects listed in the old entry turned out to be fine, and EDOPro's
own `replay/_LastReplay.yrp` settles them: it writes `hash` and `datasize` as
0, so neither is checked; its `version` is `0x000b0029`, which is exactly the
value we now compute (client 41.0, core 11.0); and its flag set is ours plus
`REPLAY_SINGLE_MODE`. `ParseReplayHeader` checks only `header_version <= 1`.

**How it is verified now.** `scripts/verify_yrp.py` replays a `.yrp` through
the EDOPro install's *own* core, card databases and Lua scripts, following
`ReplayMode::StartDuel`. This is not a stand-in for the client - it is the
client's code path, minus rendering. A duel of 917 responses reproduces in
2212 engine steps with the same winner, identical to our own engine.
`tests/test_yrp_edopro.py` keeps it, skipping when EDOPro is not installed.

Confirmed in the GUI on 2026-08-24: an exported duel opens from EDOPro's
replay menu and plays back with card art and animation. Reviewing a duel the
agent played is now a thing that happens by watching it, which was the whole
argument for doing M1.5 before anything prettier.

---

## A replay is only as portable as the card scripts it was played with

**Status:** empirical, found while verifying the export.

EDOPro does not store a picture of a duel. It re-creates one from the seed and
feeds the responses back into its own core, so a response is only legal if the
client's engine offers the same menu ours did. Card scripts move, and when they
move the menu changes.

Measured, not theorised: against EDOPro 41.0.2 as shipped, our replay desynced
at response 18 of 917 - `MSG_SELECT_IDLECMD`, turn 2. The installer's April
2025 script snapshot was **missing eight of the deck's cards outright** and
differed on six more. EDOPro clones `ProjectIgnis/DeltaBagooska` over that
snapshot on first launch; against the updated scripts the same file replays
clean. So the failure was never in the file.

**Consequences:**

- A `.yrp` we publish is only replayable by a client whose scripts cover the
  cards played. "It desynced" is not evidence the export is broken - check the
  data versions first, which is what `--engine ours` exists for.
- Read EDOPro's data the way EDOPro does: prefer
  `repositories/delta-bagooska/{script,bin,*.delta.cdb}` over the bundled
  `script/`, `libocgcore.dylib` and `expansions/`. The bundled copies are the
  installer's snapshot and are stale the moment the client first runs.
- `data/DATA_COMMITS` pins babelcdb at `d1cf9e0a`, which is what
  `repositories/delta-bagooska/VERSION` reports today. That agreement is
  luck, not machinery. Nothing enforces it.

---

## Deferred: WindBot as an opponent

**Status:** not in v1. Revisit after M2.

[WindBot](https://github.com/IceYGO/windbot) is the community's rule-based bot:
C#, per-deck `Executor` classes, speaks the YGOPro network protocol over TCP.
It never links the core.

Worth knowing when this comes back: installing EDOPro drops a WindBot build at
`~/Applications/ProjectIgnis/WindBot`, so the "real WindBot over a local
server" option no longer starts with a C# build.

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
