"""Compact text rendering of a duel state, for the LLM prompt.

Two properties matter more than looks.

**Hidden information must stay hidden.** The query API will cheerfully hand you
the opponent's hand and their set cards. Rendering those would leak perfect
information into the agent's context and silently invalidate every result the
benchmark produces. Masking is therefore done here, once, and tested - never
left to the caller to remember.

**Terseness is a budget line.** This text is rebuilt at every decision point,
50-100 times per duel, so a wasted line costs real money at eval scale.
"""

from __future__ import annotations

from .board import Board, CardInfo, query_field, read_board

HIDDEN = "?"


def card_label(db, c: CardInfo | None, *, reveal: bool) -> str:
    """One card. `reveal=False` masks anything the viewer should not see."""
    if c is None:
        return "-"
    if c.face_down and not reveal:
        return "[set]"
    name = db.name(c.code) if c.code else HIDDEN
    if c.face_down:
        return f"[set: {name}]"
    return name


def monster_label(db, c: CardInfo | None, *, reveal: bool) -> str:
    """One monster, with its battle position stated explicitly.

    Position is not decoration in this game - a face-down monster cannot
    attack and has not had its effects applied, flip effects fire on being
    turned face-up, and plenty of card text keys off attack or defence
    position. This previously tested POS_FACEUP_DEFENSE alone, so a monster
    you had set face-down in defence was described to the agent as being in
    attack position.

    Both ATK and DEF are shown regardless of position, because effects that
    change position make the other number immediately relevant.
    """
    if c is None:
        return "-"
    if c.face_down and not reveal:
        return "[set]"
    name = db.name(c.code) if c.code else HIDDEN
    pos = "DEF" if c.defense_position else "ATK"
    if c.face_down:
        # Ours, so we may name it - but it is still face-down, which the
        # agent has to know before trying to attack with it.
        return f"[face-down {pos}: {name} {c.attack}/{c.defense}]"
    if c.is_link:
        return f"{name} {c.attack} ATK (Link)"
    return f"{name} {c.attack}/{c.defense} {pos}"


def _row(labels: list[str]) -> str:
    kept = [x for x in labels if x != "-"]
    return "  ".join(kept) if kept else "empty"


def render_side(db, b: Board, *, viewer: int, label: str) -> list[str]:
    """Render one player's side. `viewer` decides what is masked."""
    own = (b.player == viewer)
    lines = [
        f"{label}  M: {_row([monster_label(db, c, reveal=own) for c in b.monsters])}",
        f"{' ' * len(label)}  S: {_row([card_label(db, c, reveal=own) for c in b.spells])}",
    ]
    pad = " " * len(label)
    if own:
        hand = "  ".join(db.name(c.code) for c in b.hand if c) or "empty"
        lines.append(f"{pad}  Hand ({len(b.hand)}): {hand}")
    else:
        # Count only - never the contents.
        lines.append(f"{pad}  Hand: {len(b.hand)} cards")
    gy = [c for c in b.grave if c]
    if gy:
        lines.append(f"{pad}  GY ({len(gy)}): "
                     + "  ".join(db.name(c.code) for c in gy[-6:]))
    lines.append(f"{pad}  Deck: {b.deck_count}  Extra: {b.extra_count}")
    return lines


def render_state(duel, db, viewer: int, *, turn: int | None = None,
                 phase: str | None = None, lp: tuple[int, int] | None = None) -> str:
    """Full board from `viewer`'s perspective, with hidden info masked."""
    me = read_board(duel, viewer)
    opp = read_board(duel, 1 - viewer)
    head = []
    if turn is not None:
        head.append(f"Turn {turn}")
    if phase:
        head.append(phase)
    if lp is None:
        fi = query_field(duel)
        lp = fi.lp if fi else None
    if lp:
        head.append(f"LP you {lp[viewer]} / opp {lp[1 - viewer]}")
    lines = [" | ".join(head)] if head else []
    lines += render_side(db, me, viewer=viewer, label="YOU")
    lines += render_side(db, opp, viewer=viewer, label="OPP")
    return "\n".join(lines)


def render_actions(db, cmd, names: dict | None = None) -> str:
    """The legal-action menu, numbered.

    This is the half of the prompt that makes an illegal move impossible: the
    agent returns an index into this list, so there is no channel through
    which an invalid action could be expressed.
    """
    from .messages import IDLE_NAMES

    table = names if names is not None else IDLE_NAMES
    lines = []
    for i, (kind, idx, card) in enumerate(cmd.actions()):
        verb = table.get(kind, "choose" if kind == 99 else str(kind))
        if card is None:
            lines.append(f"  {i:>2}) {verb}")
        else:
            lines.append(f"  {i:>2}) {verb}: {db.name(card.code)}")
    return "\n".join(lines) if lines else "  (no legal actions)"


def render_decision(duel, db, cmd, viewer: int, *, turn: int | None = None) -> str:
    """The complete prompt body for one decision point: state, then options."""
    return (
        render_state(duel, db, viewer, turn=turn)
        + "\nACTIONS\n"
        + render_actions(db, cmd)
    )
