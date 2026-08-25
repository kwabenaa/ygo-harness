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
    parse_select_place, parse_select_position,
)
from engine.render import render_actions, render_state, zone_label
from llm.prompt import decision_prompt, system_prompt

_NUM = re.compile(r"-?\d+")


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
    choices: list[int] = field(default_factory=list)


class LLMAgent:
    """Policy callable compatible with Duel.run()."""

    def __init__(self, provider, db, deck_codes: list[int], *, viewer: int = 0,
                 verbose: bool = False, system: str | None = None):
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
        #: Every decision, as the model saw it. This is the whole prompt body
        #: - board, hand, legal actions - plus the reply, so a transcript
        #: shows the harness's translation rather than a summary of it.
        self.trace: list[dict] = []

    # ------------------------------------------------------------ helpers

    def _ask(self, duel, cmd, n_options: int, turn: int | None = None,
             menu_names: dict | None = None) -> int:
        """Ask the model to choose among `n_options`. Returns an index."""
        body = decision_prompt(
            render_state(duel, self.db, self.viewer, turn=turn)
            + "\nACTIONS\n" + render_actions(self.db, cmd, names=menu_names),
            history=self.history,
            n_options=n_options,
        )
        self.stats.asked += 1
        step = {"n": self.stats.asked, "shown": body, "reply": "", "chose": None,
                "model": getattr(self.p, "model", "?")}
        self.trace.append(step)
        try:
            reply = self.p.complete(self.system, body)
        except Exception as e:                     # network/provider failure
            self.stats.fallbacks += 1
            step["reply"] = f"<provider error: {type(e).__name__}: {e}>"
            if self.verbose:
                print(f"  [provider error: {type(e).__name__}: {e}]")
            return 0
        step["reply"] = reply
        step["reasoning"] = getattr(self.p, "last_reasoning", "") or ''

        m = _NUM.search(reply)
        if not m:
            self.stats.unparseable += 1
            if self.verbose:
                print(f"  [unparseable reply: {reply[:80]!r}]")
            return 0
        idx = int(m.group())
        if not (0 <= idx < n_options):
            self.stats.out_of_range += 1
            if self.verbose:
                print(f"  [out of range: {idx} not in 0..{n_options-1}]")
            return 0
        self.stats.choices.append(idx)
        step["chose"] = idx
        if self.verbose:
            print(f"  [chose {idx}] {reply[:100]}")
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
            i = self._ask(duel, menu, len(menu.actions()))
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
            sc = parse_select_card(msg.payload)
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
            i = self._ask(duel, menu, len(free), menu_names=menu.names(self.db))
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
