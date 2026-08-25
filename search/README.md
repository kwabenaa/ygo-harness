# search — the referee

Replay-based state restore, a value function, and DFS/MCTS over the action
tree. Its first job is not to play: it computes the best achievable value
`V*` for a sealed case, which is what makes the regret metric (`V* - V`)
possible. Search-as-agent comes after.

Empty until M3. Restore works by replaying a recorded `(seed, response log)`
into a fresh in-process duel - measured at single-digit milliseconds per node
at M0, which is what makes this affordable.
