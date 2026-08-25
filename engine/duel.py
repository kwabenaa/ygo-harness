"""Duel lifecycle: create, seed, load a deck, and run the message/response loop.

Determinism is the load-bearing property here. A duel is fully described by
(seed, ordered response log) - which is also exactly what a .yrp replay file
is, and why replay-based state restore works for search.
"""

from __future__ import annotations

import ctypes as C
import random
import struct
from dataclasses import dataclass, field
from pathlib import Path

from . import ocgapi as api
from .carddb import CardDB, ScriptProvider
from .constants import (
    DECISION_MESSAGES, LOCATION_DECK, LOCATION_EXTRA, MASTER_RULE_5,
    MSG_NAMES, MSG_RETRY, MSG_WIN, POS_FACEDOWN_DEFENSE,
)


@dataclass
class Message:
    """One decoded-at-the-boundary engine message: id plus its raw payload."""
    id: int
    payload: bytes

    @property
    def name(self) -> str:
        return MSG_NAMES.get(self.id, f"MSG_{self.id}")

    def __repr__(self) -> str:
        return f"<{self.name} {len(self.payload)}B>"


class Duel:
    """A single duel instance bound to one ygopro-core duel handle."""

    def __init__(
        self,
        seed: tuple[int, int, int, int],
        *,
        lib: C.CDLL | None = None,
        carddb: CardDB | None = None,
        scripts: ScriptProvider | None = None,
        flags: int = MASTER_RULE_5,
        starting_lp: int = 8000,
        starting_draw: int = 5,
        draw_per_turn: int = 1,
    ):
        self.lib = lib or api.load()
        self.db = carddb or CardDB()
        self.scripts = scripts or ScriptProvider()
        self.seed = seed
        self.responses: list[bytes] = []
        self.log: list[str] = []
        self.missing_scripts: set[str] = set()

        opts = api.OCG_DuelOptions()
        C.memset(C.byref(opts), 0, C.sizeof(api.OCG_DuelOptions))
        for i, s in enumerate(seed):
            opts.seed[i] = s
        opts.flags = flags
        for team in (opts.team1, opts.team2):
            team.startingLP = starting_lp
            team.startingDrawCount = starting_draw
            team.drawCountPerTurn = draw_per_turn

        # These trampolines MUST be kept alive for the duel's lifetime: ctypes
        # does not retain them, and the core will call into freed memory if
        # they are collected.
        self._cb_card = api.OCG_DataReader(self._on_card)
        self._cb_script = api.OCG_ScriptReader(self._on_script)
        self._cb_log = api.OCG_LogHandler(self._on_log)
        opts.cardReader = self._cb_card
        opts.scriptReader = self._cb_script
        opts.logHandler = self._cb_log

        handle = C.c_void_p()
        rc = self.lib.OCG_CreateDuel(C.byref(handle), C.byref(opts))
        if rc != api.DuelCreation.SUCCESS:
            raise RuntimeError(f"OCG_CreateDuel failed: status {rc}")
        self.handle = handle

    # ------------------------------------------------------------ callbacks

    def _on_card(self, payload, code, data_ptr):
        self.db.fill(code, data_ptr.contents)

    def _on_script(self, payload, duel, name):
        fname = name.decode("utf-8", "replace")
        body = self.scripts.read(fname)
        if body is None:
            # c0.lua is a sentinel the core probes for (card code 0), not a
            # real card - recording it as missing is a false positive.
            if fname not in ("c0.lua", "./c0.lua"):
                self.missing_scripts.add(fname)
            return 0
        return self.lib.OCG_LoadScript(self.handle, body, len(body), name)

    def _on_log(self, payload, msg, log_type):
        self.log.append(f"[{log_type}] {msg.decode('utf-8', 'replace')}")

    # ------------------------------------------------------------ setup

    def add_card(self, code: int, team: int, loc: int, seq: int = 0,
                 pos: int = POS_FACEDOWN_DEFENSE) -> None:
        info = api.OCG_NewCardInfo(
            team=team, duelist=0, code=code, con=team, loc=loc, seq=seq, pos=pos
        )
        self.lib.OCG_DuelNewCard(self.handle, C.byref(info))

    def load_deck(self, team: int, main: list[int], extra: list[int],
                  shuffle_seed: int | None = None) -> None:
        """Load a deck for `team`, shuffling the main deck ourselves.

        ygopro-core does NOT shuffle at startup - Processors::Startup just
        draws start_count cards off the back of the main list. Shuffling is
        the client's job, which is why reproducing a duel needs two seeds:
        this one for the deal, and the engine's seed[4] for in-duel randomness.

        A consequence worth keeping: because the deal is ours, a specific
        opening hand can be dealt exactly by ordering the list, which is what
        sealed benchmark hands require. The engine draws from the END of the
        list, so the last `start_count` codes are the opening hand.
        """
        order = list(main)
        if shuffle_seed is not None:
            random.Random(shuffle_seed).shuffle(order)
        for code in order:
            self.add_card(code, team, LOCATION_DECK)
        for code in extra:
            self.add_card(code, team, LOCATION_EXTRA)

    def start(self) -> None:
        self.lib.OCG_StartDuel(self.handle)

    # ------------------------------------------------------------ loop

    def _messages(self) -> list[Message]:
        length = C.c_uint32(0)
        buf = self.lib.OCG_DuelGetMessage(self.handle, C.byref(length))
        if not buf or length.value == 0:
            return []
        raw = C.string_at(buf, length.value)
        out, off = [], 0
        # Each message is a uint32 length followed by that many bytes, the
        # first of which is the message id.
        while off + 4 <= len(raw):
            (mlen,) = struct.unpack_from("<I", raw, off)
            off += 4
            if mlen == 0 or off + mlen > len(raw):
                break
            out.append(Message(raw[off], raw[off + 1:off + mlen]))
            off += mlen
        return out

    def respond(self, data: bytes) -> None:
        self.responses.append(data)
        self.lib.OCG_DuelSetResponse(self.handle, data, len(data))

    def respond_int(self, value: int) -> None:
        self.respond(struct.pack("<i", value))

    def run(self, policy, max_steps: int = 100_000,
            retry_limit: int = 32) -> dict:
        """Drive the duel to completion.

        `policy(msg, duel) -> bytes` answers every decision point.

        The pending decision is tracked *across* iterations: when a response
        is rejected the engine emits MSG_RETRY on its own, with no restatement
        of the question, so a loop that only looks at the current batch loses
        track of what was being asked and answers into the void forever.
        """
        seen: list[Message] = []
        pending: Message | None = None
        retries = consecutive = steps = 0
        winner = None

        while steps < max_steps:
            steps += 1
            status = self.lib.OCG_DuelProcess(self.handle)
            msgs = self._messages()
            seen.extend(msgs)

            saw_retry = False
            for m in msgs:
                if m.id == MSG_RETRY:
                    saw_retry = True
                    retries += 1
                elif m.id == MSG_WIN and len(m.payload) >= 1:
                    winner = m.payload[0]

            new_decision = next(
                (m for m in reversed(msgs) if m.id in DECISION_MESSAGES), None
            )
            if new_decision is not None:
                pending = new_decision
                consecutive = 0
            elif saw_retry:
                consecutive += 1
                if consecutive > retry_limit:
                    raise RuntimeError(
                        f"policy rejected {consecutive}x on "
                        f"{pending.name if pending else 'unknown'} - "
                        f"response format is wrong"
                    )

            if winner is not None or status == api.DuelStatus.END:
                break
            if status == api.DuelStatus.AWAITING:
                self.respond(policy(pending, self))

        return {
            "steps": steps,
            "messages": seen,
            "message_count": len(seen),
            "retries": retries,
            "winner": winner,
            "responses": list(self.responses),
            "missing_scripts": sorted(self.missing_scripts),
        }

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.lib.OCG_DestroyDuel(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
