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

from .deliberation import Deliberation
from .llm_agent import LLMAgent


class HierarchicalAgent(LLMAgent):
    def __init__(self, planner, executor, db, deck_codes, *, viewer=0,
                 verbose=False, system=None, split=None):
        super().__init__(executor, db, deck_codes, viewer=viewer,
                         verbose=verbose, system=system)
        self.planner = planner
        self.executor = executor
        self.split = split or Deliberation()

    def _ask(self, duel, cmd, n_options: int, turn=None, **kw) -> int:
        why = self.split.why(duel, self.viewer, cmd)
        self.split.note(duel, self.viewer, why)
        self.p = self.planner if why else self.executor
        if self.verbose and why:
            print(f"  [planner: {why}]")
        return super()._ask(duel, cmd, n_options, turn=turn, **kw)

    @property
    def usage_summary(self) -> str:
        return f"planner {self.planner.usage} | executor {self.executor.usage}"
