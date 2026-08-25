"""Minimal .ydk parsing. The format is line-based: #main / #extra / !side
sections containing one card code per line, repeated per copy."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Deck:
    main: list[int] = field(default_factory=list)
    extra: list[int] = field(default_factory=list)
    side: list[int] = field(default_factory=list)

    @classmethod
    def from_ydk(cls, path: str | Path) -> "Deck":
        deck, section = cls(), None
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("#main"):
                section = deck.main
            elif line.startswith("#extra"):
                section = deck.extra
            elif line.startswith("!side"):
                section = deck.side
            elif line.startswith("#"):
                continue          # comment / metadata
            elif section is not None and line.isdigit():
                section.append(int(line))
        return deck

    def __repr__(self) -> str:
        return f"Deck(main={len(self.main)}, extra={len(self.extra)}, side={len(self.side)})"
