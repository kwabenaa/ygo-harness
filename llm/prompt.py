"""Prompt construction, split along the caching boundary.

Measured cost structure for one decision point on the Sky Striker deck:

    card text for 36 distinct cards   ~3,600 tokens   stable, cacheable
    rules primer                        ~400 tokens   stable, cacheable
    board state + action menu           ~170 tokens   volatile
    model reasoning + answer            ~600 tokens   volatile, billed as output

So roughly 83% of the per-decision cost is the model's own output. Board
verbosity is close to free; reasoning length is the dial that matters. That is
the opposite of what the plan assumed, and it is why the stable half is built
once per duel and never rebuilt.
"""

from __future__ import annotations

from engine import constants as K

RULES_PRIMER = """\
You are playing Yu-Gi-Oh (Master Rule 5) through a rules engine.

How this works:
- You will be shown the board and a numbered list of LEGAL ACTIONS.
- Reply with the number of the action you choose. Nothing else is accepted.
- Every listed action is legal. You cannot make an illegal move, so do not
  hedge about legality - choose the best option.
- The engine resolves each action and tells you what happened, including
  whether your opponent responded. Then you choose again.

What you cannot see:
- Your opponent's hand (only its size) and the contents of their set cards.
- Face-down cards shown as [set] are unknown to you. Yours are named.

The structure of a turn, which is one-way:

    Draw -> Standby -> MAIN PHASE 1 -> BATTLE PHASE -> MAIN PHASE 2 -> End

- The board tells you which phase you are in. Read it before planning.
- You may only declare attacks during the BATTLE PHASE. Once you leave it for
  Main Phase 2 the Battle Phase is over for the turn and cannot be re-entered.
  There is no second Battle Phase.
- So anything you want to attack with must already be on the field when you
  enter the Battle Phase. "Go to Main Phase 2, summon a monster, then attack
  with it" is impossible - a mistake that costs the whole turn.
- You may Normal Summon or Set at most once per turn, and only during a Main
  Phase. Some cards forbid Normal Summoning for the rest of the turn as a cost
  of their own effect; the action menu is the authority on what you may
  actually still do.
- Special Summons are separate from your one Normal Summon and are governed by
  each card's own text.

Notation:
- M: monster zones, S: spell/trap zones.
- "Roze 1500/1500 ATK" is face-up in ATTACK position, 1500 ATK / 1500 DEF.
- "Roze 1500/1500 DEF" is the same card face-up in DEFENCE position.
- "[face-down DEF: Roze 1500/1500]" is yours, set face-down in defence. A
  face-down monster cannot attack and its effects are not applied until it
  is turned face-up.
- "[set]" is a face-down card of your opponent's - you cannot see what it is.
- Battle position matters beyond combat: many effects can only be activated
  by, or can only target, a monster in a particular position.
- "GY" is the graveyard.

The field, and why zones matter:
- Each side has 5 main monster zones [0]..[4], plus two shared Extra Monster
  Zones shown as [EM-L] and [EM-R]. Extra Deck monsters normally arrive in an
  Extra Monster Zone or in a zone a Link monster points to.
- Spell/trap zones are [0]..[4], with [Field] for the Field Zone.
- Every zone is shown even when empty, so you always know what is free.
- Columns matter. Your zone [0] is in the same column as your opponent's
  zone [4], your [1] with their [3], and so on - your zone N faces their
  zone 4-N. [EM-L] sits in column 1 and [EM-R] in column 3.
- When you are asked where to place a card, the choice is real: Link markers
  point at specific zones, and some effects only apply to cards in a
  particular column or zone. Do not treat placement as arbitrary.
"""


