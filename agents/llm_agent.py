"""An LLM policy over the engine's legal-action menu.

The split is deliberate and is the first step toward the hierarchical agent:
the model is asked only about *strategic* decisions (what to do in the main
phase, whether to chain), while mechanical ones (which empty zone to place a
card in, position selection) fall through to a cheap default.

That matters for cost. Roughly 80% of decision points in a duel are mechanical
and near-forced, and at ~$0.13/1M output tokens the difference between asking
the model 50 times and 250 times per duel is the difference between a
leaderboard that fits the budget and one that does not.
"""

from __future__ import annotations

import re
import struct
import time
from dataclasses import dataclass, field

from engine.constants import (
    MSG_SELECT_BATTLECMD, MSG_SELECT_CARD, MSG_SELECT_CHAIN, MSG_SELECT_DISFIELD,
    MSG_SELECT_EFFECTYN, MSG_SELECT_IDLECMD, MSG_SELECT_OPTION, MSG_SELECT_PLACE,
    MSG_SELECT_POSITION, MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD,
    MSG_SELECT_YESNO, MSG_SORT_CARD,
)
from engine.messages import (
    BATTLE_NAMES, BATTLE_TO_EP, BattleCmd, IDLE_NAMES, IdleCmd, SelectCard, SelectChain,
    SelectPlace, SelectPosition, SelectUnselect, parse_idlecmd,
    parse_select_battlecmd, parse_select_card, parse_select_chain,
    parse_select_place, parse_select_position, parse_select_tribute,
)
from engine.render import render_actions, render_state, zone_label
from llm.events import chain_context
from llm.events import recent as recent_events
from llm.prompt import decision_prompt, plan_prompt, system_prompt

_NUM = re.compile(r"-?\d+")

#: How many times to re-ask when the provider itself fails. Network trouble is
#: not the model failing, and killing a half-hour run on one dropped
#: connection would conflate infrastructure with capability.
PROVIDER_ATTEMPTS = 3


class NoAnswer(RuntimeError):
    """The model never produced a usable choice.

    Raised instead of picking a move. The harness used to fall back to option
    0, which is not a neutral default: in a chain window option 0 is
    *activate*, and on one measured puzzle that fallback activated Raigeki
    Break, destroyed the agent's own only monster and made the puzzle
    unwinnable - after which the run reported `unsolved`, as though the agent
    had played it out and lost. A duel we could not get an answer for is not a
    duel the agent lost, and reporting them alike hides the only fact that
    matters about it.
    """


class _CardMenu:
    """Adapts a SelectCard into a menu render_actions() can print."""

    def __init__(self, sc, db):
        self.sc, self.db = sc, db

    def actions(self):
        from engine.board import CardInfo
        return [(99, i, CardInfo(code=c)) for i, c in enumerate(self.sc.codes)]


class _PlaceMenu:
    """Adapts a SelectPlace into a numbered menu of zones.

    Placement used to fall through to `free[0]` - always the leftmost open
    zone. That is not a neutral default: Link markers point at specific zones,
    the Extra Monster Zones are shared, and effects key off columns, so
    choosing the first free slot quietly throws away a real decision.
    """

    def __init__(self, sp, viewer: int):
        self.free = sp.available()
        self.viewer = viewer

    def actions(self):
        return [(i, i, None) for i in range(len(self.free))]

    def names(self, db) -> dict:
        from engine.render import zone_label
        return {
            i: zone_label(player, loc, seq, viewer=self.viewer)
            for i, (player, loc, seq) in enumerate(self.free)
        }


class _ChainMenu:
    """Adapts a SelectChain into something render_actions() can print."""

    #: Spending an interrupt - or declining to - is never a formality, so
    #: these always go to the planner regardless of how narrow the menu is.
    deliberate = True

    def __init__(self, ch, db):
        self.ch, self.db = ch, db

    def actions(self):
        out = [(5, i, c) for i, c in enumerate(self.ch.options)]
        if self.ch.can_decline():
            out.append((-1, -1, None))
        return out


@dataclass
class Stats:
    asked: int = 0
    unparseable: int = 0
    out_of_range: int = 0
    fallbacks: int = 0
    #: Replies cut off mid-reasoning, before any answer was produced.
    truncated: int = 0
    #: Replies that carried no usable index and had to be re-asked. If the
    #: re-ask also fails the duel is abandoned, not answered on the model's
    #: behalf - see NoAnswer.
    reasked: int = 0
    choices: list[int] = field(default_factory=list)


