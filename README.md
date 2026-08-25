# ygo-harness

An LLM agent and benchmark for Yu-Gi-Oh, built directly on the game's real rules engine.

> **Status: M0 — engine spike.** Nothing works yet.

## Why this exists

Yu-Gi-Oh is the hardest mainstream TCG nobody has pointed an LLM at. Pokémon TCG has PTCG-Bench,
Magic has UrzaGPT and a causal-RL gym. Yu-Gi-Oh has exactly one serious AI attempt — [ygo-agent][],
pure RL — which cost 32× RTX 4090 for 5 days / 100M games, covers a narrow deck set, and produces a
policy that cannot explain a single decision.

This project takes the other road: an LLM harness on top of `ygopro-core`, the actual C++ rules
engine that EDOPro and every other simulator runs on.

## The bet

**The engine hands you a legal-action menu at every decision point.** You do not read a screen, you
do not validate moves, you do not recover from illegal actions — the agent returns an index into a
menu the engine built. Everything that remains is planning under interruption, which is the part
worth studying.

The common objection to LLMs playing Yu-Gi-Oh is that they will hallucinate rulings and fabricate
card interactions. [Can Large Language Models Master Complex Card Games?][cardgames] documents
exactly that across Dou Dizhu and Mahjong. Three of its four reported failure modes are
architecturally excluded here:

| Reported failure mode | Status here |
|---|---|
| Rule violations, invalid moves | **Impossible** — no channel exists to express one |
| Hallucinated card interactions | **Delegated to the engine** — search executes and reports ground truth |
| Large discrete action-space mishandling | **Bounded** — an index into ~5–25 options |
| Hidden information | **Real and unfixed** — a genuine limitation |

## Yu-Gi-Oh is not solitaire

An early version of this design assumed combo lines have canonical correct sequences that could be
scored by line-matching. That is wrong. You commit an action, the engine resolves it, the engine
tells you whether the opponent chained, and only then do you choose again — possibly spending
resources to answer the interruption, possibly rerouting, possibly ending with nothing.

So ground truth is **computed, not authored**. For a given (hand, interruption schedule),
engine-backed search yields the best achievable value `V*`; the agent scores `V`; the metric is
**regret = V\* − V**. This handles "you got Ashed, so a weaker board was correct" natively.

**The search is the referee, not just a stronger agent.**

## Layout

```
engine/   ctypes bindings to ygopro-core + MSG_* decoders + text renderer
llm/      one OpenAI-compatible adapter: OpenRouter | Ollama | LM Studio | llama.cpp
search/   replay-based state restore, DFS/MCTS, value function
agents/   free-for-all: hierarchical LLM agent, search-guided agent, baselines
bench/    SEALED: eval splits, interrupt schedules, scoring protocol, results
viz/      terminal live view + .yrp replay export
data/     cards.cdb + scripts, pinned by commit hash
```

`agents/` and `bench/` are deliberately separated. Overfitting is a virtue in one and a sin in the
other; eval splits are sealed and hashed before any agent tuning begins.

## License

**AGPL-3.0.** Not a choice — `ygopro-core` is AGPL and this links it.

[ygo-agent]: https://github.com/sbl1996/ygo-agent
[cardgames]: https://arxiv.org/abs/2509.01328