#: Type bits that name a card, in the order a real card prints them.
_TYPE_LABELS = [
    (K.TYPE_RITUAL, "Ritual"), (K.TYPE_FUSION, "Fusion"),
    (K.TYPE_SYNCHRO, "Synchro"), (K.TYPE_XYZ, "Xyz"), (K.TYPE_LINK, "Link"),
    (K.TYPE_PENDULUM, "Pendulum"), (K.TYPE_TUNER, "Tuner"),
    (K.TYPE_SPIRIT, "Spirit"), (K.TYPE_UNION, "Union"), (K.TYPE_GEMINI, "Gemini"),
    (K.TYPE_TOON, "Toon"), (K.TYPE_FLIP, "Flip"), (K.TYPE_TOKEN, "Token"),
    (K.TYPE_NORMAL, "Normal"), (K.TYPE_EFFECT, "Effect"),
    (K.TYPE_SPSUMMON, "Special Summon"),
]
_SPELL_TRAP_LABELS = [
    (K.TYPE_QUICKPLAY, "Quick-Play"), (K.TYPE_CONTINUOUS, "Continuous"),
    (K.TYPE_EQUIP, "Equip"), (K.TYPE_FIELD, "Field"),
    (K.TYPE_COUNTER, "Counter"), (K.TYPE_RITUAL, "Ritual"),
]
_ATTRIBUTES = [
    (K.ATTRIBUTE_EARTH, "EARTH"), (K.ATTRIBUTE_WATER, "WATER"),
    (K.ATTRIBUTE_FIRE, "FIRE"), (K.ATTRIBUTE_WIND, "WIND"),
    (K.ATTRIBUTE_LIGHT, "LIGHT"), (K.ATTRIBUTE_DARK, "DARK"),
    (K.ATTRIBUTE_DIVINE, "DIVINE"),
]
#: Octal in the C header - 0010 is 8, not 10 (trap 7).
_LINK_MARKERS = [
    (K.LINK_MARKER_TOP_LEFT, "TL"), (K.LINK_MARKER_TOP, "T"),
    (K.LINK_MARKER_TOP_RIGHT, "TR"), (K.LINK_MARKER_LEFT, "L"),
    (K.LINK_MARKER_RIGHT, "R"), (K.LINK_MARKER_BOTTOM_LEFT, "BL"),
    (K.LINK_MARKER_BOTTOM, "B"), (K.LINK_MARKER_BOTTOM_RIGHT, "BR"),
]


def _race_name(race: int) -> str:
    for name, val in vars(K).items():
        if name.startswith("RACE_") and isinstance(val, int) and val == race:
            return name[5:].replace("_", "-").title()
    return "?"


def _stat_line(db, code: int) -> str:
    """The printed face of a card: everything but the artwork.

    Without this the model saw a name and a paragraph of effect text, and had
    to infer levels, ranks, Link ratings, ATK and attributes from prose - or
    from memory of a card it may never have seen. Material requirements are
    arithmetic over exactly these numbers, so a puzzle that needs a Rank 4 or
    a Link-3 was being guessed at.
    """
    row = db.row(code)
    if row is None:
        return ""
    _id, _ot, _alias, _setcode, ctype, atk, def_, level, race, attribute = row
    ctype, level = ctype or 0, level or 0

    def value(v):
        return "?" if v is not None and v < 0 else str(v or 0)

    bits = []
    if ctype & K.TYPE_MONSTER:
        attr = next((n for b, n in _ATTRIBUTES if attribute and attribute & b), "?")
        bits.append(attr)
        bits.append(_race_name(race or 0))
        if ctype & K.TYPE_LINK:
            bits.append(f"Link-{level & 0xFF}")
            bits.append(f"{value(atk)} ATK")
            marks = [n for b, n in _LINK_MARKERS if (def_ or 0) & b]
            if marks:
                bits.append("markers " + "/".join(marks))
        else:
            rank = "Rank" if ctype & K.TYPE_XYZ else "Level"
            bits.append(f"{rank} {level & 0xFF}")
            bits.append(f"{value(atk)} ATK / {value(def_)} DEF")
        if ctype & K.TYPE_PENDULUM:
            bits.append(f"Pendulum Scale {(level >> 24) & 0xFF}")
        kinds = [n for b, n in _TYPE_LABELS if ctype & b]
        bits.append(" ".join(kinds + ["Monster"]))
    else:
        kind = "Spell" if ctype & K.TYPE_SPELL else "Trap"
        sub = [n for b, n in _SPELL_TRAP_LABELS if ctype & b] or ["Normal"]
        bits.append(f"{' '.join(sub)} {kind}")

    sets = db.archetypes(code)
    if sets:
        bits.append("archetype: " + ", ".join(sets))
    return " | ".join(b for b in bits if b)


