"""M0 smoke test: drive a real duel end to end and prove determinism.

Policy is deliberately trivial (always answer 0 = first legal option). The
point is not to play well, it is to show the engine runs, the message loop
decodes, and identical seeds produce identical duels.
"""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.deck import Deck
from engine.duel import Duel
from engine.constants import (
    MSG_NAMES, MSG_SELECT_BATTLECMD, MSG_SELECT_CHAIN, MSG_SELECT_IDLECMD,
)
from engine.constants import MSG_SELECT_CARD, MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD
from engine.messages import (
    IDLE_TO_BP, IDLE_TO_EP, IdleCmd, SelectCard, parse_idlecmd, parse_select_card,
)

SEED = (0x1234_5678_9ABC_DEF0, 0x0FED_CBA9_8765_4321, 0xDEAD_BEEF_CAFE_BABE, 42)


BATTLE_TO_EP = 3  # playerop.cpp battle validator: t==3 is "go to end phase"


def always_pass(msg, duel):
    """Deterministic do-nothing policy: end the turn as soon as legal.

    Not a strategy - a control. It exercises the full duel loop without any
    of the decisions we actually care about, so any nondeterminism it shows
    is the engine's, not the agent's.
    """
    if msg is None:
        return (0).to_bytes(4, "little", signed=True)
    if msg.id == MSG_SELECT_IDLECMD:
        cmd = parse_idlecmd(msg.payload)
        if cmd.to_ep:
            return IdleCmd.encode(IDLE_TO_EP)
        if cmd.to_bp:
            return IdleCmd.encode(IDLE_TO_BP)
        acts = cmd.actions()
        t, i, _ = acts[0]
        return IdleCmd.encode(t, i)
    if msg.id == MSG_SELECT_BATTLECMD:
        return (BATTLE_TO_EP).to_bytes(4, "little", signed=True)
    if msg.id == MSG_SELECT_CHAIN:
        return (-1).to_bytes(4, "little", signed=True)   # decline to chain
    if msg.id in (MSG_SELECT_CARD, MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD):
        sc = parse_select_card(msg.payload)
        n = max(sc.min, 1)
        return SelectCard.encode(list(range(n)))
    return (0).to_bytes(4, "little", signed=True)


def play(seed, deck, max_steps=200_000):
    """A duel is reproduced by (engine seed, shuffle seed). The shuffle seed is
    derived from the engine seed so callers only pass one thing around."""
    with Duel(seed) as d:
        d.load_deck(0, deck.main, deck.extra, shuffle_seed=seed[0])
        d.load_deck(1, deck.main, deck.extra, shuffle_seed=seed[1])
        d.start()
        return d.run(always_pass, max_steps=max_steps)


def main():
    deck = Deck.from_ydk("data/decks/sky_striker_pulp6.ydk")
    print(f"deck: {deck}")

    r = play(SEED, deck)
    print(f"\nsteps={r['steps']}  messages={r['message_count']}  "
          f"retries={r['retries']}  winner={r['winner']}")
    if r["missing_scripts"]:
        print(f"MISSING SCRIPTS: {r['missing_scripts'][:10]}")

    counts = Counter(m.id for m in r["messages"])
    print("\ntop messages:")
    for mid, n in counts.most_common(12):
        print(f"  {MSG_NAMES.get(mid, f'MSG_{mid}'):<26} {n}")

    # ---- determinism: same seed must produce a byte-identical message stream
    r2 = play(SEED, deck)
    s1 = b"".join(bytes([m.id]) + m.payload for m in r["messages"])
    s2 = b"".join(bytes([m.id]) + m.payload for m in r2["messages"])
    same_seed_identical = (s1 == s2)

    # ---- a different seed must produce a different duel
    r3 = play((1, 2, 3, 4), deck)
    s3 = b"".join(bytes([m.id]) + m.payload for m in r3["messages"])
    diff_seed_differs = (s1 != s3)

    print(f"\nsame seed  -> identical stream : {same_seed_identical} "
          f"({len(s1)} bytes)")
    print(f"diff seed  -> different stream : {diff_seed_differs} "
          f"({len(s3)} bytes)")

    ok = same_seed_identical and diff_seed_differs and not r["missing_scripts"]
    print(f"\n{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
