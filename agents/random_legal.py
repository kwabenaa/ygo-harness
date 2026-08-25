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
    MSG_SELECT_BATTLECMD, MSG_SELECT_CARD, MSG_SELECT_CHAIN, MSG_SELECT_EFFECTYN,
    MSG_SELECT_IDLECMD, MSG_SELECT_OPTION, MSG_SELECT_PLACE, MSG_SELECT_POSITION,
    MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_YESNO, MSG_SORT_CARD,
    MSG_SELECT_DISFIELD,
)
from engine.messages import (
    IdleCmd, SelectCard, SelectPlace, SelectUnselect, parse_idlecmd,
    parse_select_card, parse_select_place,
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
            # Battle types: 0 activate, 1 attack, 2 to M2, 3 to EP. Without
            # parsing the payload only "to end phase" is unconditionally safe.
            return struct.pack("<i", 3)

        if msg.id == MSG_SELECT_CHAIN:
            # -1 declines. Chain options are 0..n-1; declining is always legal
            # unless the chain is forced, in which case the engine retries and
            # we fall through to index 0 on the next pass.
            return struct.pack("<i", -1 if self.rng.random() < 0.7 else 0)

        if msg.id == MSG_SELECT_UNSELECT_CARD:
            # One index per round-trip - not the SELECT_CARD list format.
            return SelectUnselect.encode(0)

        if msg.id in (MSG_SELECT_CARD, MSG_SELECT_TRIBUTE):
            sc = parse_select_card(msg.payload)
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

        if msg.id in (MSG_SELECT_OPTION, MSG_SELECT_POSITION, MSG_SORT_CARD):
            # Handled generically for now; M1 gives these real decoders.
            self.unhandled[msg.id] = self.unhandled.get(msg.id, 0) + 1
            return struct.pack("<i", 0)

        self.unhandled[msg.id] = self.unhandled.get(msg.id, 0) + 1
        return struct.pack("<i", 0)
