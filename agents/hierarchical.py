"""Two-model hierarchical policy.

Deliberation is bought only where it can change the answer. The planner runs
at the start of a turn and after any opponent interruption - the moments when
the shape of the turn is actually in question - and a cheap executor handles
everything else.

Measured basis for the split (see llm/models.yaml): at reasoning budgets from
32 to 256 tokens, the planner model chose the same actions the no-reasoning
executor chose on the decision points tested. Most decisions in a duel are
near-forced, so paying a reasoning model for all of them buys nothing but
latency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.messages import IdleCmd, parse_idlecmd

from .llm_agent import LLMAgent


@dataclass
class Split:
    planned: int = 0
    executed: int = 0
    triggers: dict = field(default_factory=dict)

    def note(self, why: str | None) -> None:
        if why:
            self.planned += 1
            self.triggers[why] = self.triggers.get(why, 0) + 1
        else:
            self.executed += 1


class HierarchicalAgent(LLMAgent):
    def __init__(self, planner, executor, db, deck_codes, *, viewer=0,
                 verbose=False):
        super().__init__(executor, db, deck_codes, viewer=viewer, verbose=verbose)
        self.planner = planner
        self.executor = executor
        self.split = Split()
        self._seen_turn = -1
        self._seen_chain = 0
        self._seen_chain_end = 0

    def _why_deliberate(self, duel) -> str | None:
        """Reasons to spend a planner call on this decision.

        Edge-triggered on the duel's monotonic counters rather than on a
        message buffer. The buffer is cleared at every decision point, so a
        draw-phase chain window would silently consume the turn-start signal
        before the main-phase decision that needed it.

        Three moments genuinely change the shape of the turn:

        - **our** turn starting. The opponent's turn start is not a planning
          moment for us - during their turn we only answer chain windows, and
          planning there doubled the planner call count for nothing.
        - the opponent activating something, which may invalidate the plan.
        - a chain resolving, after which the board has changed and the route
          to the target board has to be reconsidered.
        """
        if duel.turn_count != self._seen_turn:
            self._seen_turn = duel.turn_count
            self._seen_chain = duel.chain_count
            self._seen_chain_end = duel.chain_end_count
            if duel.turn_player == self.viewer:
                return "our turn start"
        if duel.chain_count != self._seen_chain:
            self._seen_chain = duel.chain_count
            if duel.last_chain_player != self.viewer:
                return "opponent chained"
        if duel.chain_end_count != self._seen_chain_end:
            self._seen_chain_end = duel.chain_end_count
            return "chain resolved"
        return None

    def _ask(self, duel, cmd, n_options: int, turn=None, **kw) -> int:
        why = self._why_deliberate(duel)
        self.split.note(why)
        self.p = self.planner if why else self.executor
        if self.verbose and why:
            print(f"  [planner: {why}]")
        return super()._ask(duel, cmd, n_options, turn=turn, **kw)

    @property
    def usage_summary(self) -> str:
        return (f"planner {self.planner.usage} | executor {self.executor.usage}")
