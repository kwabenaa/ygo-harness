"""Holding the agent to its own plan, without ever retracing.

The failure this exists for: on Seto VS Ishizu the agent produced a correct,
lethal plan - Fiend's Sanctuary for a Token, Stormforth to borrow a tribute,
Normal Summon Obelisk on three tributes, Soul Energy MAX for 4000 into 1400
life points - and then executed step 4 before step 3. Without the Token it
never had three tributes, so `summon: Obelisk` was never offered in a single
menu for the rest of the duel, and the linchpin of its own plan quietly became
unreachable.

Nothing about that is a reasoning failure the model can be prompted out of in
general: at the moment it chose, both steps were legal and it had no signal
that order mattered. What it lacked was a sense of *where it was in its own
plan*.

So this tracks the plan as an ordered list and, at every decision, reports
which step is next and whether the menu currently offers it. It never
speculates and never asks the engine to undo anything - it reads the
legal-action menu, which the engine hands over anyway. See DECISIONS.md, "The
agent never retraces".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Lines that are commentary rather than a step. Plans come back with a
#: DAMAGE line and the occasional aside; neither is an action to take.
_NOISE = re.compile(r"^\s*(DAMAGE:|Correction:|Alternative:|Note:|Total\b)", re.I)
_STEP = re.compile(r"^\s*(?:\*\*)?(\d+)[.)]\s*(.+)$")


@dataclass
class Step:
    n: int
    text: str
    #: Card names mentioned, matched against the cards actually in this duel.
    cards: tuple[str, ...] = ()
    done: bool = False


@dataclass
class PlanTracker:
    """An ordered plan, and how far through it the agent has got."""

    steps: list[Step] = field(default_factory=list)
    #: Times the agent took an action while an earlier step was available.
    skipped_ahead: int = 0

    @classmethod
    def parse(cls, plan: str, known_cards: list[str]) -> "PlanTracker":
        """Read a numbered plan, keeping only lines that name a real card.

        Card names come from the duel's own card list rather than from a
        general parse, because a plan mentions cards by name and nothing else
        in the line is reliable to match on.
        """
        steps = []
        for line in (plan or "").splitlines():
            if _NOISE.match(line):
                continue
            m = _STEP.match(line)
            if not m:
                continue
            text = m.group(2).replace("*", "").strip()
            named = tuple(c for c in known_cards if c and c.lower() in text.lower())
            steps.append(Step(int(m.group(1)), text, named))
        return cls(steps=steps)

    # ------------------------------------------------------------ progress

    def pending(self) -> list[Step]:
        return [s for s in self.steps if not s.done]

    def _offered(self, step: Step, options: list[str]) -> int | None:
        """Index of a menu option that would carry out `step`, if any."""
        if not step.cards:
            return None
        for i, label in enumerate(options):
            low = label.lower()
            if any(c.lower() in low for c in step.cards):
                return i
        return None

    def note_choice(self, chosen_label: str, options: list[str]) -> None:
        """Record what was taken, and whether it jumped an available step."""
        pending = self.pending()
        if not pending:
            return
        low = (chosen_label or "").lower()
        matched = next(
            (s for s in pending
             if s.cards and any(c.lower() in low for c in s.cards)), None)

        # Count the skip before marking anything done: taking a later step
        # while the next one was sitting in the same menu *is* the ordering
        # failure, and it looks like ordinary progress once the later step is
        # ticked off.
        first = pending[0]
        if matched is not first and self._offered(first, options) is not None:
            self.skipped_ahead += 1

        if matched is not None:
            matched.done = True

    def is_dead(self, options: list[str]) -> bool:
        """Whether the next step names a card the menu cannot act on.

        Not proof - a step may simply need something else to happen first. It
        becomes proof when it stays true, which is what the caller counts.
        """
        pending = self.pending()
        if not pending or not pending[0].cards:
            return False
        return self._offered(pending[0], options) is None

    def choose(self, options: list[str]) -> int | None:
        """The option that carries out the next step, if it is unambiguous.

        Returns an index only when **exactly one** option matches the next
        pending step. Several matches, or none, return None and the decision
        goes to the model.

        Deliberately strict. The harness must never commit to an action the
        plan did not name - that is the whole safety property of an agent that
        cannot retrace. A wrong guess here is not recoverable the way a wrong
        guess in a search would be, because there is no undo in a real duel.
        """
        pending = self.pending()
        if not pending:
            return None
        step = pending[0]
        if not step.cards:
            return None
        hits = [
            i for i, label in enumerate(options)
            if any(c.lower() in label.lower() for c in step.cards)
        ]
        return hits[0] if len(hits) == 1 else None

    # ------------------------------------------------------------ prompt

    def render(self, options: list[str]) -> str:
        """The plan with progress marked, for the decision prompt."""
        if not self.steps:
            return ""
        lines = []
        pending = self.pending()
        nxt = pending[0] if pending else None
        for s in self.steps:
            if s.done:
                mark, note = "done", ""
            elif s is nxt:
                where = self._offered(s, options)
                mark = "NEXT"
                note = (f"  <- available now, option {where}" if where is not None
                        else "  <- NOT available in this menu")
            else:
                where = self._offered(s, options)
                mark = "    "
                note = f"  (option {where})" if where is not None else ""
            lines.append(f"  [{mark}] {s.n}. {s.text[:110]}{note}")
        tail = ""
        if nxt is not None and self._offered(nxt, options) is None:
            tail = ("\nYour next step is not available. Either something must "
                    "happen first, or the plan is dead - if it is dead, say so "
                    "and pick the best remaining action.")
        return "YOUR PLAN, AND WHERE YOU ARE IN IT\n" + "\n".join(lines) + tail
