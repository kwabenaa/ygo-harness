"""EDOPro puzzle scripts: locating them, reading their metadata, running them.

A puzzle is a Lua script that builds a fixed field through the core's `Debug`
library and then calls `aux.BeginPuzzle()`. That call is what makes puzzles
worth having: it registers an EVENT_TURN_END effect running
`Auxiliary.PuzzleOp`, which is `Duel.SetLP(0,0)` - fail to win during the turn
and you lose. So "solved" is the duel result, decided by the engine, with no
value function and no authored answer to diff against.

Loading one is not the deck path. `Debug.ReloadFieldBegin` calls
`pduel->clear()` and overwrites `duel_options` wholesale, and every puzzle
calls `Debug.SetPlayerInfo(player, lp, 0, 0)` - start count and draw count
zero - so the LP, ruleset and opening hand all come from the script. Anything
we pass to `Duel(...)` about those is dead. See `Duel.from_puzzle`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from engine.constants import (
    DEFAULT_PUZZLE_RULE,
    DUEL_MODE_RUSH,
    DUEL_MODE_SPEED,
    MASTER_RULES,
)
from engine import constants as K

#: Locations that exist only in the scripts' vocabulary, not in the C header.
#: libdebug.cpp folds both into LOCATION_SZONE when it places the card, so
#: they never appear in a query result - but they do appear in puzzle source,
#: and a parser that does not know them silently drops those cards.
LOCATION_FZONE = 0x100
LOCATION_PZONE = 0x200

_SCRIPT_NAMES = {
    "LOCATION_FZONE": LOCATION_FZONE,
    "LOCATION_PZONE": LOCATION_PZONE,
    # constant.lua's own name for the header's DUEL_1_FACEUP_FIELD; both 0x400.
    # The script vocabulary and the C header are not the same namespace.
    "DUEL_1_FIELD": K.DUEL_1_FACEUP_FIELD,
}

_RELOAD = re.compile(r"Debug\.ReloadFieldBegin\(([^)]*)\)")
_PLAYER_INFO = re.compile(r"Debug\.SetPlayerInfo\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)")
_ADD_CARD = re.compile(r"Debug\.AddCard\(([^)]*)\)")
_MESSAGE = re.compile(r"--\[\[message(.*?)\]\]", re.S)
_ORIGINAL_NAME = re.compile(r"^--\s*Original Puzzle Name:\s*(.+)$", re.M)
_OBJECTIVE = re.compile(r"^\s*(Objective:.*)$", re.M)


def _strip_comments(text: str) -> str:
    """Blank out Lua comments, preserving line structure.

    Several puzzles end with a commented-out cheat sheet of the Debug API
    (`--Debug.AddCard()`), and scanning raw text picks those up as real calls.
    Blanking rather than deleting keeps line numbers usable in error messages.
    """
    text = re.sub(r"--\[\[.*?\]\]", lambda m: "\n" * m.group(0).count("\n"),
                  text, flags=re.S)
    return re.sub(r"--[^\n]*", "", text)


def _resolve(token: str) -> int | None:
    """Resolve one Lua constant name or integer literal to its value."""
    token = token.strip()
    if not token:
        return None
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    if re.fullmatch(r"0x[0-9a-fA-F]+", token):
        return int(token, 16)
    if token in _SCRIPT_NAMES:
        return _SCRIPT_NAMES[token]
    val = getattr(K, token, None)
    return val if isinstance(val, int) else None


def _resolve_sum(expr: str) -> tuple[int, tuple[str, ...]]:
    """Resolve a `A+B+C` flag expression, reporting what it could not resolve.

    Unresolved names are returned rather than dropped: a flag we have never
    seen means the puzzle selects behaviour we are not modelling, and this
    codebase's failures are all of the shape "it quietly did nothing".
    """
    total, unknown = 0, []
    for part in re.split(r"[+|]", expr):
        part = part.strip()
        if not part:
            continue
        val = _resolve(part)
        if val is None:
            unknown.append(part)
        else:
            total |= val
    return total, tuple(unknown)


@dataclass(frozen=True)
class PuzzleCard:
    """One `Debug.AddCard(code, owner, playerid, location, sequence, position)`."""

    code: int
    owner: int
    player: int
    location: int
    sequence: int
    position: int


@dataclass
class Puzzle:
    path: Path
    source: bytes
    name: str
    message: str = ""
    objective: str = ""
    flags: int = 0
    flag_names: tuple[str, ...] = ()
    unknown_flags: tuple[str, ...] = ()
    rule: int = DEFAULT_PUZZLE_RULE
    lp: dict[int, int] = field(default_factory=dict)
    cards: tuple[PuzzleCard, ...] = ()
    #: Whether the script actually calls aux.BeginPuzzle().
    enforces_win_condition: bool = True
    #: AddCard lines we could not resolve. Never silently dropped: an
    #: unresolvable name means a card missing from our picture of the field
    #: while the engine places it regardless, which reads as the agent
    #: misplaying rather than as a parser bug.
    unparsed_cards: tuple[str, ...] = ()

    # ------------------------------------------------------------ parsing

    @classmethod
    def load(cls, path: str | Path) -> "Puzzle":
        path = Path(path)
        source = path.read_bytes()
        text = source.decode("utf-8", "replace")

        m = _ORIGINAL_NAME.search(text)
        name = m.group(1).strip() if m else path.stem

        msg = _MESSAGE.search(text)
        message = msg.group(1).strip() if msg else ""
        obj = _OBJECTIVE.search(message or text)

        code = _strip_comments(text)

        flags, flag_names, unknown, rule = 0, (), (), DEFAULT_PUZZLE_RULE
        reload = _RELOAD.search(code)
        if reload:
            args = reload.group(1).split(",")
            flags, unknown = _resolve_sum(args[0])
            flag_names = tuple(
                t.strip() for t in re.split(r"[+|]", args[0]) if t.strip()
            )
            if len(args) > 1 and args[1].strip().isdigit():
                rule = int(args[1].strip())

        lp = {int(p): int(v) for p, v, _s, _d in _PLAYER_INFO.findall(code)}

        enforced = "BeginPuzzle" in code
        cards, unparsed = [], []
        for raw in _ADD_CARD.findall(code):
            parts = [_resolve(a) for a in raw.split(",")]
            if len(parts) < 6 or any(p is None for p in parts[:6]):
                unparsed.append(raw.strip())
                continue
            cards.append(PuzzleCard(*parts[:6]))  # type: ignore[arg-type]

        return cls(
            path=path, source=source, name=name, message=message,
            objective=obj.group(1).strip() if obj else "",
            flags=flags, flag_names=flag_names, unknown_flags=unknown,
            rule=rule, lp=lp, cards=tuple(cards),
            enforces_win_condition=enforced,
            unparsed_cards=tuple(unparsed),
        )

    # ------------------------------------------------------------ traits

    @property
    def is_rush(self) -> bool:
        return bool(self.flags & DUEL_MODE_RUSH == DUEL_MODE_RUSH)

    @property
    def is_speed(self) -> bool:
        return bool(self.flags & DUEL_MODE_SPEED == DUEL_MODE_SPEED)

    @property
    def is_marathon(self) -> bool:
        """No aux.BeginPuzzle(), so nothing ends the duel at turn end.

        Seven playable puzzles comment the call out. Without it the engine
        never zeroes the solver's life points, so these are ordinary duels
        that happen to start from a fixed field - one of them puts the
        opponent on 9,999,999 LP and asks you to win outright. They run fine;
        they just cannot be judged by the one-turn rule, and a policy that
        does not win them exhausts the step cap rather than losing.
        """
        return not self.enforces_win_condition

    @property
    def is_tutorial(self) -> bool:
        return "Tutorials" in self.path.parts

    @property
    def ruleset_flags(self) -> int:
        """Flags the core will end up with, mirroring ReloadFieldBegin.

        libdebug ORs in the Master Rule preset only when the rule argument is
        non-zero; Rush puzzles pass 0 precisely to suppress it.
        """
        if self.rule:
            return self.flags | MASTER_RULES.get(self.rule, 0)
        return self.flags

    def skip_reason(self) -> str | None:
        """Why this puzzle is out of scope, or None if it should run."""
        if self.is_rush:
            return "rush"
        if self.unknown_flags:
            return f"unknown flags: {', '.join(self.unknown_flags)}"
        return None

    def declared_counts(self) -> dict[tuple[int, int], int]:
        """Cards this script declares, keyed by (player, location).

        Locations are normalised the way libdebug.cpp places them: both
        LOCATION_FZONE and LOCATION_PZONE are script-side names that the core
        resolves into a LOCATION_SZONE sequence, so a field spell counted as
        its own location would read as a missing spell/trap zone.

        The count is what the script *asks for*, which is not always what the
        field ends up holding: `Debug.AddCard` checks `is_location_useable`
        and returns silently when the zone is unavailable, so a puzzle that
        over-declares a location simply loses the surplus with no error.
        """
        out: dict[tuple[int, int], int] = {}
        for c in self.cards:
            loc = c.location
            if loc in (LOCATION_FZONE, LOCATION_PZONE):
                loc = K.LOCATION_SZONE
            out[(c.player, loc)] = out.get((c.player, loc), 0) + 1
        return out

    @property
    def field_is_fully_declared(self) -> bool:
        """Whether `cards` is the complete field the script builds.

        False when an AddCard uses a loop variable - a handful of puzzles
        place cards inside a `for` loop, which no static read can resolve.
        Those puzzles still run perfectly well; only a declared-vs-actual
        comparison of the field has to sit them out.
        """
        return not self.unparsed_cards

    def __repr__(self) -> str:
        return f"Puzzle({self.name!r}, MR{self.rule}, {len(self.cards)} cards)"


# ---------------------------------------------------------------- discovery

def find_pool() -> Path:
    """Locate the puzzle collection.

    Prefers our own pinned clone, because a benchmark that reads whatever the
    EDOPro install happens to hold today is not reproducible. Falls back to
    the install so the runner works before scripts/fetch_data.sh has been
    re-run.
    """
    root = Path(__file__).resolve().parent.parent
    pinned = root / "data" / "Puzzles"
    if pinned.is_dir():
        return pinned
    edopro = Path(
        os.environ.get("EDOPRO_DIR", Path.home() / "Applications" / "ProjectIgnis")
    ).expanduser()
    installed = edopro / "puzzles"
    if installed.is_dir():
        return installed
    raise FileNotFoundError(
        "no puzzle collection found - run scripts/fetch_data.sh, or install "
        "EDOPro and point EDOPRO_DIR at it"
    )


def iter_puzzles(root: str | Path | None = None):
    """Yield every puzzle under `root`, sorted, skipping the creator template."""
    root = Path(root) if root is not None else find_pool()
    for path in sorted(root.rglob("*.lua")):
        if path.name == "Puzzle Creator.lua":
            continue
        yield Puzzle.load(path)