class LLMAgent:
    """Policy callable compatible with Duel.run()."""

    def __init__(self, provider, db, deck_codes: list[int], *, viewer: int = 0,
                 verbose: bool = False, system: str | None = None,
                 planning: bool = False, objective: str = ""):
        self.p = provider
        self.db = db
        #: Callers with a different framing - a puzzle rather than a duel -
        #: pass their own system prompt; it is still built once and reused,
        #: which is what keeps the cached prefix intact.
        self.system = system if system is not None else system_prompt(db, deck_codes)
        self.viewer = viewer
        self.verbose = verbose
        self.stats = Stats()
        self.history: list[str] = []
        # Correct-but-unthinking answers for the decision types the model is
        # never asked about. Seeded, so a duel stays reproducible.
        from agents.random_legal import RandomLegal
        self.mechanical = RandomLegal(seed=viewer)
        #: A line to lethal, written once per turn and carried into every
        #: decision that turn.
        self.plan = ""
        self.planning = planning
        self.objective = objective
        self._plan_turn = -1
        #: Every decision, as the model saw it. This is the whole prompt body
        #: - board, hand, legal actions - plus the reply, so a transcript
        #: shows the harness's translation rather than a summary of it.
        self.trace: list[dict] = []

    # ------------------------------------------------------------ planning

    def _ensure_plan(self, duel, turn: int | None) -> None:
        """Write a line to lethal once per turn, and keep it.

        Rebuilt on a turn boundary rather than per decision: a plan is the
        thing that survives across decisions, and re-deriving it every step is
        exactly the shallow reasoning the split was meant to avoid. On a
        puzzle the turn never changes, so this fires once.
        """
        if not self.planning:
            return
        if duel.turn_count == self._plan_turn:
            return
        self._plan_turn = duel.turn_count
        provider = getattr(self, "planner", self.p)
        try:
            self.plan = provider.complete(
                self.system,
                plan_prompt(render_state(duel, self.db, self.viewer, turn=turn,
                             phase=None),
                            self.objective),
            ).strip()
        except Exception as e:                      # a failed plan is not fatal
            self.plan = ""
            if self.verbose:
                print(f"  [planning failed: {type(e).__name__}: {e}]")
            return
        self.plan = self._check_damage(duel, provider, turn)
        self.trace.append({
            "n": 0, "shown": "<planning request>", "reply": self.plan,
            "chose": None, "model": getattr(provider, "model", "?"),
            "reasoning": getattr(provider, "last_reasoning", "") or "",
        })
        if self.verbose and self.plan:
            print(f"  [plan] {self.plan[:200]}")

    def _check_damage(self, duel, provider, turn) -> str:
        """Hold the plan against the opponent's actual life total.

        The engine knows the number the plan has to reach, so a plan that does
        not reach it can be rejected before a single action is committed. This
        is the failure that survived the phase fix: the agent stopped planning
        illegal lines and started planning legal ones that were never enough,
        attacking for 200 into a 2400 life total.

        One re-plan, then the best attempt stands - the point is to catch a
        plan that was never going to win, not to loop until one appears.
        """
        from engine.board import query_field

        m = re.search(r"DAMAGE:[^=\n]*=\s*([\d,]+)", self.plan or "")
        info = query_field(duel)
        if not m or info is None:
            return self.plan
        target = info.lp[1 - self.viewer]
        stated = int(m.group(1).replace(",", ""))
        if stated >= target:
            return self.plan
        if self.verbose:
            print(f"  [plan deals {stated} vs {target} LP; re-planning]")
        try:
            return provider.complete(
                self.system,
                plan_prompt(render_state(duel, self.db, self.viewer, turn=turn),
                            self.objective)
                + f"\n\nYour previous plan was:\n{self.plan}\n\n"
                  f"That deals {stated}. The opponent has {target} life points, "
                  f"so it does not win. Find a line that reaches {target}. "
                  f"Look again at every card - your hand, your graveyard, your "
                  f"Extra Deck, and effects that change ATK or let a monster "
                  f"attack more than once. If no such line exists, say so.",
            ).strip() or self.plan
        except Exception:
            return self.plan

    # ------------------------------------------------------------ helpers

    def _ask(self, duel, cmd, n_options: int, turn: int | None = None,
             menu_names: dict | None = None, note: str = "") -> int:
        """Ask the model to choose among `n_options`. Returns an index."""
        # What the engine reported since we last acted, then what we did.
        # Board state cannot express either: an effect being negated, a card
        # being revealed, or a coin landing tails all leave a board that looks
        # like any other board.
        events = self.history[-6:] + recent_events(duel, self.db, self.viewer)
        self._ensure_plan(duel, turn)
        body = decision_prompt(
            render_state(duel, self.db, self.viewer, turn=turn,
                             phase=None)
            + "\nACTIONS\n" + (f"({note})\n" if note else "")
            + render_actions(self.db, cmd, names=menu_names),
            history=events,
            n_options=n_options,
            plan=self.plan,
        )
        self.stats.asked += 1
        step = {"n": self.stats.asked, "shown": body, "reply": "", "chose": None,
                "model": getattr(self.p, "model", "?")}
        self.trace.append(step)
        reply, last_error = "", None
        for attempt in range(PROVIDER_ATTEMPTS):
            try:
                reply = self.p.complete(self.system, body)
                break
            except Exception as e:                 # network/provider failure
                last_error = e
                self.stats.fallbacks += 1
                if self.verbose:
                    print(f"  [provider error {attempt + 1}/{PROVIDER_ATTEMPTS}: "
                          f"{type(e).__name__}: {e}]")
                time.sleep(2 ** attempt)
        else:
            step["reply"] = (f"<provider error: {type(last_error).__name__}: "
                             f"{last_error}>")
            raise NoAnswer(f"provider failed {PROVIDER_ATTEMPTS}x: "
                           f"{type(last_error).__name__}: {last_error}")
        # A reasoning model with no budget can spend the whole max_tokens
        # thinking and return nothing. Measured on one puzzle: 7 of 18 replies
        # came back empty after ~7k tokens of reasoning, and each one silently
        # became "take option 0" - which reads as the agent playing badly
        # rather than as the agent never having answered.
        if not reply and getattr(self.p, "last_finish_reason", None) == "length":
            self.stats.truncated += 1
            if self.verbose:
                print("  [reasoning ran past max_tokens; asking again, capped]")
            try:
                reply = self.p.complete(self.system, body,
                                        reasoning={"max_tokens": 512})
            except Exception:
                reply = ""
        step["reply"] = reply
        step["reasoning"] = getattr(self.p, "last_reasoning", "") or ''

        idx = self._read_choice(reply, n_options)
        if idx is None:
            # One terse re-ask before giving up: the thinking is already done,
            # what failed was producing the number.
            if self.verbose:
                print(f"  [no usable index in {reply[:60]!r}; re-asking]")
            try:
                reply = self.p.complete(
                    self.system,
                    body + f"\n\nReply with ONLY a single number from 0 to "
                           f"{n_options - 1}. No words, no explanation.",
                    reasoning={"max_tokens": 128},
                )
            except Exception as e:
                raise NoAnswer(f"re-ask failed: {type(e).__name__}: {e}") from e
            step["reply"] = f"{step['reply']}\n[re-asked] {reply}"
            idx = self._read_choice(reply, n_options)
        if idx is None:
            raise NoAnswer(f"no usable choice among {n_options} options; "
                           f"last reply {reply[:120]!r}")
        self.stats.choices.append(idx)
        step["chose"] = idx
        if self.verbose:
            print(f"  [chose {idx}] {reply[:100]}")
        return idx

    def _read_choice(self, reply: str, n_options: int) -> int | None:
        """The chosen index, or None when the reply does not contain one."""
        m = _NUM.search(reply or "")
        if not m:
            self.stats.unparseable += 1
            return None
        idx = int(m.group())
        if not (0 <= idx < n_options):
            self.stats.out_of_range += 1
            if self.verbose:
                print(f"  [out of range: {idx} not in 0..{n_options - 1}]")
            return None
        return idx

    # ------------------------------------------------------------ policy

    def __call__(self, msg, duel) -> bytes:
        if msg is None:
            return struct.pack("<i", 0)

        # --- strategic: ask the model -----------------------------------
        if msg.id == MSG_SELECT_IDLECMD:
            cmd = parse_idlecmd(msg.payload)
            acts = cmd.actions()
            if not acts:
                return struct.pack("<i", 0)
            self.viewer = cmd.player
            i = self._ask(duel, cmd, len(acts))
            kind, idx, card = acts[i]
            label = self.db.name(card.code) if card else ""
            verb = IDLE_NAMES.get(kind, str(kind))
            self.history.append(f"you {verb} {label}".strip())
            return IdleCmd.encode(kind, idx)

        # --- mechanical: cheap defaults ---------------------------------
        if msg.id == MSG_SELECT_BATTLECMD:
            cmd = parse_select_battlecmd(msg.payload)
            acts = cmd.actions()
            if not acts:
                return BattleCmd.encode(BATTLE_TO_EP)
            self.viewer = cmd.player
            i = self._ask(duel, cmd, len(acts), menu_names=BATTLE_NAMES)
            kind, idx, card = acts[i]
            label = self.db.name(card.code) if card else ""
            self.history.append(
                f"battle: {BATTLE_NAMES.get(kind, kind)} {label}".strip())
            return BattleCmd.encode(kind, idx)
        if msg.id == MSG_SELECT_CHAIN:
            ch = parse_select_chain(msg.payload)
            if not ch.options:
                return SelectChain.decline()
            self.viewer = ch.player
            # Spending a handtrap or a quick effect is a real decision, so it
            # goes to the model rather than to a default. Declining is offered
            # as the last option, but only when the engine allows it.
            menu = _ChainMenu(ch, self.db)
            i = self._ask(duel, menu, len(menu.actions()),
                          note=chain_context(duel, self.db, self.viewer))
            picked = menu.actions()[i]
            if picked[0] == -1:
                self.history.append("you declined to respond")
                return SelectChain.decline()
            self.history.append(
                f"you responded with {self.db.name(picked[2].code)}")
            return SelectChain.encode(picked[1])
        if msg.id == MSG_SELECT_UNSELECT_CARD:
            return SelectUnselect.encode(0)
        if msg.id in (MSG_SELECT_CARD, MSG_SELECT_TRIBUTE):
            # Different entry widths; see parse_select_tribute.
            sc = (parse_select_tribute if msg.id == MSG_SELECT_TRIBUTE
                  else parse_select_card)(msg.payload)
            # "Which card do you add / target / tribute" is a real strategic
            # decision - Engage! searching Hornet Drones vs Widow Anchor is a
            # different game - so it goes to the model whenever there is an
            # actual choice to make.
            if sc.min == sc.max == len(sc.codes) or len(sc.codes) <= 1:
                return SelectCard.encode(list(range(max(sc.min, 1))))
            self.viewer = sc.player
            menu = _CardMenu(sc, self.db)
            i = self._ask(duel, menu, len(menu.actions()))
            picked = menu.actions()[i][1]
            self.history.append(f"you chose {self.db.name(sc.codes[picked])}")
            need = max(sc.min, 1)
            rest = [j for j in range(len(sc.codes)) if j != picked]
            return SelectCard.encode(sorted([picked] + rest[:need - 1]))
        if msg.id in (MSG_SELECT_PLACE, MSG_SELECT_DISFIELD):
            sp = parse_select_place(msg.payload)
            free = sp.available()
            if not free:
                return struct.pack("<i", 0)
            need = max(sp.count, 1)
            if len(free) == 1:
                return SelectPlace.encode([free[0]] * need)
            menu = _PlaceMenu(sp, self.viewer)
            # The message carries zones and nothing else, so name the card
            # from what we just did. Without it the menu is five identical
            # zone names and no indication of what is being placed - which
            # the transcripts show the model guessing at.
            placing = self.history[-1] if self.history else ""
            i = self._ask(duel, menu, len(free), menu_names=menu.names(self.db),
                          note=f"choosing a zone for: {placing}" if placing
                          else "choosing a zone")
            chosen = free[i]
            self.history.append(
                f"you placed in {zone_label(*chosen, viewer=self.viewer)}")
            # Multi-placement asks for `count` zones; take the chosen one
            # first and fill from the rest rather than repeating it, which
            # would be rejected as a duplicate.
            rest = [z for z in free if z != chosen]
            return SelectPlace.encode(([chosen] + rest)[:need])
        if msg.id == MSG_SELECT_POSITION:
            pos = parse_select_position(msg.payload).available()
            return SelectPosition.encode(pos[0] if pos else 0x1)
        if msg.id in (MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO):
            return struct.pack("<i", 1)               # yes

        # Everything else is mechanical - sort orders, sum selections, the
        # announce family. Answering 0 is wrong for most of them and shows up
        # as an endless MSG_RETRY, so hand them to the baseline policy, which
        # holds the real encoders.
        return self.mechanical(msg, duel)
