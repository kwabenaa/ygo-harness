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

Notation:
- M: monster zones, S: spell/trap zones.
- "Roze 1500 ATK" means face-up in attack position with 1500 ATK.
- "[set]" is a face-down card. "GY" is the graveyard.
"""


def card_corpus(db, codes: list[int]) -> str:
    """Card text for every card in the deck, sorted for a stable prefix.

    Sorted by code, not by deck order: prompt caching is a prefix match, so
    any reordering between duels would silently destroy the cache hit.
    """
    parts = []
    for code in sorted(set(codes)):
        name = db.name(code)
        text = db.text(code).replace("\r\n", "\n").strip()
        parts.append(f"### {name}\n{text}")
    return "\n\n".join(parts)


def system_prompt(db, deck_codes: list[int]) -> str:
    """The stable, cacheable half. Built once per duel, never rebuilt."""
    return (
        RULES_PRIMER
        + "\n\n## Cards in this matchup\n\n"
        + card_corpus(db, deck_codes)
    )


def decision_prompt(state_text: str, *, history: list[str] | None = None,
                    n_options: int | None = None) -> str:
    """The volatile half: what just happened, the board, and the options."""
    parts = []
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
