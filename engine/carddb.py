"""Card data + Lua script providers for ygopro-core.

The core ships no card data. It calls back into us for every card code it
encounters and every script it needs, which is exactly what lets a benchmark
pin its card pool by commit hash.
"""

from __future__ import annotations

import ctypes as C
import re
import sqlite3
from functools import lru_cache
from pathlib import Path

from .constants import TYPE_LINK
from .ocgapi import OCG_CardData

DATA = Path(__file__).parent.parent / "data"


class CardDB:
    """Reads card rows out of BabelCDB's sqlite databases.

    `setcodes` arrays are cached permanently rather than freed in
    cardReaderDone: the core may hold the pointer past the reader callback,
    and the deck only ever touches a few dozen codes, so leaking them is
    cheaper than getting the lifetime wrong.
    """

    #: Databases whose entries should win a name clash, in order. Everything
    #: else in BabelCDB is appended after these.
    PREFERRED = ("cards.cdb", "cards-unofficial.cdb")

    def __init__(self, cdbs: list[Path] | None = None):
        if cdbs is None:
            base = DATA / "BabelCDB"
            # Load every database, not a hand-picked pair. Two of thirteen
            # were loaded, so a puzzle using a pre-errata card - the GOAT
            # entries - showed the agent a bare passcode it then spent its
            # reasoning budget guessing at. Measured across the set: the ids
            # in the other databases do not overlap cards.cdb at all, so
            # loading them cannot shadow a current card. `row()` returns the
            # first match, and PREFERRED comes first regardless.
            ordered = [base / n for n in self.PREFERRED]
            ordered += sorted(p for p in base.glob("*.cdb")
                              if p.name not in self.PREFERRED)
            cdbs = ordered
        self.conns = [sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                      for p in cdbs if p.exists()]
        if not self.conns:
            raise FileNotFoundError("no card database - run scripts/fetch_data.sh")
        self._setcode_cache: dict[int, C.Array] = {}

    def row(self, code: int) -> tuple | None:
        for conn in self.conns:
            r = conn.execute(
                "select id, ot, alias, setcode, type, atk, def, level, race, attribute "
                "from datas where id = ?", (code,)
            ).fetchone()
            if r:
                return r
        return None

    @lru_cache(maxsize=None)
    def _archetype_names(self) -> dict[int, str]:
        """setcode -> archetype name, from CardScripts' own constants file.

        Read from pinned data rather than from EDOPro's strings.conf, which
        the install rewrites on launch (trap 11). Archetype membership is not
        cosmetic in this game - most card text refers to archetypes by name -
        so a card description that omits it is missing the thing that makes
        the card work with the rest of the field.
        """
        path = DATA / "CardScripts" / "archetype_setcode_constants.lua"
        out: dict[int, str] = {}
        if not path.exists():
            return out
        for m in re.finditer(r"^SET_([A-Z0-9_]+)\s*=\s*(0x[0-9a-fA-F]+)",
                             path.read_text(), re.M):
            name = m.group(1).replace("_", " ").title()
            out.setdefault(int(m.group(2), 16), name)
        return out

    def archetypes(self, code: int) -> list[str]:
        """Archetype names this card belongs to."""
        row = self.row(code)
        if row is None:
            return []
        names = self._archetype_names()
        out = []
        for i in range(4):
            sc = ((row[3] or 0) >> (16 * i)) & 0xFFFF
            if not sc:
                continue
            label = names.get(sc) or names.get(sc & 0xFFF)
            if label and label not in out:
                out.append(label)
        return out

    def all_rows(self):
        """Every card row across every attached database, deduplicated by id.

        Used to answer MSG_ANNOUNCE_CARD, which asks for *a card satisfying a
        filter* rather than a choice from a menu, so the pool has to be
        searched. Streams rather than materialising - the databases together
        hold well over ten thousand cards.
        """
        seen = set()
        for conn in self.conns:
            for r in conn.execute(
                "select id, ot, alias, setcode, type, atk, def, level, race, "
                "attribute from datas"
            ):
                if r[0] not in seen:
                    seen.add(r[0])
                    yield r

    @lru_cache(maxsize=None)
    def name(self, code: int) -> str:
        for conn in self.conns:
            r = conn.execute("select name from texts where id = ?", (code,)).fetchone()
            if r:
                return r[0]
        return f"<{code}>"

    @lru_cache(maxsize=None)
    def text(self, code: int) -> str:
        for conn in self.conns:
            r = conn.execute("select desc from texts where id = ?", (code,)).fetchone()
            if r:
                return r[0]
        return ""

    def _setcodes(self, code: int, packed: int) -> C.Array:
        """Unpack the 64-bit setcode column into a null-terminated uint16 array."""
        if code not in self._setcode_cache:
            vals = [(packed >> (16 * i)) & 0xFFFF for i in range(4)]
            vals = [v for v in vals if v] + [0]  # null terminator
            arr = (C.c_uint16 * len(vals))(*vals)
            self._setcode_cache[code] = arr
        return self._setcode_cache[code]

    def fill(self, code: int, out: OCG_CardData) -> None:
        """Populate an OCG_CardData for `code`. Zeroes it if the card is unknown."""
        r = self.row(code)
        if r is None:
            C.memset(C.byref(out), 0, C.sizeof(OCG_CardData))
            return
        _id, _ot, alias, setcode, type_, atk, def_, level, race, attribute = r

        out.code = code
        out.alias = alias or 0
        out.setcodes = self._setcodes(code, setcode or 0)
        out.type = type_ or 0
        out.attribute = attribute or 0
        out.race = race or 0
        out.attack = atk if atk is not None else 0

        # `level` packs pendulum scales into its upper bytes.
        lv = level or 0
        out.level = lv & 0xFF
        out.rscale = (lv >> 16) & 0xFF
        out.lscale = (lv >> 24) & 0xFF

        # Link monsters have no DEF; the column carries link markers instead.
        if type_ and (type_ & TYPE_LINK):
            out.defense = 0
            out.link_marker = def_ or 0
        else:
            out.defense = def_ if def_ is not None else 0
            out.link_marker = 0


class ScriptProvider:
    """Resolves script names the core asks for to files on disk.

    The core requests both card scripts (`c12345678.lua`) and shared library
    scripts (`constant.lua`, `utility.lua`, ...). Project Ignis splits these
    across several directories.
    """

    def __init__(self, root: Path | None = None):
        self.root = root or (DATA / "CardScripts")
        if not self.root.exists():
            raise FileNotFoundError(f"{self.root} - run scripts/fetch_data.sh")
        # Every subdirectory, discovered rather than listed. The hardcoded
        # list omitted goat/ (191 scripts), rush/ (3087) and skill/ (174), and
        # a card whose script is not found does not error - it simply has no
        # effects, which is trap 1 wearing a different hat.
        self.search_dirs = [self.root, self.root / "official"]
        self.search_dirs += sorted(
            d for d in self.root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
            and d not in self.search_dirs
        )
        self._index: dict[str, Path] | None = None

    def _build_index(self) -> dict[str, Path]:
        idx: dict[str, Path] = {}
        # Later dirs must not shadow earlier ones, so iterate in reverse.
        for d in reversed(self.search_dirs):
            if d.is_dir():
                for p in d.glob("*.lua"):
                    idx[p.name] = p
        return idx

    def read(self, name: str) -> bytes | None:
        if self._index is None:
            self._index = self._build_index()
        # The core passes paths like "./script/c123.lua"; only the leaf matters.
        p = self._index.get(Path(name).name)
        return p.read_bytes() if p else None
