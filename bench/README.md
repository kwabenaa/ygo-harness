# bench — sealed evaluation

Nothing here is tuned against. `agents/` is the free-for-all; this directory
holds the protocol, the eval splits, and recorded results.

| Path | What |
|---|---|
| `splits/` | sealed cases: deck, deal seed, engine seed, opponent hand, interrupt policy |
| `results/` | runs written against a pinned commit + pinned `data/DATA_COMMITS` |

Empty until the splits are sealed. See `docs/PLAN.md` (M1, "seal the eval
splits here") for what a case is and why sealing precedes agent tuning.
