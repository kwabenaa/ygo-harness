# ygo-harness — working notes for agents

An LLM agent and benchmark for Yu-Gi-Oh, built on `ygopro-core` (the real
rules engine behind EDOPro). Read `docs/PLAN.md` for why the project exists
and where it is going; this file is how to work in it without re-learning
what already cost a debugging session.

## Setup

```bash
brew install cmake lua@5.4 meson ninja pkg-config   # macOS
./scripts/build_core.sh      # builds engine/lib/libocgcore.dylib
./scripts/fetch_data.sh      # card database + Lua card scripts
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install pytest openai rich pyyaml
python -m pytest tests/ -q
```

`.env` holds `OPENROUTER_API_KEY`. It is gitignored — **this repo is public,
never commit it.**

## Layout

| Path | What |
|---|---|
| `engine/ocgapi.py` | ctypes bindings to the `OCG_*` C API |
| `engine/duel.py` | duel lifecycle + the message/response loop |
| `engine/messages.py` | decoders/encoders per `MSG_*` decision type |
| `engine/board.py` | board state via `OCG_DuelQuery*` |
| `engine/render.py` | compact text rendering, **hidden-info masking** |
| `llm/provider.py` | one OpenAI-compatible client (OpenRouter/Ollama/…) |
| `llm/models.yaml` | model roles, with the measurements that chose them |
| `agents/` | policies. Anything goes here |
| `bench/` | **sealed** eval protocol. Do not tune against it |
| `viz/replay.py` | `.yrp` export - see the two `REPLAY_NEWREPLAY` traps below |
| `scripts/verify_yrp.py` | replays a `.yrp` through EDOPro's own core/cards/scripts |
| `docs/PLAN.md`, `DECISIONS.md` | plan, and the record of decisions/deferrals |

## Traps

Every one of these cost real time. They share a shape: **the engine fails
silently rather than loudly**, so a bug looks like bad play rather than an
error.

1. **Global Lua scripts must be loaded before any card is created.** Every
   card script starts `local s,id=GetID()`, and `GetID` is in `utility.lua`.
   The core only ever requests `cXXXXXXX.lua` on demand. Without
   `constant.lua` + `utility.lua` (loaded in `Duel.load_globals`, cascading to
   everything else) *every card has no effects*, duels still run to
   completion, and it looks like a game where nothing has an ability.
   Guarded by `tests/test_card_effects.py`.

2. **The engine does not shuffle.** `Processors::Startup` draws `start_count`
   cards off the *back* of the main deck and nothing more. Shuffling is the
   client's job, so reproducing a duel needs **two** seeds — one for the deal,
   one for the engine's `seed[4]`. Upside: the deal is ours, so an exact
   opening hand can be dealt by ordering the list.

3. **`MSG_RETRY` does not restate the question.** Track the pending decision
   across loop iterations or the policy answers into the void forever.

4. **Query buffers start with a `uint32` total-length prefix.** Skip it or
   the whole TLV parse desyncs — and it renders as "the board is empty",
   not as an error.

5. **Field widths are not uniform within one message.** In
   `MSG_SELECT_IDLECMD` the *repositionable* list writes `sequence` as
   `uint8` while every other list in the same message uses `uint32`.

6. **Response formats differ per message and are not guessable:**
   - `MSG_SELECT_CARD`: `int32 type, uint32 count, indices…` (type 0 = uint32 indices)
   - `MSG_SELECT_UNSELECT_CARD`: **not** the same — `int32 1, int32 index`, one at a time
   - `MSG_SELECT_PLACE`: 3 `int8`s per placement; `flag` marks **unavailable** zones
   - `MSG_SELECT_POSITION`: a single position bit present in the allowed mask; `0` is never valid
   - `MSG_SELECT_CHAIN`: `-1` declines, **but only when `forced` is unset**
   - `MSG_SELECT_IDLECMD`: `(index << 16) | type`

   When in doubt read `vendor/ygopro-core/playerop.cpp` — the validator right
   after each `new_message(...)` is the spec.

7. **Constants are hand-transcribed and drift silently.** `MSG_SORT_CARD` and
   `MSG_SELECT_DISFIELD` were transposed once; a wrong id misroutes a
   decision instead of raising. `tests/test_constants.py` checks every one
   against the header. Note `LINK_MARKER_*` are **octal** in C (`0010` is 8).

8. **Hidden information is masked in `render.py`, once.** The query API
   returns the opponent's hand and set cards without complaint. Leaking them
   would invalidate every result without raising. When testing this,
   remember both players run the same deck — a whole-text substring search
   cannot tell "leaked their Ash Blossom" from "named my own".

9. **ctypes callbacks must be kept alive** for the duel's lifetime, or the
   core calls into freed memory.

10. **`.yrp` fields that exist only under `REPLAY_NEWREPLAY`.** A per-side
    `uint32` player count before the names, and a `uint32` custom-rule-card
    count after the decks. Omit either and EDOPro reads name bytes as a
    player count, or a response byte as a rule count - it does not reject the
    file, it misparses it. A round-trip through our own parser cannot catch
    this, so `tests/test_replay.py` pins byte offsets taken from
    `Replay::ParseNames`/`ParseDecks` instead.

11. **EDOPro's install directory is stale the moment it first runs.** The
    real core, cards and scripts live in
    `repositories/delta-bagooska/{bin,*.delta.cdb,script}`, cloned on first
    launch over the installer's snapshot. Reading the bundled `script/` gave
    a deck with eight cards missing and a replay that desynced at turn 2.

12. **Lua is compiled as C++** (see `scripts/build_core.sh`). Not cosmetic:
    Lua's `longjmp` error handling would skip C++ destructors otherwise. This
    is why upstream `meson.build` cannot be used — it links a C-compiled
    system Lua.

## Models

See `llm/models.yaml`. Two findings worth not re-deriving:

- On OpenRouter, `reasoning` must go through the SDK's `extra_body`, not as a
  keyword argument.
- **`reasoning: {effort: "low"}` is *slower* than the default** on
  qwen3.7-flash (11.8s vs 7.7s). Use a bounded budget instead:
  `reasoning: {max_tokens: 256}` gives ~3.1s. Latency is roughly linear in
  reasoning tokens — 10ms/token plus 0.8s overhead.

## Conventions

- Prefer the engine's **query API** for state; never rebuild a shadow state
  machine from the message stream.
- Every duel records `(seed, response log)`. Not for rollback — it is what
  makes replay, offline scoring and `.yrp` export possible.
- **Win rate is not a skill signal without controlling turn order.** Random
  play rarely deals lethal, so games become deck-out races, and the player
  going second draws one extra card and decks out first. Always split results
  by going first vs. second.
- `bench/` is sealed. Tune in `agents/`, never against the eval set.
