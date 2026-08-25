"""Duel lifecycle: create, seed, load a deck, and run the message/response loop.

Determinism is the load-bearing property here. A duel is fully described by
(seed, ordered response log) - which is also exactly what a .yrp replay file
is, and why replay-based state restore works for search.
"""

from __future__ import annotations

import ctypes as C
import random
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path

from . import ocgapi as api
from .carddb import CardDB, ScriptProvider
from .constants import (
    DECISION_MESSAGES, LOCATION_DECK, LOCATION_EXTRA, MASTER_RULE_5,
    MSG_CHAINING, MSG_CHAIN_END, MSG_NAMES, MSG_NEW_PHASE, MSG_NEW_TURN,
    MSG_RETRY, MSG_WIN,
    POS_FACEDOWN_DEFENSE, TYPE_NORMAL,
)


@dataclass
class Message:
    """One decoded-at-the-boundary engine message: id plus its raw payload."""
    id: int
    payload: bytes

    @property
    def name(self) -> str:
        return MSG_NAMES.get(self.id, f"MSG_{self.id}")

    @property
    def player(self) -> int | None:
        """Whose decision this is.

        Every MSG_SELECT_* writes playerid as the first payload byte
        (playerop.cpp), which is what lets one duel run two different
        policies - needed for any agent-vs-baseline match.
        """
        if self.id in DECISION_MESSAGES and self.payload:
            v = self.payload[0]
            return v if v in (0, 1) else None
        return None

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
        load_globals: bool = True,
    ):
        self.lib = lib or api.load()
        self.db = carddb or CardDB()
        self.scripts = scripts or ScriptProvider()
        self.seed = seed
        self.responses: list[bytes] = []
        #: Decks in *dealt* order, per player. The engine does not shuffle -
        #: we do - so this, not the .ydk, is what reproduces the duel and what
        #: a .yrp replay must record.
        self.dealt: list[tuple[list[int], list[int]]] = []
        self.flags = flags
        self.starting_lp = starting_lp
        self.starting_draw = starting_draw
        self.draw_per_turn = draw_per_turn
        #: Messages emitted since the last OCG_DuelProcess.
        self.last_batch: list[Message] = []
        #: Messages since the last decision point.
        self.since_last_decision: list[Message] = []
        #: Monotonic counters. A policy that wants to act on "a new turn
        #: started" or "the opponent chained" must compare these against the
        #: value it last saw, rather than scanning a buffer: OCG_DuelProcess
        #: emits those messages in an earlier batch than the decision they
        #: precede, and any intervening decision (a draw-phase chain window,
        #: say) clears the buffer before the decision that cared about it.
        self.turn_count = 0
        self.chain_count = 0
        self.chain_end_count = 0
        #: Whose turn it currently is (MSG_NEW_TURN payload is the turn player).
        self.turn_player: int | None = None
        #: Current phase, from MSG_NEW_PHASE. Tracked because nothing else
        #: reports it: the query API describes the field, not where in the
        #: turn we are, and an agent left to infer the phase from the shape of
        #: its action menu will get it wrong.
        self.phase: int | None = None
        #: Player who activated the most recent chain link.
        self.last_chain_player: int | None = None
        self.log: list[str] = []
        self.missing_scripts: set[str] = set()
        #: Set by from_puzzle/load_puzzle; None for an ordinary deck duel.
        self.puzzle = None

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
        if load_globals:
            self.load_globals()

    # ------------------------------------------------------------ callbacks

    def _on_card(self, payload, code, data_ptr):
        self.db.fill(code, data_ptr.contents)

    def _on_script(self, payload, duel, name):
        fname = name.decode("utf-8", "replace")
        body = self.scripts.read(fname)
        if body is None:
            if self._script_absence_is_notable(fname):
                self.missing_scripts.add(fname)
            return 0
        return self.lib.OCG_LoadScript(self.handle, body, len(body), name)

    def _script_absence_is_notable(self, fname: str) -> bool:
        """Whether a script the core could not find is actually a problem.

        Two cases are normal and must not be reported, or the real signal - a
        card silently left with no effects, which is trap 1 - drowns in noise:

        - `c0.lua`, a sentinel the core probes for card code 0.
        - Vanilla monsters. A Normal monster has no script in CardScripts at
          all, so the core asks, gets nothing, and is perfectly correct. Every
          "missing" script in the first puzzle run was one of these: Blue-Eyes
          White Dragon, Dark Magician, Mokey Mokey.
        """
        stem = Path(fname).name
        if stem == "c0.lua":
            return False
        m = re.fullmatch(r"c(\d+)\.lua", stem)
        if not m:
            return True
        row = self.db.row(int(m.group(1)))
        if row is None:
            return True
        return not (row[4] & TYPE_NORMAL)

    def _on_log(self, payload, msg, log_type):
        self.log.append(f"[{log_type}] {msg.decode('utf-8', 'replace')}")

    # ------------------------------------------------------------ setup

    #: Shared library scripts, in dependency order. The core never asks for
    #: these - it only requests cXXXXXXX.lua on demand - so the host must load
    #: them itself. They cascade: constant.lua pulls in the counter and
    #: setcode tables, utility.lua pulls in every proc_*.lua.
    GLOBAL_SCRIPTS = ("constant.lua", "utility.lua")

    def load_globals(self) -> None:
        """Load the shared scripts that every card script depends on.

        Without these, every card's `local s,id=GetID()` fails with
        "attempt to call a nil value (global 'GetID')" and the card ends up
        with no effects at all. The duel still runs - cards can be summoned
        and set, because those are rules actions - so the failure looks like
        a game where nothing has an ability rather than like an error.
        Must run before any card is created: initial_effect fires inside
        OCG_DuelNewCard.
        """
        for name in self.GLOBAL_SCRIPTS:
            body = self.scripts.read(name)
            if body is None:
                raise FileNotFoundError(
                    f"global script {name} not found - run scripts/fetch_data.sh"
                )
            if not self.lib.OCG_LoadScript(self.handle, body, len(body),
                                           name.encode()):
                raise RuntimeError(f"OCG_LoadScript failed for {name}")

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
        while len(self.dealt) <= team:
            self.dealt.append(([], []))
        self.dealt[team] = (list(order), list(extra))

    # ------------------------------------------------------------ puzzles

    #: Any fixed non-zero seed. OCG_CreateDuel rejects an all-zero seed with
    #: NULL_RNG_SEED, and a puzzle's field is authored rather than dealt, so
    #: the value only matters for in-duel randomness - which most puzzles
    #: suppress anyway with DUEL_PSEUDO_SHUFFLE.
    PUZZLE_SEED = (1, 7, 13, 29)

    @classmethod
    def from_puzzle(cls, puzzle, *, seed: tuple[int, int, int, int] | None = None,
                    **kwargs) -> "Duel":
        """Build a duel whose field comes from an EDOPro puzzle script.

        Deliberately not the deck path. `Debug.ReloadFieldBegin` calls
        `pduel->clear()` and assigns `duel_options` outright, and every puzzle
        calls `Debug.SetPlayerInfo(p, lp, 0, 0)`, so the script decides the
        ruleset, the life points and - with start count zero - the fact that
        OCG_StartDuel draws nothing. Passing our own flags/LP/draw counts here
        would be inert at best and misleading to read, so they are forced to
        zero and the script is left to set them.

        Order matters and is not interchangeable: the globals must be loaded
        before the puzzle, because the puzzle's top-level Lua runs during
        OCG_LoadScript and immediately creates cards, and a card created
        before utility.lua exists has no effects at all (see trap 1).
        """
        seed = seed or cls.PUZZLE_SEED
        kwargs.pop("flags", None)
        kwargs.pop("starting_lp", None)
        kwargs.pop("starting_draw", None)
        kwargs.pop("draw_per_turn", None)
        duel = cls(seed, flags=0, starting_lp=0, starting_draw=0,
                   draw_per_turn=0, **kwargs)
        duel.load_puzzle(puzzle)
        return duel

    def load_puzzle(self, puzzle) -> None:
        """Run a puzzle script, building its field. Must precede start()."""
        name = puzzle.path.name.encode("utf-8", "replace")
        if not self.lib.OCG_LoadScript(self.handle, puzzle.source,
                                       len(puzzle.source), name):
            raise RuntimeError(
                f"OCG_LoadScript failed for puzzle {puzzle.path.name}: "
                + "; ".join(self.log[-3:] or ["no core log output"])
            )
        self.puzzle = puzzle

    # ------------------------------------------------------------ start

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
            retry_limit: int = 32, policy1=None) -> dict:
        """Drive the duel to completion.

        `policy(msg, duel) -> bytes` answers every decision point. If
        `policy1` is given, `policy` answers for player 0 and `policy1` for
        player 1, which is how an agent is matched against a baseline.

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
            self.last_batch = msgs
            self.since_last_decision.extend(msgs)
            seen.extend(msgs)
            for m in msgs:
                if m.id == MSG_NEW_TURN:
                    self.turn_count += 1
                    if m.payload:
                        self.turn_player = m.payload[0]
                elif m.id == MSG_NEW_PHASE and len(m.payload) >= 2:
                    (self.phase,) = struct.unpack_from("<H", m.payload, 0)
                elif m.id == MSG_CHAINING:
                    self.chain_count += 1
                    # code (4 bytes), then a loc_info whose first byte is the
                    # handler's controller - i.e. who activated.
                    if len(m.payload) > 4:
                        self.last_chain_player = m.payload[4]
                elif m.id == MSG_CHAIN_END:
                    self.chain_end_count += 1

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
                # The engine is blocked on an answer. If this batch said
                # something but none of it was a decision we recognise, the
                # question is one we cannot see - and `pending` still holds
                # the *previous* question, so answering now replies to
                # something the engine already moved past. That presents as an
                # endless MSG_RETRY loop attributed to the wrong message,
                # which is how four missing decision types stayed hidden.
                if msgs and new_decision is None and not saw_retry:
                    ids = ", ".join(
                        f"{MSG_NAMES.get(m.id, m.id)}({m.id})" for m in msgs
                    )
                    raise RuntimeError(
                        f"engine is awaiting a response but this batch held no "
                        f"decision we know: [{ids}]. Add it to "
                        f"DECISION_MESSAGES and give it a decoder."
                    )
                who = pending.player if pending is not None else None
                active = policy1 if (policy1 is not None and who == 1) else policy
                response = active(pending, self)
                self.since_last_decision = []
                self.respond(response)

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
