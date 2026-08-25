"""When to spend a planner call instead of an executor call.

Split out of `HierarchicalAgent` so it can be measured without buying tokens:
the decision of *when* to deliberate is independent of what the models say, so
a random-legal duel exercises it exactly as an LLM duel would, for free. See
`scripts/deliberation_report.py`.
"""

from __future__ import annotations

from engine.board import board_signature


class Deliberation:
    """Edge-triggered on the duel's monotonic counters.

    Counters rather than a message buffer, because the buffer is cleared at
    every decision point - a draw-phase chain window would silently consume
    the turn-start signal before the main-phase decision that needed it.

    Three moments genuinely change the shape of a turn:

    - **our** turn starting. The opponent's turn start is not a planning
      moment for us: during their turn we only answer chain windows, and
      planning there doubled the planner call count for nothing.
    - the opponent activating something, which may invalidate the plan.
    - a chain **the opponent was part of** resolving and leaving the board
      different from the one we planned against.

    Both qualifiers on that last edge are measured, not assumed
    (`scripts/deliberation_report.py`, 20 duels, planner calls per duel):

        any chain resolves                              82.1
        ...and the board changed                        78.6   -4%
        ...and the opponent was in the chain            60.5  -26%
        ...both                                         57.2  -30%
        ...never                                        40.6  -51%

    The dominant term is our own uncontested chains: 431 of 830 resolutions.
    Those are the plan executing exactly as planned - nobody interfered, so
    there is nothing to reconsider - and paying the expensive model to look
    again is the single biggest waste in the split.

    `never` scores best and is still wrong. `opponent chained` fires when they
    *activate*, so a rule with no chain-resolution edge does its only thinking
    on a board mid-chain, before the interruption has resolved. The point is
    to think about the board we actually have to play around.
    """

    def __init__(self):
        self.planned = 0
        self.executed = 0
        self.triggers: dict[str, int] = {}
        self._turn = -1
        self._chain = 0
        self._chain_end = 0
        self._planned_sig: tuple | None = None

    def why(self, duel, viewer: int) -> str | None:
        if duel.turn_count != self._turn:
            self._turn = duel.turn_count
            self._chain = duel.chain_count
            self._chain_end = duel.chain_end_count
            if duel.turn_player == viewer:
                return "our turn start"
        if duel.chain_count != self._chain:
            self._chain = duel.chain_count
            if duel.last_chain_player != viewer:
                return "opponent chained"
        if duel.chain_end_count != self._chain_end:
            self._chain_end = duel.chain_end_count
            if duel.last_chain_player == viewer:
                return None             # our own chain, uncontested
            if board_signature(duel, viewer) != self._planned_sig:
                return "opponent's chain changed the board"
        return None

    def note(self, duel, viewer: int, why: str | None) -> None:
        """Record the outcome, and remember what we planned against."""
        if why:
            self.planned += 1
            self.triggers[why] = self.triggers.get(why, 0) + 1
            self._planned_sig = board_signature(duel, viewer)
        else:
            self.executed += 1

    @property
    def total(self) -> int:
        return self.planned + self.executed

    def __str__(self) -> str:
        if not self.total:
            return "no decisions"
        pct = 100 * self.planned / self.total
        by = ", ".join(f"{k} {v}" for k, v in
                       sorted(self.triggers.items(), key=lambda x: -x[1]))
        return (f"{self.planned} planned / {self.executed} executed "
                f"({pct:.0f}% planner)" + (f"  [{by}]" if by else ""))