def card_corpus(db, codes: list[int]) -> str:
    """Everything about every card in play except the artwork.

    Sorted by code, not by deck order: prompt caching is a prefix match, so
    any reordering between duels would silently destroy the cache hit.
    """
    parts = []
    for code in sorted(set(codes)):
        name = db.name(code)
        text = db.text(code).replace("\r\n", "\n").strip()
        stats = _stat_line(db, code)
        head = f"### {name}\n{stats}" if stats else f"### {name}"
        parts.append(f"{head}\n{text}")
    return "\n\n".join(parts)


def system_prompt(db, deck_codes: list[int]) -> str:
    """The stable, cacheable half. Built once per duel, never rebuilt."""
    return (
        RULES_PRIMER
        + "\n\n## Cards in this matchup\n\n"
        + card_corpus(db, deck_codes)
    )


PLAN_REQUEST = """\
Before choosing any action, work out the whole line.

You are looking for a sequence that wins THIS TURN. Think about which cards
combine, what each summon enables, and where the damage finally comes from.
Count the damage: say how the opponent's life total reaches zero.

Answer with a short numbered list of the steps you intend to take, then a
final line beginning "DAMAGE:" showing the arithmetic. If you cannot find a
winning line, say so and give the best attempt you can.

Do not choose an action yet. This is the plan only."""


def plan_prompt(state_text: str, objective: str = "") -> str:
    """Ask for a full line to lethal, once, before the first action.

    A policy asked only "which of these options" re-derives its intentions
    from the board at every step, and a combo is precisely the thing that
    cannot be re-derived one decision at a time - step three looks pointless
    unless you already know steps four and five. This buys one long think and
    then holds the result, rather than paying for shallow thinking repeatedly.
    """
    goal = f"\nObjective: {objective}\n" if objective else ""
    return f"{state_text}\n{goal}\n{PLAN_REQUEST}"


def decision_prompt(state_text: str, *, history: list[str] | None = None,
                    n_options: int | None = None, plan: str = "") -> str:
    """The volatile half: the plan, what just happened, the board, options."""
    parts = []
    if plan:
        parts.append(
            "YOUR PLAN FOR THIS TURN (you wrote this before acting; follow it "
            "unless the board now makes a step impossible)\n" + plan)
    if history:
        parts.append("RECENT EVENTS\n" + "\n".join(f"  {h}" for h in history[-8:]))
    parts.append(state_text)
    if n_options:
        # Stating the range explicitly: models otherwise return indices past
        # the end of the menu, which costs a wasted call and a fallback.
        parts.append(f"Reply with only a number from 0 to {n_options - 1}.")
    else:
        parts.append("Reply with only the number of your chosen action.")
    return "\n\n".join(parts)


PUZZLE_PRIMER = """\
This is a Yu-Gi-Oh PUZZLE, not a normal duel. Read this carefully - it changes
what a good move is.

- The board and both hands are FIXED. Nothing was drawn and nothing is random.
- You must WIN THIS TURN. At the end of this turn you automatically lose, so
  passing, setting up for later, or preserving resources is always wrong.
- There is a solution. Every card on the field and in your hand is there for a
  reason; a line that leaves cards unused is usually the wrong line.
- Spend everything. Life points, materials, and cards in hand have no value
  after this turn.
- Your opponent will not meaningfully act. Play as if uninterrupted.
"""


def puzzle_system_prompt(db, codes: list[int], objective: str = "") -> str:
    """The stable half for a puzzle: rules, the puzzle framing, card text.

    Same caching argument as `system_prompt` - built once per puzzle and never
    rebuilt - but the goal is different enough that reusing the duel primer
    would actively mislead. A duel rewards banking resources; a puzzle
    punishes it, because the turn ends in a loss.
    """
    goal = f"\nYour objective: {objective}\n" if objective else ""
    return (
        RULES_PRIMER
        + "\n\n## This is a puzzle\n\n"
        + PUZZLE_PRIMER
        + goal
        + "\n## Cards in this puzzle\n\n"
        + card_corpus(db, codes)
    )
