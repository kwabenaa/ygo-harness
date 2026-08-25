# ygo-harness — an LLM agent + benchmark for Yu-Gi-Oh

> **Status: M0 complete, M1 mostly complete.** The engine builds on Apple
> Silicon, duels run end to end, determinism is proven, and a two-model
> hierarchical LLM agent plays real Sky Striker lines. See "Progress" at the
> end for what changed versus the original plan — several cost assumptions
> turned out wrong by an order of magnitude.

## Context

Yu-Gi-Oh is the hardest mainstream TCG nobody has pointed an LLM at. Pokémon TCG has
[PTCG-Bench](https://arxiv.org/html/2605.29653v1), Magic has [UrzaGPT](https://arxiv.org/pdf/2508.08382)
and a [causal-RL gym](https://arxiv.org/html/2605.06066v1). Yu-Gi-Oh has exactly one serious AI
attempt — [ygo-agent](https://github.com/sbl1996/ygo-agent), pure RL — which cost **32× RTX 4090 for
5 days / 100M games**, covers ~9k cards on a narrow deck set, has been dormant since July 2024, and
produces a policy that cannot explain a single decision.

The opening is that Yu-Gi-Oh's difficulty is *structurally different* from the games already
benchmarked, in a way that plays to an LLM harness rather than against it:

- **The engine hands you a legal-action menu at every decision point.** Illegal moves are
  impossible by construction. No screen reading, no action validation, no error recovery. All the
  difficulty is planning under interruption — the part that's actually interesting.
- **Play is deeply interactive.** Every action opens a response window; the opponent may interrupt;
  each interruption forces a re-plan with degraded resources.
- **PTCG-Bench's stated failure is that long-horizon card games give no dense or verifiable signal**,
  so self-improvement methods can't do credit assignment. Yu-Gi-Oh can be made to yield one — see
  "Regret, not accuracy."

Two goals, ranked: a **public research artifact** and an **agent that actually plays well**. These
share ~80% of the build and diverge on one axis — overfitting is a virtue for the agent and a sin
for the benchmark. Resolved structurally: one repo, `agents/` is a free-for-all, `bench/` holds a
protocol and eval splits sealed on day one.

Build order is **agent-first**: building to win reveals which metrics matter. Benchmark-first means
guessing at metrics and usually shipping an eval nobody can move.

**Platform: macOS (M3 MacBook Air, 16GB) only for v1.** Single dev machine, portable. The Linux/AMD
box is out of scope — no local GPU inference, no headless self-play farm. Everything runs through
OpenRouter, with a local-model path available but not required.

---

## The corrected thesis: Yu-Gi-Oh is not solitaire

An earlier draft assumed combo lines have canonical correct sequences and that the benchmark could
score line-matching. That is wrong, and the correction drives most of the design below.

Real play is a **conditional policy, not a script**. You commit an action, the engine resolves it,
the engine tells you whether the opponent chained, and only then do you choose again — possibly
having to spend resources answering the interruption, possibly rerouting, possibly ending with
nothing. Good players don't hold a 25-step sequence in their head. They hold a small library of
**target board states**, plan only to **the next commitment point**, and **re-plan on every response
window**.

Three consequences:

**Regret, not accuracy.** There is no canonical answer to diff against, so ground truth must be
*computed*, not authored. For a given (hand, interruption schedule), engine-backed search gives the
best achievable value `V*`; the agent scores `V`; the metric is **regret = V* − V**. This handles
"you got Ashed, so a weaker board was correct" natively. **The search is therefore the referee, not
just a stronger agent** — which is a much better justification for building it.

**Interruption schedules are a controlled variable, not noise.** A test case is
`(deck, seed, opponent_hand, interrupt_policy)`. Fixing "opponent holds Ash + Droll, fires Ash at
the first Engage" makes a case deterministic, reproducible, *and* genuinely interactive — the middle
ground between goldfishing and a full adversarial opponent. This is the core benchmark unit.

**The agent must be hierarchical.** Nobody plans 20 moves ahead, and an agent that tries will
hallucinate ocgcore's ruling minutiae.

---

## Why the common skepticism targets a different architecture

The standard objection — voiced on r/yugioh and elsewhere — is that an LLM will hallucinate rulings
and fabricate card interactions. [Can Large Language Models Master Complex Card
Games?](https://arxiv.org/pdf/2509.01328) (Dou Dizhu, Mahjong; LoRA + in-context learning + RL)
makes that concrete, reporting four failure modes. Three of them are design-excluded here:

| Reported failure mode | Status in this design |
|---|---|
| **Rule violations, invalid moves** | **Impossible.** The engine emits a legal-action menu; the agent returns an index. There is no channel through which an illegal move can be expressed. |
| **Hallucinated card interactions / fabricated state** | **Delegated to the engine.** With search, the LLM never predicts what an interaction does — it proposes a branch, ocgcore executes it and reports ground truth. This is the strongest argument for search-as-referee. |
| **Large discrete action-space mishandling** | **Bounded.** The choice is an index into a menu of ~5–25 options, not a selection over 13k cards. The hierarchical split further narrows it. |
| **Hidden information** | **Real and unfixed.** Named as a genuine limitation. Sky Striker leans into it — Triple Tactics Talent is a pure read on the opponent. |

The skeptics are right about the architecture they're imagining: an LLM that reads card text and
emits moves as free text will fail exactly this way. That is not this. Being able to state this
crisply, with a citation, is worth putting in the README — it is the clearest framing of what an
engine-native harness buys you.

The paper's other finding is a warning shot for later: fine-tuning on games caused **catastrophic
forgetting** of general capability, mitigated only partially by LoRA plus mixed game/general
training data. It is an argument for staying prompt-and-search-based in v1 — which the budget
already dictates — and a constraint on any future distillation of verified traces.

---

## v1 deck: Sky Striker — and what that changes

Target list: `el`'s 2nd-place Sky Striker from [Pulp Squeeze #6](https://www.masterduelmeta.com/top-decks/community-tournaments/pulp-squeeze/6/sky-striker/el/fBYJH),
23 Aug 2026. **Verified: 40 main / 15 extra, both legal.**

```
MAIN (40)
1  Maxx "C"                      3  Sky Striker Mobilize - Engage!
3  Ash Blossom & Joyous Spring   1  Triple Tactics Talent
1  Ghost Belle & Haunted Mansion 2  Sky Striker Special Maneuver - Lemnisgate!
3  Sky Striker Ace - Raye        1  Mystical Space Typhoon
2  Sky Striker Ace - Roze        1  Called by the Grave
1  Gameciel, the Sea Turtle Kaiju 1 Sky Striker Mecha - Hornet Drones
1  Reinforcement of the Army     1  Sky Striker Mecha - Shark Cannon
1  Pot of Desires                3  Sky Striker Mecha - Widow Anchor
1  Sky Striker Maneuver - Afterburners!  2  Forbidden Droplet
3  Sky Striker Mobilize - Linkage!       2  Radiant Typhoon Vision
3  The Fallen & The Virtuous     1  Forbidden Crown
1  Infinite Impermanence         1  Solemn Accusation

EXTRA (15)
1 Albion the Branded Dragon      1 Prototype Sky Striker Ace - Amatsu
1 Ecclesia and the Dark Dragon   1 Sky Striker Ace - Zeke
1 Super Starslayer TY-PHON - Sky Crisis  1 Sky Striker Ace - Azalea
2 Sky Striker Ace = Zero         1 S:P Little Knight
3 Sky Striker Ace - Kagari       1 Sky Striker Ace - Camellia
1 Sky Striker Ace - Shizuku      1 Sky Striker Ace - Hayate
```

Note this is a **modern hybrid, not pure Sky Striker**: a Fusion package (Albion, Ecclesia), a
Radiant Typhoon engine, 3× The Fallen & The Virtuous, and Forbidden Droplet / Forbidden Crown. Lines
are still short — the reason for choosing it over Branded — but effect *complexity* is higher than a
classic build, and that lands squarely on M1's decoder surface: Forbidden Droplet's
send-any-number-as-cost is a multi-select, Fusion Summon needs material selection, Triple Tactics
Talent is a mode choice. **Mitigation: stage the bring-up.** Get the harness working on a minimal
Sky Striker core (Raye / Roze / Engage / Kagari / Hornet Drones — a handful of scripts), prove the
loop end to end, then load the full 40. Same destination, much less M1 sprawl.

**Handtrap density is unusually high and this is a feature.** With Maxx "C", 3× Ash, Ghost Belle,
Imperm, Called by the Grave and Solemn Accusation, the agent plays *both* sides of interruption —
it must decide when to spend its own interrupts, not just how to recover from the opponent's. That
doubles the interesting decision class and is directly on-thesis.

The emphasis shift versus Branded, worth naming explicitly:

| | Branded (combo) | **Sky Striker (control)** |
|---|---|---|
| Where the horizon lives | Within one long turn | **Across many short turns** |
| Core skill | Combo execution under interruption | **Resource management** — hold or use Widow Anchor, what to Shark Cannon, spell count in GY, Engage now or later |
| Decisions per duel | ~100+ | **~40–60** |
| What the scorer values | End-board interruption count | **Board + hand + GY resources + card advantage** |

Two of these are strict wins. Short turns make **full duels affordable** — at ~$0.005/decision a
duel is ~$0.25, which means a real multi-model leaderboard on complete games now fits the budget.
That inverts the earlier conclusion that full duels were a luxury. And small Sky Striker boards make
the value function *easier* to write, not harder.

The tradeoff to accept honestly: this is less a test of long-horizon *combo execution* and more a
test of long-horizon *resource management under interaction*. That still lands squarely on
PTCG-Bench's gap — arguably more squarely, since it demands memory and planning **across** turns
rather than within one — but the writeup should frame it as attrition/interaction, not as combo
solving.

The deck is also unusually well-suited to the interaction thesis: Maxx "C" and Droll & Lock Bird are
opponent-turn interrupts, and Triple Tactics Talent is *conditional on the opponent having activated
a monster effect* — a card whose correct use is purely a read on the opponent.

The sealed held-out split should include at least one non-Sky-Striker deck, or there is nothing to
say about generalization.

---

## Architecture

```
ygo-harness/
  engine/        ctypes bindings to edo9300/ygopro-core + MSG_* decoders + text renderer
  llm/           one OpenAI-compatible adapter: OpenRouter | Ollama | LM Studio | llama.cpp
  search/        replay-based state restore, DFS/MCTS over the action tree, value function
  agents/        anything goes: hierarchical LLM agent, search-guided agent, baselines
  bench/         SEALED: eval splits, interrupt schedules, scoring protocol, results/
  viz/           terminal live view + .yrp replay export
  data/          cards.cdb + script/ pinned by commit hash
```

### Engine layer

Link **edo9300/ygopro-core** (EDOPro's fork, modern `OCG_*` C API) in-process via Python ctypes.

- The FFI layer is near-free: `ctypesgen ocgapi.h` generates it, and the API is ~12 functions —
  `OCG_CreateDuel`, `OCG_DuelNewCard`, `OCG_StartDuel`, `OCG_DuelProcess`, `OCG_DuelGetMessage`,
  `OCG_DuelSetResponse`, `OCG_DuelQuery*`. Card data and Lua scripts arrive through your own
  `OCG_DataReader` / `OCG_ScriptReader` callbacks.
- The real work is the **`MSG_*` decoders** (~40 message types matter). **Port these from
  [tspivey/yugioh-game](https://github.com/tspivey/yugioh-game) and ygo-agent rather than reading
  C++ by hand** — it's the only tedious part and it's already been done twice.
- Why the current core rather than forking yugioh-game's existing bindings: **the card pool is not
  baked into bindings** — it comes from `cards.cdb` + `script/`, pulled fresh. The real coupling is
  core-version ↔ script-version, because new cards call new Lua API functions. An old core cannot
  run current scripts. Linking the current core is what buys the current card pool.
- Chain handling is native: `MSG_CHAINING`(70) → `MSG_CHAINED`(71) → `MSG_CHAIN_SOLVING`(72) →
  `MSG_CHAIN_SOLVED`(73) → `MSG_CHAIN_END`(74), with `MSG_SELECT_CHAIN`(16) as your own response
  window. The act → resolve → did-they-respond → re-decide loop is consumed, not built.

**License: ocgcore is AGPL-3.0, so this repo is AGPL-3.0.** Stated up front. The project can never
quietly become a closed product.

### LLM layer — one adapter, three deployments

OpenRouter speaks the OpenAI-compatible API, and so do Ollama, LM Studio, and `llama-server`. So a
single client covers every case; **`base_url` + model string are the only differences.** No
provider-specific branching, no plugin system.

```python
# config/providers.yaml
openrouter: {base_url: "https://openrouter.ai/api/v1",  model: "..."}
local:      {base_url: "http://localhost:11434/v1",     model: "..."}
```

Interface: `propose(state, actions, context) -> action_index + reasoning_trace`. Provider swaps are
a config line.

Two OpenRouter features that are **great for development and poison for benchmark numbers**:
`:floor` (routes to the cheapest provider for a slug) and `openrouter/free` (rotating $0 models).
Both make the serving backend vary run to run, which destroys reproducibility. **Use them freely in
`agents/` and for smoke tests; pin exact provider and model version for anything written to
`bench/results/`.** Getting a free model wired up first is worth doing on day one — debugging prompt
formatting shouldn't cost money.

Model roles: a cheap fast workhorse (Gemini 3.7 Flash or Haiku 4.5 — $1/$5 with a **$0.10 cached-in**
rate, which matters because the prompt is ~90% stable prefix) for the executor layer; a stronger
model for the planner; a free model for CI smoke tests. Kimi K3 ($3/$15, reasoning locked to max, no
cost dial) only as an occasional "does a big reasoner clear the bar?" datapoint.

### State restore — design in from day one

ocgcore has **no documented clone or serialize**. Restore by replaying the action prefix against a
fixed seed. This is proven: a `.yrp` replay file *is* `(decklists, seed, ordered response log)` in
~1KB, which is why replays work at all. A Sky Striker turn is a few hundred engine steps, so
replay-to-node is cheap.

Every duel is `(seed, response log)` from the first commit even though M1 never calls restore.
Retrofitting this later is miserable — and as a bonus it's also the replay-export format.

### Agent layer — hierarchical, split by decision type

| Layer | Fires when | Model | Job |
|---|---|---|---|
| **Planner** | Turn start, and after every opponent interruption | Stronger, thinking on | Choose a target board state and commit only to the next decision point. Few calls per turn. |
| **Executor** | Every other decision point | Cheap / cached | Advance toward the target. Many decisions are near-forced. |
| **Interrupt handler** | `MSG_CHAINING` from opponent, or own `MSG_SELECT_CHAIN` | Stronger | Answer the interruption or not; is the target still reachable? Re-plan trigger. |
| **Cross-turn memory** | Turn boundaries | — | Sky Striker specific and load-bearing: spell count in GY, what's been Shark Cannon'd, what the opponent has shown. |

That last row exists because Sky Striker's horizon is across turns. It's the piece PTCG-Bench found
that generic memory scaffolds handle badly, so it's also where the interesting negative results live.

### Search layer

Engine-backed DFS/MCTS with the LLM as a **policy prior over branches** — the LLM never predicts
mechanics, only ranks which branches look promising; the engine executes speculatively and reports
ground truth; roll back and try another. An LLM with a real simulator and an undo button is
categorically stronger than one without, because mental simulation of ocgcore's rulings is the
binding constraint.

Honest novelty claim: LLM-guided MCTS is well-trodden ([MC-DML](https://arxiv.org/abs/2504.16855),
PAC-MCTS, DeepSearch). What is undone is a domain with *all three* of enormous branching factor, an
exact rules oracle, and computable achievable-value ground truth. **Novel application, not novel
method** — the writeup should say so.

---

## Watching it play

Three tiers, in build order:

1. **Terminal live view (M1).** The `MSG_*` stream is already being decoded into structured state,
   so a Rich/Textual TUI showing board + legal-action menu + the agent's reasoning side-by-side is a
   thin view layer. This is the "watch it think" experience, and it doubles as the debugging tool.
2. **`.yrp` replay export (M2) — highest value per unit effort by a wide margin.** The
   `(seed, response log)` already stored for state restore *is* a replay file; write the header and
   serialize. **Every duel then opens in the real EDOPro client with real card art and full
   animation, for essentially zero rendering work.** Verify round-tripping against
   [ygopro-replay-inflate](https://github.com/ghlin/ygopro-replay-inflate). Post-hoc rather than
   live, but full fidelity.
3. **Web board view (optional, later).** FastAPI + websocket → browser, rendering from the same
   decoded state, card images from YGOPRODeck's CDN. Live *and* graphical, but it is a real UI
   project — only worth it if the terminal view plus replays prove insufficient.

**Deliberately not doing: agent-as-network-client into a live EDOPro server.** It's how WindBot
works and it would give live GUI for free, but you cannot roll back a remote server, so it breaks
state restore and kills the search layer. Worth adding later as a "play against it yourself" mode —
never as the research loop.

---

## Milestones

**M0 — Engine spike.** *The only milestone that can kill the project.* Build `libocgcore` on Apple
Silicon. Generate ctypes bindings. Drive one scripted duel end to end from Python. Prove
determinism: same seed + same response log → byte-identical message stream. **Resolve here:** does
the core build cleanly on macOS/arm64; does replay-based restore reproduce state faithfully; how
fast is replay-to-node.

**M1 — Harness, text rendering, terminal view.** `MSG_*` decoders, compact board renderer,
action-menu formatter, card-text lookup tool, `.ydk` loading. OpenAI-compatible LLM adapter wired to
a free OpenRouter model. First full duel played badly, watchable in the terminal. Establish the
prompt-caching prefix layout now rather than discovering it later. **Seal the eval splits here** —
held-out hands, interrupt schedules, decks; committed and hashed.

*Staged deck bring-up within M1:* minimal Sky Striker core first (Raye / Roze / Engage / Kagari /
Hornet Drones), then the full 40. The multi-select and Fusion-material message paths that Forbidden
Droplet and the Albion package require are the most likely source of decoder sprawl — don't meet
them on day one of M1.

**M2 — Hierarchical agent, baselines, replay export.** Planner/executor/interrupt/memory split.
Baselines: random-legal, greedy, and **WindBot** — a [C# rule-based bot](https://github.com/IceYGO/windbot)
with per-deck executors, a free fixed-skill opponent. `.yrp` export so duels are watchable in EDOPro.

**M3 — Search and the referee.** Replay-based restore, value function, DFS/MCTS. Compute `V*` for
sealed cases, turning on the regret metric and simultaneously producing the strongest agent.

**M4 — Benchmark run + writeup.** Multi-model leaderboard, ablations (harness alone vs.
harness+search; flat vs. hierarchical; with vs. without cross-turn memory), public results.

**Out of scope for v1:** deck construction, and any bridge to live Master Duel — PvP botting there
is a reportable ToS violation ("using modding/cheats/tools") and risks the account. Offline vs.
WindBot and self-play gets everything research-wise.

---

## Metrics

**Primary — regret** (`V* − V`), per sealed case, against search-derived achievable value.

Secondary:
- **Recovery quality** — conditional on interruption at step *k*, how much of `V*` is retained.
- **Resource discipline** — Sky Striker specific: Widow Anchor / Shark Cannon used on the right
  target at the right time; spells banked vs. spent.
- **Own-interrupt timing** — the deck holds 8 reactive cards (Maxx "C", 3× Ash, Ghost Belle, Imperm,
  Called by, Solemn Accusation). Did the agent spend Ash on the right activation, or burn it on a
  low-value target and get run over two links later? Scored against search: what did holding vs.
  spending it cost in achievable value?
- **Re-plan discipline** — does the agent re-plan after interruption or continue a dead line?
  Detectable from the trace.
- Win rate vs. WindBot; Glicko across models (PTCG-Bench's protocol, for comparability).
- Cost and tokens per duel — non-negotiable to report; the whole design is bent around this axis.

There is no "illegal move rate" — the engine makes it structurally zero. The analogous failure is
passing when action was correct.

---

## Verification

- **M0:** determinism harness — 1000 duels replayed from `(seed, response log)`, asserting identical
  message streams. Everything else stands on this.
- **M1:** golden-file tests on `MSG_*` decoding against recorded `.yrp` replays; a scripted duel with
  known outcome green in CI; free-model smoke test runs at $0.
- **M2:** N duels vs. WindBot without crash or stall; exported `.yrp` opens and plays back correctly
  in EDOPro; trace inspection confirms the planner fires on interruptions.
- **M3:** search finds a known-good Sky Striker line from a hand-constructed hand; `V*` on a
  goldfish case matches community consensus. **This step needs the user's eyes** — see risk 3.
- **M4:** full sealed-split run reproducible from a pinned commit + pinned `cards.cdb`/`script/`
  hashes, by someone with only the repo.

---

## Repo

`github.com/kwabenaa/ygo-harness` — **public from day one, AGPL-3.0** (forced by linking ocgcore).
Initial commit: README with the thesis, license, `data/` pinning strategy, sealed-split policy.

---

## Open risks

1. **The core may not build cleanly on Apple Silicon.** This is the single biggest unknown and the
   reason M0 exists. With the Linux box out of scope there is no fallback dev target — if arm64
   fights us, the platform decision reopens.
2. **The value function is the soft spot.** `V*` is only as meaningful as the function scoring a
   position, and for a resource deck like Sky Striker that means valuing card advantage and GY
   state, which strong players genuinely disagree about. Start hand-written and legible, publish it
   explicitly, treat disagreement as a finding rather than a bug.
3. **Much of this decklist postdates the assistant's knowledge cutoff** — The Fallen & The Virtuous,
   Radiant Typhoon Vision, Forbidden Crown, Ecclesia and the Dark Dragon, Sky Striker Ace = Zero,
   Prototype Amatsu, Zeke, Camellia. Harmless for the build (card text comes from `cards.cdb`, and
   ground truth comes from search rather than from authored lines — the architecture already assumes
   this). But **the user is the domain oracle for M3 validation**: whether the search's best line
   matches community consensus is not something the assistant can independently check. Budget a
   review pass there.
4. **Benchmark decay.** Meta rotates with every banlist. Pin `cards.cdb`/`script/` by commit hash so
   results stay reproducible after the format moves on.
5. **Search cost at real branching factors** may make `V*` expensive on deep lines. Cap depth and
   report where the cap binds.


---

# Progress and corrections

What the first two milestones changed about the plan. Kept honest rather than
tidied: several of these contradict the estimates above.

## M0 — engine spike: complete

- ygopro-core builds on arm64 macOS; all 13 `OCG_*` functions export.
  `scripts/build_core.sh` reproduces it without a premake dependency.
- **127 full duels/sec, ~126k engine steps/sec** single-threaded on an M3 Air.
  Replaying a turn prefix to restore a search node costs single-digit
  milliseconds, so the search layer is affordable. This was the open question
  with the most riding on it.
- Determinism holds both ways: same seed gives a byte-identical message
  stream, a different seed gives a genuinely different duel.
- All 36 distinct cards in the Sky Striker list resolve with scripts present.

**Correction to the plan:** the engine does *not* shuffle. Reproducing a duel
needs two seeds, not one. The upside is that the deal is ours to control,
which is what sealed benchmark hands require.

## M1 — harness: mostly complete

Board state via the query API, compact renderer with hidden-info masking,
OpenAI-compatible provider, and a two-model hierarchical agent.

**The cost model in this plan was wrong by roughly 10x, in our favour.**

| | planned | measured |
|---|---|---|
| board state per decision | ~2,000 tok | **~170 tok** |
| card corpus (cacheable) | ~15,000 tok | **~3,900 tok** |
| cost per duel | ~$0.25 | **$0.004–0.013** |

Board verbosity is close to free. Cost is dominated by the model's own
reasoning output, so **reasoning length is the only dial that matters** — the
opposite of what this plan assumed. Consequence: full duels are affordable
after all, and the earlier conclusion that they were a luxury is withdrawn.

**Model roles** (measured, see `llm/models.yaml`): executor
`mistralai/mistral-nemo` at 0.8s and 2 output tokens; planner
`qwen/qwen3.7-flash` with `reasoning: {max_tokens: 256}` at ~3.1s. Note
`effort: "low"` is *slower* than the default and should not be used.

## The bug that invalidated everything measured before it

Every card script begins `local s,id=GetID()`, and `GetID` lives in
`utility.lua`. The core only requests `cXXXXXXX.lua` on demand, so the shared
library scripts are the host's responsibility — and we were not loading them.
Every card script died on its first line. **Every card had no effects.**

Duels still ran to completion, because summoning and setting are rules
actions needing no script. So it presented as a game where nothing had an
ability rather than as an error, and it silently invalidated everything
measured up to that point: `activatable` was empty across all 1,211 idle
decisions sampled, and every duel necessarily ended in deck-out.

Worth internalising as the shape of this codebase's failures: **the engine
fails quietly.** A wrong message id misroutes rather than raises; a missed
length prefix renders as an empty board; unloaded scripts render as a deck
with no abilities. Assume silence is not success, and assert on positives
(*is Engage! ever offered?*) rather than on the absence of errors.

## Metric correction, measured

Random-vs-random went 40-0 to player 0. Not bias in our code: random play
rarely deals lethal, so games become deck-out races, and the player going
second draws one extra card over the game and decks out first —
deterministically, regardless of RNG.

**Every win-rate number must be split by going first vs. second.** This is
also direct evidence for the plan's argument that regret-against-achievable
is the better primary metric; "did you win" is a weak signal in this game.

## Harness design is a benchmark variable

The planner/executor routing rule is hardcoded, which matches how Gemini and
Claude Plays Pokémon actually work — hand-refined scaffolding is the norm,
and [Continual Harness](https://arxiv.org/abs/2605.09998) exists precisely
because people want to stop doing it by hand.

But hand-tuned routing measures harness+model rather than model. Two rules
keep it honest: **fix the harness across all models** (never tune per model),
and **ablate it** — report flat vs. hierarchical as a result, not a config.

## Open

- `chain resolved` fires ~35x per duel and pushes the planner/executor split
  to 64/32, which is backwards. Should probably only fire when the resolved
  chain actually changed our board.
- The agent still wins by deck-out rather than damage. It plays real lines
  but does not yet close games.
- `.yrp` export (M1.5) not started — this is what makes duels watchable in
  EDOPro, and its format compatibility is still unverified.
