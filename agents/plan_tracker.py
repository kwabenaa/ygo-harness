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

#: Where a step stops naming what it *does* and starts naming what it spends
#: or points at. "Tribute Summon Zanki by Tributing La Jinn" has to split at
#: the second "Tribut-", not the first, so a marker followed by Summon/Set is
#: part of the action rather than the cost.
_OPERAND = re.compile(
    r"\b(?:by\s+)?(?:discard|tribut|banish|target|destroy|send|return|add)\w*\b"
    r"(?!\s+(?:Summon|Set))", re.I)

#: Step verb -> the menu action word it should match. Checked longest-first,
#: so "special summon" never resolves to "summon".
_VERBS = (
    ("special summon", "special summon"),
    ("tribute set", "set"),
    ("normal summon", "summon"),
    ("tribute summon", "summon"),
    ("flip summon", "summon"),
    ("activate", "activate"),
    ("summon", "summon"),
    ("attack", "attack"),
    ("reposition", "reposition"),
    ("battle phase", "to battle phase"),
    ("end phase", "to end phase"),
)


def _verb_of(text: str) -> str | None:
    low = text.lower()
    best = None
    for phrase, action in _VERBS:
        i = low.find(phrase)
        if i >= 0 and (best is None or i < best[0] or len(phrase) > len(best[1])):
            if best is None or i < best[0]:
                best = (i, phrase, action)
    return best[2] if best else None


@dataclass
class Step:
    n: int
    text: str
    #: Card names mentioned, matched against the cards actually in this duel.
    cards: tuple[str, ...] = ()
    #: The card this step acts *with* - what you activate, summon or attack
    #: with. Separated from the rest because matching on every mentioned card
    #: is what stopped the plan from ever executing itself: a step naming its
    #: cost and its target hits three options in a Main Phase menu, reads as
    #: ambiguous, and goes to the model - so the better the plan describes
    #: itself, the less it was used.
    actor: tuple[str, ...] = ()
    #: What it spends or points at: discards, tributes, banishes, targets.
    #: These are the sub-decisions that follow, and naming them is what makes
    #: them safe to carry out without asking.
    operands: tuple[str, ...] = ()
    #: Menu action word this step expects, e.g. "summon" - distinguishes
    #: "summon: Zanki" from "set monster: Zanki", which name the same card.
    verb: str | None = None
    done: bool = False


@dataclass
class PlanTracker:
    """An ordered plan, and how far through it the agent has got."""

    steps: list[Step] = field(default_factory=list)
    #: Times the agent took an action while an earlier step was available.
    skipped_ahead: int = 0
    #: The step whose action was taken most recently. Its costs and targets
    #: are the sub-decisions the engine is about to ask about, so this is what
    #: makes "discarding Night Assailant" usable when the discard menu opens
    #: two messages later.
    active: Step | None = None
    #: Operands already spent by the active step, so a step naming two of them
    #: does not answer the second menu with the first card.
    used: set = field(default_factory=set)

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
            cut = _OPERAND.search(text)
            head = text[:cut.start()] if cut else text
            tail = text[cut.start():] if cut else ""
            actor = tuple(c for c in named if c.lower() in head.lower())
            operands = tuple(c for c in named
                             if c.lower() in tail.lower() and c not in actor)
            steps.append(Step(int(m.group(1)), text, named,
                              actor=actor, operands=operands,
                              verb=_verb_of(head)))
        return cls(steps=steps)

    # ------------------------------------------------------------ progress

    def pending(self) -> list[Step]:
        return [s for s in self.steps if not s.done]

    def _offered(self, step: Step, options: list[str]) -> int | None:
        """Index of a menu option that would carry out `step`, if any.

        Keyed on the step's actor, not every card it mentions. A step whose
        *target* happens to appear in the menu is not a step you can take, and
        counting it as one made `is_dead` too optimistic - the plan looked
        alive while its actual action was unavailable.
        """
        names = step.actor or step.cards
        if not names:
            return None
        hits = self._hits(names, step.verb, options)
        return hits[0] if hits else None

    @staticmethod
    def _hits(names, verb: str | None, options: list[str]) -> list[int]:
        """Options naming one of `names`, narrowed by the action word."""
        hits = [i for i, label in enumerate(options)
                if any(c.lower() in label.lower() for c in names)]
        if len(hits) > 1 and verb:
            # "summon: Zanki" and "set monster: Zanki" name the same card and
            # are different plays. The verb is what tells them apart.
            narrowed = [i for i in hits
                        if options[i].split(":")[0].strip().lower() == verb]
            if len(narrowed) == 1:
                return narrowed
        return hits

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
            # The sub-decisions the engine is about to ask about belong to
            # this step, not to whatever is pending next.
            self.active = matched
            self.used = set()

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
        names = step.actor or step.cards
        if not names:
            return None
        hits = self._hits(names, step.verb, options)
        return hits[0] if len(hits) == 1 else None

    def choose_operand(self, options: list[str]) -> int | None:
        """The card the active step said to discard, tribute or target.

        Separate from `choose` because these menus are not action menus: the
        step has already been committed and the engine is asking what to aim
        it at. `_CardMenu` routes here first and only escalates when the plan
        did not name the answer - which keeps the safety property intact (we
        still never commit to something the plan did not name) while removing
        a model call for something already decided.
        """
        step = self.active
        if step is None:
            return None
        names = [c for c in step.operands if c not in self.used]
        if not names:
            return None
        hits = [i for i, label in enumerate(options)
                if any(c.lower() in label.lower() for c in names)]
        if len(hits) != 1:
            return None
        label = options[hits[0]].lower()
        for c in names:
            if c.lower() in label:
                self.used.add(c)
                break
        return hits[0]

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
