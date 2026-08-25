"""Random-legal policy: pick uniformly at random from whatever is legal.

This is the stress test the always-pass control cannot be. Passing every turn
never summons, never activates and never attacks, so most of the engine's
message space is never reached. Playing randomly reaches it, which is how the
remaining decoders get shaken out.

It is also the floor every real agent must beat.
"""

from __future__ import annotations

import random
import struct

from engine.constants import (
    MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
    MSG_ANNOUNCE_RACE, MSG_ROCK_PAPER_SCISSORS,
    MSG_SELECT_BATTLECMD, MSG_SELECT_CARD, MSG_SELECT_CHAIN, MSG_SELECT_COUNTER,
    MSG_SELECT_EFFECTYN,
    MSG_SELECT_IDLECMD, MSG_SELECT_OPTION, MSG_SELECT_PLACE, MSG_SELECT_POSITION,
    MSG_SELECT_SUM, MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD,
    MSG_SELECT_YESNO, MSG_SORT_CARD, MSG_SORT_CHAIN,
    MSG_SELECT_DISFIELD,
)
from engine.declare import find_declarable
from engine.messages import (
    BATTLE_ATTACK, BATTLE_TO_EP, AnnounceCard, AnnounceNumber, BattleCmd,
    IdleCmd, SelectCard, SelectChain, SelectCounter, SelectOption,
    SelectPlace, SelectPosition, SelectSum, SelectUnselect, SortCard,
    parse_announce_attrib, parse_announce_card, parse_announce_number,
    parse_announce_race, parse_idlecmd, parse_select_battlecmd,
    parse_select_card, parse_select_chain, parse_select_counter,
    parse_select_option, parse_select_place, parse_select_position, parse_select_tribute,
    parse_select_sum, parse_sort_card,
)


class RandomLegal:
    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)
        self.unhandled: dict[int, int] = {}

    def __call__(self, msg, duel) -> bytes:
        if msg is None:
            return struct.pack("<i", 0)

        if msg.id == MSG_SELECT_IDLECMD:
            acts = parse_idlecmd(msg.payload).actions()
            t, i, _ = self.rng.choice(acts)
            return IdleCmd.encode(t, i)

        if msg.id == MSG_SELECT_BATTLECMD:
            cmd = parse_select_battlecmd(msg.payload)
            acts = cmd.actions()
            if not acts:
                return BattleCmd.encode(BATTLE_TO_EP)
            # Prefer attacking when possible - a baseline that never attacks
            # makes every game a deck-out race and measures nothing.
            attacks = [a for a in acts if a[0] == BATTLE_ATTACK]
            pool = attacks if (attacks and self.rng.random() < 0.8) else acts
            k, i, _ = self.rng.choice(pool)
            return BattleCmd.encode(k, i)

        if msg.id == MSG_SELECT_CHAIN:
            ch = parse_select_chain(msg.payload)
            if not ch.options:
                return SelectChain.decline()
            if not ch.can_decline():
                return SelectChain.encode(self.rng.randrange(len(ch.options)))
            if self.rng.random() < 0.7:
                return SelectChain.decline()
            return SelectChain.encode(self.rng.randrange(len(ch.options)))

        if msg.id == MSG_SELECT_UNSELECT_CARD:
            # One index per round-trip - not the SELECT_CARD list format.
            return SelectUnselect.encode(0)

        if msg.id in (MSG_SELECT_CARD, MSG_SELECT_TRIBUTE):
            # Different entry widths; see parse_select_tribute.
            sc = (parse_select_tribute if msg.id == MSG_SELECT_TRIBUTE
                  else parse_select_card)(msg.payload)
            n = max(sc.min, 1)
            avail = max(len(sc.codes), n)
            picks = self.rng.sample(range(avail), min(n, avail))
            return SelectCard.encode(sorted(picks))

        if msg.id in (MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO):
            return struct.pack("<i", self.rng.randint(0, 1))

        if msg.id in (MSG_SELECT_PLACE, MSG_SELECT_DISFIELD):
            sp = parse_select_place(msg.payload)
            free = sp.available()
            if not free:
                return struct.pack("<i", 0)
            picks = [self.rng.choice(free) for _ in range(max(sp.count, 1))]
            return SelectPlace.encode(picks)

        if msg.id == MSG_SELECT_POSITION:
            pos = parse_select_position(msg.payload).available()
            return SelectPosition.encode(self.rng.choice(pos) if pos else 0x1)

        if msg.id == MSG_SELECT_OPTION:
            opt = parse_select_option(msg.payload)
            n = max(len(opt.options), 1)
            return SelectOption.encode(self.rng.randrange(n))

        if msg.id in (MSG_SORT_CARD, MSG_SORT_CHAIN):
            # A permutation, one int8 per card - not an index. Answering 0
            # here fails the moment there is more than one card, because the
            # validator rejects a repeated position.
            cards = parse_sort_card(msg.payload).cards
            if not cards:
                return SortCard.decline()
            order = list(range(len(cards)))
            self.rng.shuffle(order)
            return SortCard.encode(order)

        if msg.id == MSG_SELECT_SUM:
            sel = parse_select_sum(msg.payload)
            picks = sel.solve()
            if picks is None:
                # No combination satisfies the sum. Nothing legal exists to
                # send, so record it rather than pretending otherwise.
                self.unhandled[msg.id] = self.unhandled.get(msg.id, 0) + 1
                return SelectCard.encode([])
            return SelectCard.encode(picks)

        if msg.id == MSG_SELECT_COUNTER:
            ctr = parse_select_counter(msg.payload)
            return SelectCounter.encode(ctr.spread())

        if msg.id in (MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB):
            ann = (parse_announce_race if msg.id == MSG_ANNOUNCE_RACE
                   else parse_announce_attrib)(msg.payload)
            return ann.encode(ann.pick())

        if msg.id == MSG_ANNOUNCE_NUMBER:
            ann = parse_announce_number(msg.payload)
            n = max(len(ann.options), 1)
            return AnnounceNumber.encode(self.rng.randrange(n))

        if msg.id == MSG_ANNOUNCE_CARD:
            ann = parse_announce_card(msg.payload)
            code = find_declarable(duel.db, ann.opcodes)
            if code is None:
                self.unhandled[msg.id] = self.unhandled.get(msg.id, 0) + 1
                return AnnounceCard.encode(0)
            return AnnounceCard.encode(code)

        if msg.id == MSG_ROCK_PAPER_SCISSORS:
            return struct.pack("<i", self.rng.randint(1, 3))

        self.unhandled[msg.id] = self.unhandled.get(msg.id, 0) + 1
        return struct.pack("<i", 0)
