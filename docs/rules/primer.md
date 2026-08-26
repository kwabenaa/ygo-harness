# The rules primer the agent is given

This is the operative text — `llm/prompt.py:RULES_PRIMER` holds the copy that
actually ships, and this file exists so it can be read and argued with without
opening the code. **If they drift, `llm/prompt.py` wins.**

Every line here was added because the agent got something wrong without it.
That is the bar for adding another: a rule earns its tokens by having caused a
measured failure, not by being true. The primer sits in the cached prefix, so
it is paid for once per puzzle rather than per decision - but it is still
context the model has to read past on every call.

## Provenance

Written from the official rulebook (`rulebook.md` in this directory), checked
against `vendor/ygopro-core` where the two could disagree. The engine is the
tiebreaker: it is what actually adjudicates the duel. For example the Tribute
thresholds below are the rulebook's, and `card::get_summon_tribute_count()`
implements exactly the same split:

```cpp
if(level < 5) return 0;
else if(level < 7) min = max = 1;   // Level 5-6: one Tribute
else min = max = 2;                 // Level 7+:  two Tributes
```

## What each rule is here to prevent

| rule | the failure it fixes |
|---|---|
| Turn structure, one-way | The agent planned to attack from Main Phase 2 and declined a free direct attack to do it. |
| Tribute cost by Level | Three of four models planned "Normal Summon Zanki" - a Level 5 - as a free action, then counted on the monster the Tribute consumes. |
| A Tribute Summon trades, not adds | The same plans assumed two attackers when the summon left them with one, so the line could never reach lethal. |
| Battle positions gate effects | Battle position was rendered wrong for face-down defence, and nothing said position matters beyond combat. |
| Zones and columns | The board collapsed to a list of cards, so Link markers, the Extra Monster Zones and column effects were invisible. |

## Current text

```
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

Summoning, which is where plans most often go wrong:

- **One Normal Summon or Set per turn, total.** Not one of each — one, either.
- A monster Level 4 or lower needs no Tribute. **Level 5 or 6 costs 1 Tribute.
  Level 7 or higher costs 2.** You Tribute monsters you control.
- **A Tribute Summon *is* your Normal Summon, and it trades monsters rather
  than adding them.** Tributing your only monster to summon a bigger one
  leaves you with one monster, not two — so it does not increase how many
  attackers you have, and often reduces your total damage. Check that before
  planning a Tribute Summon as part of a lethal line.
- Special Summons do not use your Normal Summon and are not limited by it.
  Each card states its own conditions, and a monster that "Cannot be Normal
  Summoned" can only arrive the way its text describes.
- Setting a monster is not a Summon. A Set monster is face-down and cannot
  attack this turn.
- Each monster may declare one attack per turn. Once it has declared, it
  cannot attack again even if the battle is cancelled.

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
```
