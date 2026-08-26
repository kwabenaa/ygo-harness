# Official rulebook — extracted text

Text layer of Konami's *Yu-Gi-Oh! TRADING CARD GAME* rulebook (SD_RuleBook_EN_10),
extracted with `pypdf`; no OCR was needed. Fetched by `scripts/fetch_data.sh`
from <https://img.yugioh-card.com/en/downloads/rulebook/SD_RuleBook_EN_10.pdf>.

Copyright Konami. Kept here as a working reference for building the agent's
rules primer — see `primer.md` for the summary that actually ships in the
prompt, and `llm/prompt.py` for the operative copy.

Extraction artefacts survive: the PDF's two-column layout interleaves in
places, and table cells land as bare runs of words. Where this disagrees with
`vendor/ygopro-core`, **the engine is what actually adjudicates** — it is the
tiebreaker, this is the readable source.

---


## Page 1

OFFICIAL RULEBOOK Version 10


## Page 2

1 Getting Started
2 Game Cards
3 How to Play
4 Battles and Chains
5 Other Rules
Table of Contents Table of Contents
l About the Game .......................................................................... 1
l Things you need to Duel ............................................................ 2
l The Game Mat ............................................................................. 4
l Monster Cards .......................................................................... 6
l Effect Monsters ........................................................................ 9
l Xyz Monsters ........................................................................... 18
l Synchro Monsters ................................................................... 20
l Fusion Monsters ...................................................................... 22
l Ritual Monsters ...................................................................... 23
l Summoning Monster Cards ..................................................... 24
l Spell & Trap Cards ................................................................... 26
l Link Monsters ......................................................................... 12
l Monster Battle Rules .............................................................. 41
l Chains and Spell Speed ............................................................ 44
l Other Rules .............................................................................. 49
l Glossary ................................................................................... 52
l Let the Duel Begin ! ................................................................... 32
l Preparing to Duel ................................................................... 33
l Turn Structure ........................................................................ 34
l Pendulum Monsters ................................................................ 16
iii


## Page 3

What is the Yu-Gi-Oh! TRADING CARD GAME?
With the Yu-Gi-Oh! TRADING CARD GAME you can take part in the
exciting card game action seen in the family of Yu-Gi-Oh! TV and
comic mega-hits.
In this game, two players Duel each other using a variety of Monster,
Spell, and Trap Cards to defeat their opponent's monsters and be the
first to drop the other's LP (Life Points) to 0.
Everything you need to start playing is in this Deck, but there are
thousands more cards to choose from, so collecting additional cards
in Booster Packs will let you customize your Deck and increase your
chances of winning!
This is the official Yu-Gi-Oh! TRADING CARD GAME rulebook. It's
important to learn how to play correctly, so you should read this
rulebook before playing if you're new to the game. Understanding
the rules will help you make the best use of your cards, so keep
the rulebook handy during your first few games. You can also visit
www.yugioh-card.com for more information.
ABOUT THE GAME
CREATE YOUR OWN DECK
With thousands of cards to choose from, you can create and
customize your own Deck with your favorite cards. Every Duelist
will have their own unique Deck, completely different from every
other Duelist's Deck, which makes it really exciting to play!
BATTLE WITH FANTASTIC MONSTERS & GREAT COMBOS
Even if a card does not have enough power on its own,
it may become powerful when combined
with other cards. It's fun to collect all the
different cards available and create your
own combos, then unleash them in a Duel.
POWER UP YOUR DECK WITH BOOSTER PACKS
Booster Packs are released every few months,
bringing new cards and new combos to add new
strength to your Deck. Duels evolve every time
a new Booster Pack is released, keeping your
Duels cool and exciting.
1iii


## Page 4

Getting Started
Getting StartedAdditional items you may need
Coin Dice
Items which can help during a Duel
Some cards require a coin toss. If you
play with these, have a coin ready to
flip.
Just like the coin, there are some
cards that need a die roll. If you play
with these, have a standard die ready
with numbers 1 through 6.
Some cards will require markers
(called counters) to keep track of
things like the number of turns, or a
card's power level. You can use small
objects like glass beads, paper clips,
or pennies for the counters, which are
then placed on these face-up cards.
Tokens are used to represent
monsters that can be created by card
effects. Any object used for a Token
needs to have two distinct ways to
place it that can clearly indicate the
monster's battle position. (See page
45 for details.)
LP changes quickly during a Duel. It's
smart to use a calculator to keep track
of your LP . During important Duels,
you should track your LP on paper as
well to be extra-careful.
Plastic sleeves can prevent your cards
from getting bent or scratched. If you
use card sleeves, they all have to be
the same so your cards aren't marked.
1 Getting Started
Assemble your favorite cards into a Deck that follows these rules:
lThe Deck must be 40 to 60 cards.
lYou can only have up to 3 copies of the same card in your Deck,
 Extra Deck and Side Deck combined.
Also, some cards are Forbidden, Limited or Semi-Limited in official
tournaments. (See page 45 for details.)
Try to keep your Deck close to the 40-card minimum. Having a Deck
with too many cards makes it hard to draw your best cards when you
need them. This Deck is called your Main Deck.
This Deck consists of Xyz Monsters, Synchro Monsters and Fusion
Monsters, which can be used during the game if you meet certain
requirements. The rules for Extra Decks are:
lYou can have up to 15 cards in the Extra Deck.
lThe Extra Deck can contain Xyz Monsters, Synchro Monsters and
 Fusion Monsters, in any combination.
lThese cards are not counted towards the 40-card minimum limit \
 of your Main Deck.
This is a separate Deck of cards you can use to change your Deck
during a Match. After each Duel in a Match, you can swap any card
from your Side Deck with a card from your Deck and/or Extra Deck to
customize your strategy against your opponent. The number of cards in
your Side Decks must not exceed 15. The number of cards in your Side
Deck before and after you swap any cards must be exactly the same.
Side Deck ...........................................(0 to 15 cards)
Extra Deck ..........................................(0 to 15 cards)
Deck ................................................(40 to 60 cards)
Things you need to DuelThings you need to Duel
Counters Monster Tokens
Calculator Card Sleeves
32


## Page 5

7
1
2
3
4
5
6
42
31
7 7
5
6
Main Monster
Zone
Spell & Trap
Zone
Pendulum Zone
Graveyard
(GY)
Deck
Extra Deck
The Game Mat helps you organize your cards
during a Duel. When you use your cards you place
them on the Game Mat. Different kinds of cards
are placed in different Zones.
Each Duelist needs their own Game Mat; place
them together while Dueling. This combined space
is known as "the field." The Game Mat contained
in this product is just for your half of the field.
The cards you "control" are the cards on your side
of the field.
You can also Duel without using the Game Mat as
long as you remember where to place the cards.
This is where you put your monsters when they're played.
You can have up to 5 cards here. There are 3 ways to
position your Monster Cards: face-up Attack Position,
face-up Defense Position, and face-down Defense Position.
Place the card upright for Attack Position, and sideways
for Defense Position.
This is where you put Spell & Trap Cards. You can have up to
5 cards here. You place them here face-up to activate them,
or place them face-down. Pendulum Monster Cards can be
activated in the leftmost and rightmost zones as Spells. This
causes the zone you use to also become a Pendulum Zone
for as long as the Pendulum Monster Card is there. (See
page 23 for details on Pendulum Monster Cards.)
When Monster Cards are destroyed, and when Spell &
Trap Cards are used, they're sent face-up to this space.
The contents of both players' Graveyards are public
knowledge, and your opponent can look through yours at
any time during the Duel. The order of the cards in the
Graveyard should not be changed. Graveyard is shortened
in the card text to "GY".
Your Deck is placed face-down in this space. You draw cards
from here to add to your hand. If a card effect requires you
to reveal cards from your Deck, or look through it, shuffle
it and put it back in this space afterwards.
Special Spell Cards called Field Spell Cards are played here.
Each player can have 1 Field Spell Card on their own side
of the field. To use another Field Spell, send your previous
one to the Graveyard. Field Spell Cards do not count
towards the 5-card limit of your Spell & Trap Zone.
Place your Extra Deck face-down in this space. You can
look at the cards in your own Extra Deck during the game.
During a Duel, Extra Deck Monsters may be Summoned
to the field from here using special methods. Pendulum
Monster Cards that would be sent from the field to the
Graveyard are placed face-up here.
Field Zone
This is where you put your monsters that are Summoned to
the field by special methods from the Extra Deck, like Link
Monsters and Fusion Monsters. Normally, each player can
only use 1 of these zones. A monster placed in this zone
does not count towards the 5-monster limit of your Main
Monster Zone.
Extra Monster
Zone
54
THE GAME MA TTHE GAME MA T


## Page 6

/ DEF / ATK
DARK
 EARTH
 FIRE
LIGHT
 WATER
 WIND
Game Cards
Game Cards1
2
3
4
7
6
5
1 2
3
4
5
6
7
Monster CardsMonster Cards
Card Name
This is the card's name. When a
card name is mentioned in card
text it appears in quotations. If
cards have the same name, they
are considered to be the same
card.
Count the number of stars here
to find out the monster's Level.
For Xyz Monsters, the number
of stars is the Rank of the
monster, and is on left.
Level
Card
Description
Type
Card Name Attribute
Level
Card Number
ATK (Attack Points)
DEF (Defense Points)
2 Game Cards
HOW TO READ A CARD
Attribute
Type
Card Number
ATK (Attack Points) / DEF (Defense Points)
Card Description
Every monster has an Attribute.
This Attribute is sometimes
important for card effects.
Monsters are divided into various Types. Some monsters with
specific abilities will have additional information here too, next to
their Type.
A card's identification number is found here. This number is useful
for collecting, and for sorting your collection.
ATK is a monster's Attack Points and DEF is a monster's Defense
Points. High Attack and Defense Points are good when battling!
Card effects are written here, describing the monster's special
abilities and how to use them. Normally, the effects of monsters
cannot be used while they are Set face-down on the field. Yellow
Normal Monster Cards do not have effects, and have a description
of them written here that does not affect the game.
76


## Page 7

Game Cards
Game Cards
WHAT IS A MONSTER CARD?
Monster Cards are used to battle and defeat your opponent. Battles
between Monster Cards are the foundation of any Duel.
There are many kinds of Monster Cards. This game is more than a
simple slugfest, so monsters with high Attack and Defense Points will
not be enough. There are also monsters with strong special effects
even though their ATK and DEF points are low. Therefore, your
success in a Duel depends on how skillfully you can make use of the
different kinds of cards. Let's take a look at the different kinds of
monsters.
These are basic Monster Cards
without special abilities. Many
Normal Monsters have higher
Attack Points and Defense
Points than Effect Monsters,
instead of having special
abilities.
<<< Normal Monsters
<<< Effect Monsters
An Effect Monster is a monster
that has special abilities.
The effects of these monsters
are split into four categories:
• Continuous Effect
• Ignition Effect
• Quick Effect
• Trigger Effect (including Flip)
Continuous Effect
This effect is active while the Effect Monster Card is face-up on
the field. The effect starts when the face-up monster appears
on the field, and ends once that monster is gone or is no longer
face-up; there is no trigger for its activation. These monsters
are most useful if you have a strategy to protect them while
they are on the field.
Monsters with 2000 or less ATK cannot declare
an attack.Example
98


## Page 8

Game Cards
Game Cards
Ignition Effect
You use this type of effect just by declaring its activation during
your Main Phase. (See Turn Structure, page 30.) There are some
Ignition Effects that have a cost to activate, like discarding cards
from your hand, Tributing a monster, or paying LP . Because you
can choose when to activate this type of effect, it's easy to
create combos with them.
You can Tribute this card, then target 1 monster
on the field; destroy that target.Example
Quick Effect
These are special monster effects that you can activate even
during your opponent's turn. These types of effects have a
Spell Speed of 2, even though all other monster effects have a
Spell Speed of 1. (See Spell Speed, page 41.) Since it's difficult for
your opponent to predict these cards, they can give them an
unexpected surprise.
(Formerly called Multi-Trigger Effects.)
When an effect is activated (Quick Effect):
You can target 1 card in your Graveyard; Special Summon it.Example
Trigger Effect
These effects are activated at specific times, such as "during
the Standby Phase" or "when this monster is destroyed". These
cards can make for some great combos, but it's easier for your
opponent to predict what will happen, so they might try to stop
you.
When this card is destroyed by battle and sent to the
Graveyard: Target 1 card on the field; destroy that target.Example
Flip Effect
Flip effect is a part of the Trigger Effect.
This is an effect that is activated when a face-down card is
flipped face-up. This can happen when it is Flip Summoned,
attacked while face-down, or flipped face-up by a card effect.
These effects start with the word "FLIP:" on the card. When
you have a face-down monster, your opponent must be wary
because they don't know if it has a Flip effect or not.
FLIP: Draw 1 card.Example
1110


## Page 9

1
2
3
A Link Monster is a new kind of
monster with the ability to increase
the number of monsters you can
Summon from your Extra Deck.
In addition to the 1 Extra Monster
Zone you can usually use, you can
also Summon monsters from the
Extra Deck to any of your Main
Monster Zones that has a Link
Monster's red arrow pointing to it.
LINK Rating - This is the number of Link
Arrows that monster has and the number
of monsters needed to Summon it.
Link Arrows - A Link Monster can apply
its effects on cards or zones that its lit-up,
red Link Arrows point to. When a Link
Monster's red arrow points to a monster,
those monsters are "linked". When two
Link Monsters have red arrows that point
at each other, they are "co-linked".
Link Materials - These are the Link
Materials you need to Summon this
Monster. Use this "recipe" printed here
to Link Summon this monster.
HOW TO LINK SUMMON
Check the materials of the Link Monster you want to Summon.
During your Main Phase, declare that you are Link Summoning,
send a number of face-up monsters from your field to the
Graveyard equal to the Link Rating of that Link Monster. They
must also match the material requirements listed in the monster's
"recipe" written on the card.
Place the Link Monster from your Extra Deck in the Extra Monster
Zone, or one of your Main Monster Zones that another Link
Monster is pointing to.
If 2 Extra Monster Zones are available, you can choose either one to
Summon your monster.
If there is a Link Monster already on the field, you can Link Summon a
monster in one of your zones it points to.
1312
LINK MONSTERSLINK MONSTERS


## Page 10

LINK MONSTER BONUSES
Link Monsters already on the field make great material!
Normally, 1 monster equals 1 Link Material. But when you use a
Link Monster as material for another Link Summon, you can count
it as either 1 monster, or as a number of monsters equal to its
Link Rating. For example, if you want to Summon a Link 3 monster
that requires 2 or more materials in its "recipe", you can either
use 3 monsters (each counts as 1 material) or else a Link 2 Link
Monster (counts as 1 or 2 materials) and a second monster (counts
as 1 material).
Special Summon to
the Main Monster Zones
Monsters Summoned from the
Extra Deck normally have to go in
the Extra Monster Zone. But Link
Monsters open up more zones
for you to use, because every
Main Monster Zone that a Link
Monster points to can also be
used to Summon monsters from your Extra Deck. Monsters that
started in the Extra Deck, but later end up in the Graveyard (or
are banished) and are Summoned from there, also go in the Main
Monster Zones (and don't need a Link Monster to point to them).
Special Summon monsters from
your Extra Deck in these zones!
Link Monsters have no DEF and cannot ever be in Defense Position.
They can't be changed to Defense Position by a card effect. They
can't even be flipped into face-down Defense Position.
If your opponent has a monster in the Extra Monster Zone, it's still
a monster they control so you can't attack directly. You have to
battle and destroy all their monsters first, including the one in the
Extra Monster Zone.
If you take control of your opponent's monster in the Extra Monster
Zone, it moves to your Main Monster Zone. When it goes back to
your opponent, it goes to their Main Monster Zone, not the Extra
Monster Zone.
As long as the materials meet the requirements of the Link Monster
you want to Summon, you can use a Token or Trap Card that is
treated as a monster as the Link Material.
Remember that when you Link Summon, you need to meet 3 goals:
 The amount of materials you use matches the Link Rating (Link
 Monsters count as 1 OR their own Link Rating).
 The number of materials you use meets the number specified in
 the materials line or "recipe".
 The materials match any other requirements in the materials line
 (such as only Effect Monsters, or only a specific Type of monster).
OR
•
•
•
1514
MORE ABOUT LINK MONSTERSMORE ABOUT LINK MONSTERS


## Page 11

1
2
3
Pendulum Monster Cards
are a unique kind of card
that blurs the line between
Monsters and Spells! They can
be Summoned as monsters to
attack or defend, or you can
activate them as Spell Cards
in your Pendulum Zones to
activate extra special abilities
and allow you to Pendulum
Summon!
Pendulum Effect - When you play this
card as a Spell Card in your Pendulum
Zone, this is its effect. Some Pendulum
Monster Cards may not have Pendulum
Effects.
During your Main Phase, activate Pendulum Monster
Cards as Spell Cards in your leftmost and rightmost Spell
& Trap Zones. These Spell & Trap Zones also become
Pendulum Zones.
After you have one in each Pendulum Zone, once
per turn during your Main Phase, declare that you're
Pendulum Summoning.
Check the Pendulum Scales on the sides of your 2
Pendulum Monster Cards, then Special Summon as many
monsters as you want from your hand and as many face-
up Pendulum Monsters from your Extra Deck, whose
Levels are in between those Pendulum Scales.
Whenever one of your Pendulum Monster Cards on the field
(regardless of which Zone it is in, or even if it is a monster or
not) would be sent to the Graveyard, place it face-up on your
Extra Deck instead. You can Pendulum Summon it back to the field
later! Monsters Pendulum Summoned from the Extra Deck must be
Summoned to the Extra Monster Zone or your Main Monster Zone
pointed to by a Link Monster.
HOW TO PENDULUM SUMMON
Monster Effect - When you play this
card as a regular Monster Card, this is
its effect. Some Pendulum Monster Cards
may not have monster effects.
Pendulum Scale - Pendulum Scale is a
number that determines which monsters
you can Special Summon during a
Pendulum Summon. The Pendulum Scale
of this card is 1.
You can Special Summon
monsters with
Levels 2, 3, 4, 5, 6 and 7.
1716
PENDULUM MONSTER CARDSPENDULUM MONSTER CARDS


## Page 12

Xyz Monsters (pronounced "ik-
seez") are a powerful kind of
monster! You can Summon an
Xyz Monster whenever you
control monsters that are the
same Level. Xyz Monsters start
in your Extra Deck, not in your
Main Deck, and wait for you to
call them into action.
Materials needed for an Xyz Summon
Xyz Monster's Rank -
This is the Rank of your Xyz
Monster. Xyz Monsters have
Ranks instead of Levels.
Stronger Xyz Monsters have
higher Ranks. This is a Rank
4 Xyz Monster.
Xyz Materials -
These are the Xyz Materials
you need to Summon this
monster. You use 2 Level 4
Monsters as the Xyz Materials
to Summon this monster. Xyz
Materials must be face-up
before you can use them.
Xyz Summoning is your cool and easy way to Special Summon
Xyz Monsters from your Extra Deck. Here's how to do it!
Choose an Xyz Monster from your Extra Deck
that you have the right Xyz Materials for. The
Xyz Materials should be face-up on your field.
During your Main Phase, declare that you are
Xyz Summoning and stack the Xyz Materials on
top of each other.
Take the Xyz Monster from your Extra Deck and
put it on top of the stacked Xyz Materials in the
Extra Monster Zone in face-up Attack or Defense
Position.
LEVEL 4 LEVEL 4 Xyz Summon!
If there is a Link Monster on the field, you can Xyz Summon a monster in
one of your zones it points to.
When an Xyz Monster tells you to "detach" a material, take one of the
stacked Xyz Material cards beneath your Xyz Monster and put it in the
Graveyard.
1
2
3
HOW TO XYZ SUMMON
1918
XYZ MONSTERSXYZ MONSTERS


## Page 13

+ =
1
2
3
Tuner Non-Tuner Monster Synchro Summon!
Synchro Monsters are placed in the
Extra Deck, separate from the Main
Deck. You can Special Summon a
powerful Synchro Monster to the
field in an instant just by using the
Levels of your monsters. They can
be Synchro Summoned from the
Extra Deck by sending 1 face-up
"Tuner" monster and any number
of face-up non-Tuner monsters from
your field to the Graveyard, when
the sum of all their Levels is exactly
equal to the Level of the Synchro
Monster.
HOW TO SYNCHRO SUMMON
During your Main Phase, you can declare a Synchro Summon when
the combined total Levels of 1 face-up Tuner monster and any
number of other face-up monsters you control are equal to the
Level of the Synchro Monster you want to Synchro Summon.
LEVEL 2LEVEL 3 LEVEL 5In order to Synchro Summon
a Synchro Monster, you need
1 Tuner (look for "Tuner" next
to its Type). The Tuner monster
and other face-up monsters you
use for the Synchro Summon are
called Synchro Materials. The
sum of their Levels is the Level
of Synchro Monster you can
Summon.
After double-checking the Level of the Synchro Monster you
want, send the face-up Synchro Materials from your field to the
Graveyard.
After sending the Synchro Materials from the field to the
Graveyard, take the Synchro Monster from your Extra Deck and
play it in the Extra Monster Zone in face-up Attack or Defense
Position.
If there is a Link Monster on the field, you can Synchro Summon a
monster in one of your zones it points to.
TUNER MONSTERS FOR SYNCHRO SUMMONTUNER MONSTERS FOR SYNCHRO SUMMON
2120
SYNCHRO MONSTERSSYNCHRO MONSTERS


## Page 14

1
2
3
1
2
3
HOW TO RITUAL SUMMONHOW TO FUSION SUMMON
Fusion Monsters are also placed
in your Extra Deck (not in your
Main Deck). They are Summoned
by using the specific monsters
listed on the card (called
Fusion Materials) combined
with a Summoning card like
Polymerization. They usually
have special abilities and very
high Attack Points as well. Since
Fusion Summons require specific
cards, be sure and include those
necessary cards in your Main
Deck!
Ritual Monsters are special monsters
that are Special Summoned with a
specific Ritual Spell Card, along with
a required Tribute. Ritual Monster
Cards are placed in the Main Deck and
cannot be Summoned unless you have
all the proper cards together in your
hand or on the field. Ritual Monsters
generally have high ATK and DEF and
some have special abilities, just like
Fusion Monsters.
If you have all the Fusion Materials listed
on the Fusion Monster Card, in the places
specified on your Summoning card, you can
activate your Summoning card by placing it in
your Spell & Trap Zone.
Send the Fusion Materials to the Graveyard, then
take the appropriate Fusion Monster from your
Extra Deck and play it in the Extra Monster Zone
in either face-up Attack or Defense Position.
Finally, place your Summoning card in the
Graveyard. (If another card effect causes your
Fusion Materials to be sent to a place other
than the Graveyard when your Summoning card
resolves, send them to that other place, but the Fusion Summon still
happens anyway.)
When you have a Ritual Spell Card, along with the matching Ritual
Monster Card, in your hand, along with the required Tribute (as
listed on the Ritual Spell Card), you can activate the Ritual Spell Card,
placing it in the Spell & Trap Zone.
If the activation of the Ritual Spell Card is successful,
Tribute monsters by sending them from your hand or
the field to the Graveyard. The Ritual Spell Card will
list the required amount to Tribute.
After sending the Tributed monsters to the Graveyard,
play the Ritual Monster Card in your Main Monster
Zone in either face-up Attack or Defense Position.
Finally, place the Ritual Spell Card in the Graveyard.
Polymerization
Ritual Spell CardIf there is a Link Monster on the field, you can Fusion Summon a
monster in one of your zones it points to.
2322
FUSION MONSTERSFUSION MONSTERS RITUAL MONSTERSRITUAL MONSTERS


## Page 15

Game Cards
 


Game Cards
There are several ways to play monsters onto the field. These ways
can be categorized into 2 groups: actions that can be done only once
per turn, and actions that can be done multiple times per turn.
This is the most common way to Summon a monster. Simply play
a Monster Card from your hand onto the field in face-up Attack
Position. All Normal Monsters, and most Effect Monsters (unless
they have a specific restriction), can be Summoned in this way.
Summoning Monster CardsSummoning Monster CardsYou can do one of these once per turn
You can do as many of these during a turn as you want
Normal Summon
You can change a face-down Defense Position monster into face-
up Attack Position, without using a card effect. This is called a Flip
Summon. When you Flip Summon, you cannot change the monster to
face-up Defense Position, only to face-up Attack Position. A Monster
Card cannot be Flip Summoned in the same turn that it was Set onto
the field. You cannot use most monsters' effects until they are face-up.
Some monsters can be played onto the field without being Normal
Summoned or Set. This is called a Special Summon. Pendulum Summons,
Xyz Summons, Synchro Summons, Fusion Summons and Ritual Summons
are all Special Summons. Some Effect Monsters also have specific
conditions that allow you to Special Summon them. Unless otherwise
specified, a Special Summoned monster is played onto the field in your
choice of face-up Attack Position or face-up Defense Position.
Monsters can also be Special Summoned onto the field through the effect
of another card. This is different from "Special Summon Monsters." You
cannot use a card effect to Special Summon those monsters from your
hand, Deck, or the Graveyard unless it was properly Special Summoned
first. For example, if a Synchro Monster is sent from your Extra Deck
to the Graveyard without being Synchro Summoned, you cannot use a
Spell Card to Special Summon it from the Graveyard, because Synchro
Monsters have to be properly Special Summoned first, before they can
be Special Summoned by another card's effect.
Flip Summon
Special Summon
Special Summon with a Card's Effect
Level 5, 6 Level 7 or higher
1 Tribute 2 Tributes

To play a Monster Card from your hand in face-down Defense
Position is called a Normal Set. A monster Normal Set on the
field is NOT considered Summoned. It has been Normal Set, and
can be Summoned with a Flip Summon or flipped face-up by an
attack or card effect. Remember, you can only Normal Summon
OR Normal Set (Normal Summon/Set, in short), once per turn, so
if you Normal Set a monster you cannot also Normal Summon a
monster that turn.
Note: You cannot play a monster from your hand onto the field
in face-up Defense Position.
Normal Set

For monsters that are Level 5 or higher, you must Tribute at least
1 monster you control before the Normal Summon/Set. This is
called a Tribute Summon. Monsters that are Level 5 or 6 require
1 Tribute and Monsters that are Level 7 or higher require 2 Tributes.
Tribute Summon
If you Tribute Summon in face-down Defense Position, it is called
a Tribute Set. A monster Tribute Set on the field is NOT considered
Summoned.
Note: When a card explains a special method to Tribute Summon a
monster, you can also Tribute Set the monster by the same method.
2524


## Page 16

Game Cards
Game Cards
1
2
3
4
5
Spell & Trap CardsSpell & Trap Cards
HOW TO READ A CARD
Spell Card
Type
Icon
Card Number
Card Name
Card Description
Trap Card
1 2
3
4 5
Remember, cards with the same
name are considered to be the
same card, and you can only
have up to 3 copies of the same
card in your Main Deck and Side
Deck combined.
Instead of having an Attribute
symbol like Monster Cards, a
Spell Card has the "SPELL 魔"
symbol and a Trap Card has the
"TRAP 罠" symbol.
Each card's activation
conditions and effects are
provided here. Read the card
description carefully and follow
the instructions.
A card's identification number is
found here. This number is useful
for collecting, and for sorting
your collection.
There are 6 types of icons that represent special properties a Spell or
Trap Card may have. Spell and Trap Cards without an icon are called
Normal Spell Cards or Normal Trap Cards.
Equip Field Quick-Play
Ritual Continuous Counter
Card Name Type
Card Description Card Number
Icon
2726


## Page 17

Game Cards
Game Cards
<<< Spell Cards
Normal Spell Cards
Ritual Spell Cards
Equip Spell Cards
Quick-Play Spell Cards
Field Spell Cards
Continuous Spell Cards
Spell Cards can normally be
activated only during your Main
Phase, and help you out with
different effects. Spell Cards
have many powerful effects,
like destroying other cards or
strengthening monsters. Save
these cards in your hand until
you can get the best results out
of them.
Normal Spell Cards have single-use effects. To use a Normal Spell Card,
announce its activation to your opponent, placing it face-up on the field.
If the activation succeeds, then you resolve the effect written on the card.
After resolving the effect, send the card to the Graveyard.
These Spell Cards are used to perform Ritual Summons. Use these cards
in the same way as you would use Normal Spell Cards.
These cards remain on the field once they are activated, and their effect
continues while the card stays face-up on the field. By using Continuous Spell
Cards, you can create lasting positive effects with a single card, which is great
but there's the chance that the opponent will remove it from the field before
you benefit from the effect.
These are special Spell Cards that can be activated during any Phase of
your turn, not just your Main Phase. You can also activate them during your
opponent's turn if you Set the card face-down first, but then you cannot
activate the card in the same turn you Set it.
These cards give an extra effect to
1 face-up monster of your choice
(either your own or your opponent's,
depending on the card). They remain
on the field after they are activated.
The Equip Spell Card affects only
1 monster (called the equipped
monster), but still occupies one of
your Spell & Trap Zones. If possible,
place it in the zone directly behind
the equipped monster to help you
remember. If the equipped monster
is destroyed, flipped face-down, or
removed from the field, its Equip
Cards are destroyed.
These cards go in your Field Zone
and stay there. Each player can have
1 Field Spell Card on their own side
of the field. To use another Field
Spell, send your previous one to the
Graveyard. Many Field Spell effects
apply to BOTH players.

These cards may be placed face-
down in the Field Zone, but are not
active until flipped face-up.
2928


## Page 18

Game Cards

Game Cards
Continuous Trap Cards
Just like Continuous Spell Cards, Continuous Trap Cards remain on the field
once they are activated and their effects continue while they are face-up on the
field. Some Continuous Trap Cards have abilities similar to the Ignition Effects or
Trigger Effects that can be found on Effect Monster Cards.
Continuous Trap Cards can have effects that limit your opponent's options, or
that slowly damage your opponent's LP .
Counter Trap Cards
These Trap Cards are normally activated in response to the activation of other
cards, and may have abilities like negating the effects of those cards. These
types of Traps are effective against Normal Spell Cards or Normal Trap Cards,
which are otherwise hard to stop, however many Counter Trap Cards require
a cost to activate them.
Normal Trap Cards
Before you can activate a Trap Card, you must Set it on the field first.
You cannot activate a Trap in the same turn that you Set it, but you
can activate it at any time after that—starting from the beginning of
the next turn.
Normal Trap Cards have single-use effects and once their effects are
resolved, they will be sent to the Graveyard, just like Normal Spell
Cards. They are also similar to Normal Spell Cards because once
activated, their effects are not likely to be stopped. However, your
opponent can destroy your face-down Trap Cards on the turn they were
Set, or before the time is right to activate them. Because of this, you
must be smart about how you use your Trap Cards.
<<< Trap Cards
Trap Cards will help you out with
different effects, just like Spell
Cards. The big difference between
them is that you can activate Trap
Cards during your opponent's turn.
Many Spell Cards have effects useful
for offense, but Trap Cards have
the ability to surprise the opponent
by disrupting their attacks and
strategies. Using Trap Cards can
sometimes be tricky, since your
opponent might have to do certain
things before you can unleash them.
Spell Cards can be Set face-down on the field like Trap Cards.
However, the rules for the two types of cards are different.
Spell Cards can be activated during the Main Phases even in the
same turn that you Set them (except for Quick-Play Spell Cards).
Setting them does not allow you to use them on your opponent's
turn; they still can only be activated during your Main Phase.
You can Set a Spell Card face-down on the field to bluff your
opponent into thinking you have a powerful Trap.
The Difference between Set Spell Cards and Set Trap Cards
3130


## Page 19

3 How to Play


How To Play
1
2
3
4
How To Play
Let the Duel Begin!Let the Duel Begin!
A single game is called a Duel, and a Duel ends when one player wins
or the game ends in a draw. Duels are played in sets of 3 called a
Match, and the winner of best 2-out-of-3 wins the Match.
How to Duel and How to Win
Each player starts a Duel with 8000 LP (Life Points). You win a Duel
if: you reduce your opponent's LP to 0; if your opponent is unable
to draw a card; or if a card's special effect says you win. If you and
your opponent both reach 0 LP at the same time, the Duel is declared
a draw.
Winning a Duel
Before starting a Duel, follow these 4 steps. Also, make sure you
have all your extra items that your Deck might need, like a coin or
counters.
Preparing to DuelPreparing to Duel
• Reduce your opponent's LP to 0.
• Your opponent is unable to draw a card when they are supposed
 to draw.
• Win with a card's special effect.
Victory Conditions
After greeting your opponent, shuffle your Deck thoroughly. Then you may
shuffle and cut your opponent's Deck (be careful when touching your opponent's
cards).
After cutting, place the Decks face-down in the proper Deck Zones on the field.
If using an Extra Deck with Xyz Monsters, Synchro Monsters or Fusion Monsters,
place it face-down in the Extra Deck Zone.
Both players show each other their Side Decks, and record the number of cards in
it, also confirming that they have 15 or fewer cards (the cards should be counted
face-down). If you exchange cards between your Side and Main Decks after a
Duel, count the cards of your Side Deck for your opponent again to show that the
number of your cards remain the same.
Play rock-paper-scissors or flip a coin. The winner decides to go first or second
in the Duel. For your next Duels, the loser of the previous Duel decides who goes
first. If the previous Duel ended in a tie, determine who starts first in the next
Duel with another coin toss, etc.
Finally, draw 5 cards from the top of your Deck; this is your starting hand.
Starting with the first player, it's time to Duel!
3332


## Page 20

How To Play
How To Play
Turn StructureTurn Structure
A Duel progresses in a series of turns which are divided into phases.
Prepare to Duel
1st Player's turn
Draw Phase
Standby Phase
Main Phase 1
Battle Phase
Main Phase 2
End Phase
2nd Player's turn
If no battles are conducted
Main Action in this Phase
Possible Other Actions
Draw 1 Card (except for the very
1st turn of the Duel).
Activate Trap Cards, Quick-Play
Spell Cards, etc.
Some cards have effects that activate, or costs you must pay, in the
Standby Phase. If you do not have any of these cards on the field, you
can still activate Trap Cards or Quick-Play Spell Cards before moving
on to your Main Phase 1.
Standby Phase
Main Action in this Phase
Possible Other Actions
Resolve card effects that happen
in this phase
Activate Trap Cards, Quick-Play
Spell Cards, etc.
This is the first phase. The player whose turn it is (the "turn player")
draws 1 card from the top of their Deck. A player with no cards left in
their Deck and unable to draw loses the Duel. After you draw, Trap
Cards or Quick-Play Spell Cards can be activated before proceeding
to the Standby Phase.
IMPORTANT: The player who goes first cannot draw during the
Draw Phase of their first turn.
Draw Phase
3534


## Page 21

How To Play
How To Play
Now it's time to battle with your Monster Cards! This phase is divided
into steps.
You do not have to conduct a Battle Phase every turn, even if you
have a monster on the field.
IMPORTANT: The player who goes first cannot conduct their
Battle Phase on their first turn.
Battle Phase
There is no limit to the number of times you can Flip Summon or
Special Summon during a turn, but you can only Normal Summon
or Set a monster (including a Tribute Summon) once per turn.
Main Phase 1
Possible Actions in this Phase
Summon or Set a Monster
This includes Flip Summoning a monster, or changing the position
of a face-up monster to face-up Attack or Defense Position. You
can change the position of each monster you control, except in
three cases. 1. You cannot change the battle position of a monster
that was played onto the field this turn. 2. You cannot change it
in Main Phase 2 if the monster attacked during the Battle Phase.
3. You cannot change it if you have already changed its battle
position once this turn.
Change Your Monsters' Battle Positions
You can activate Spell and Trap Cards, or the effects of Spell, Trap,
or Effect Monster Cards as many times as you want during this
phase, as long as you can keep paying any costs involved.
Active a Card or EffectActive a Card or Effect
You can Set Spell and Trap Cards face-down in your Spell & Trap
Zone during this phase, as long as you have space.
Set Spell Cards and Trap Cards
Possible Actions in
this Phase
Battle with monsters
Activate Trap Cards and Quick-
Play Spell Cards
Start step
Battle Step
End Step
Damage Step
Flow of the
Battle Phase
The Battle Phase is split into
4 steps and is conducted in the
order shown in the diagram. The
Battle Step and Damage Step are
repeated each time you attack
with a monster.
This is when you play most of your cards: you can Normal Summon,
Set, or change the battle position of a monster, activate a card's
effect, and Set Spell and Trap Cards. These actions can be done in
any order you want, but some actions have restrictions.
3736


## Page 22

How To Play

How To Play
After you've announced your
attacking monster and the attack
target monster during a Battle
Step, the attack target might be
removed from the field, or a new
monster may be played onto the
opponent's side of the field before
the Damage Step, due to a card's
effect. This causes a "Replay."
When this occurs, you can choose
to attack with the same monster
again, or choose to attack with a
different monster, or choose not
to attack at all. Note that if you
attack with a different monster,
the first monster is still considered
to have declared an attack, and it
cannot attack again this turn.
Replay Rules during the Battle Step
This step starts the Battle Phase. The turn player should
announce "I'm entering the Battle Phase." Remember, the player
who goes first cannot conduct a Battle Phase in their very first
turn.
Start Step
Select 1 monster on your side of the field to attack with, and 1 of
your opponent's monsters as your attack target, and then declare
the attack. If your opponent does not have any monsters on the
field, you can attack directly. Play then proceeds to the Damage
Step. Afterwards, the attacking player returns to the Battle Step,
and repeats this procedure. Each face-up Attack Position monster
you control is allowed 1 attack per turn. You do not have to attack
with a monster if you don't want to.
Battle Step
In this step, the players calculate the result of the battle and
whatever damage is done. (See "Monster Battle Rules", page 37.)
After finishing the Damage Step, return to the Battle Step.
Damage Step
After you've resolved all your battles by repeating the Battle and
Damage Steps, and you have no more monsters you want to attack
with, announce to your opponent that you are ending your Battle
Phase.
End Step
Declare your attacking
monster and your attack
target monster.
A replay happens!
Re-select a target monster.
The
monsters
your opponent
controls change
before the Damage
Step.
3938


## Page 23

4 Battles and Chains



Battles and Chains
How To Play
Monster Battle RulesMonster Battle Rules
Main Phase 2
If you conducted your Battle Phase, your turn moves to Main Phase 2
afterwards. The actions a player can perform in this phase are the same
as in Main Phase 1. However, if the player already did something in Main
Phase 1 that has a limit to the number of times it can be done, the player
cannot do it again in Main Phase 2. Consider if you want to activate and
Set Spell & Trap Cards, or Summon or Set a monster (if you didn't do that
in Main Phase 1) based on your situation after the Battle Phase. Use this
phase to prepare for the opponent's turn.
End Phase
Announce the end of your turn, and if there are any cards on the
field which say "…during the End Phase…" in their text, resolve
those effects in this phase. If you have more than 6 cards in your
hand at the end of this phase, select and discard cards to the
Graveyard until you only have 6 cards in your hand.
Possible Actions in this Phase
Summon or Set a monster
Change your monsters' battle positions
Active a card or effect
Set Spell Cards and Trap Cards
Actions in this Phase
Resolve card effects which
activate in this phase
Discard if you have more than
6 cards in hand
Possible Other Actions
in this Phase
Activate Trap Cards and Quick-Play
Spell Cards
DAMAGE STEP RULES
During the Damage Step, you can only activate Counter Trap Cards,
or cards with effects that directly change a monster's ATK or DEF.
Also, these cards can only be activated up until the start of damage
calculation.
Limitations on Activating Cards
If you attack a face-down Defense Position monster, flip the card to
face-up Defense Position in the Damage Step. Now you can see the
monster's DEF and then calculate damage.
Attacking a Face-Down Card
When an attacked monster is flipped face-up, any Flip effects are
activated and resolved after damage calculation. If you need to select
a monster for the Flip effect to target, you cannot target a monster
that has already been destroyed during damage calculation.
Activation of a Flip Effect
During the Damage Step, there are limits on what cards you can
activate. Also, during the Damage Step, Flip effects resolve a bit
differently than they normally do.
For more info on the Damage Step, please visit:
www.yugioh-card.com/en/gameplay/damage_step/
4140


## Page 24

VS.
VS.
Battles and Chains
Battles and Chains
You calculate battle damage based on the battle position of the
monster you are attacking. If you attack an Attack Position monster,
compare ATK vs. ATK. If you attack a Defense Position monster,
compare your monster's ATK vs. the attacked monster's DEF.
When your attacking monster's ATK is higher than the ATK of
the opponent's monster, the attacking monster destroys the
opponent's monster and sends it to the Graveyard.
The amount that your attacking monster's ATK exceeds the
ATK of your opponent's monster is subtracted from your
opponent's LP as battle damage.
When your attacking monster's ATK is equal to the ATK of the
opponent's monster, the result is considered a tie, and both
monsters are destroyed.
Neither player takes any battle damage.
When your attacking monster's ATK is lower than the ATK of
the opponent's monster, the attacking monster is destroyed
and sent to the Graveyard.
The amount that the opponent's monster's ATK exceeds the
ATK of your attacking monster is subtracted from your LP as
battle damage.
When your attacking monster's ATK is higher than the DEF of
the opponent's monster, the attacking monster destroys the
opponent's monster and sends it to the Graveyard.
Neither player takes any battle damage.
When your attacking monster's ATK is equal to the DEF of the
opponent's monster, neither monster is destroyed.
Neither player takes any battle damage.
When your attacking monster's ATK is lower than the DEF of
the opponent's monster, neither monster is destroyed.
The amount that the opponent's monster's DEF exceeds the
ATK of your attacking monster is subtracted from your LP as
battle damage.
If there are no monsters on your opponent's side of the field, you
can attack directly. The full amount of your attacking monster's ATK
is subtracted from the opponent's LP as battle damage.
When You Attack an Attack Position Monster
ATK of Attacking
Monster
ATK of Opponent's
Monster
ATK of Attacking
Monster
DEF of Opponent's
Monster
WINTIELOSE
WINTIELOSE
If Your Opponent Has No Monsters
DETERMINING DAMAGE When You Attack a Defense Position Monster
4342


## Page 25

Battles and Chains
Battles and Chains
Chains and Spell SpeedChains and Spell Speed
Chains are a way to order the resolution of multiple card effects.
They are used when the effects of more than 1 card are activated
at once (see page 46), or when a player wants to use an effect after
a card has been played, but BEFORE that card has an effect on the
game.
If a card's effect is activated, the opponent is always given a chance
to respond with a card effect of their own, creating a Chain. If your
opponent responds with an effect, then you can choose to respond
and add another effect to the Chain. If your opponent does not
respond, you may activate a second effect and create a Chain to
your own card's activation. Both players continue to add effects to
the Chain until they both wish to add nothing else, then you resolve
the outcome in reverse order - starting with the last card that was
activated.
You must always be careful not to resolve the effects of your cards
before asking your opponent if they wish to make a Chain.
WHAT IS A CHAIN?
Every type of card effect has a Spell Speed between 1 and 3. If you
want to respond to a card effect in a Chain, you have to use an effect
with Spell Speed 2 or higher, and it cannot have a lower Spell Speed
than the effect you are responding to. Please see page 41 for an
introduction to each type of card's Spell Speed.
SPELL SPEED
Spell, Trap, and Effect Monster effects have different Spell Speeds.
There are Spell Speeds from 1 to 3. You can only respond with an
effect if it is Spell Speed 2 or higher, and has an equal or greater Spell
Speed than the effect on the Chain Link before it.

This is the slowest of all Spell Speeds. These cards cannot be
activated in response to any other effects. Typically, these effects
cannot be Chain Link 2 or higher, unless multiple Spell Speed 1
effects are activated simultaneously.
Spell Speed 1
These cards can be used to respond to a Spell Speed 1 or 2 effect, and
can typically be activated during any phase.
Spell Speed 2
This is the fastest of all Spell Speeds and can be used to respond to
a card of any Spell Speed. Only another Spell Speed 3 card may be
used to respond to these cards.
Spell Speed 3
Spells (Normal, Equip, Continuous, Field, Ritual),
Effect Monster's effects (Ignition, Trigger, and Flip)
Traps (Normal, Continuous), Quick-Play Spells,
Effect Monster's Quick Effects
Counter Trap
Spell Speeds
4544


## Page 26

Battles and Chains
3
2
1


Battles and Chains
How a Chain Works
[Chain Complete]
[Chain Link 4]
[Chain Link 3]
[Chain Link 2]
[Chain Link 1]
Spell Speed 2 or 3 card used
against Chain Link 3
Spell Speed 2 or 3 card used
against Chain Link 2
Spell Speed 2 or 3 card used
against Chain Link 1
Spell Speed 1 or 2 card that's
used
As shown in the diagram above, the first effect activated is Chain
Link 1. The next effect is Chain Link 2, and so on. Every time a new
Chain Link is made, they are stacked up in the order that the cards
are activated. Once the Chain is completed, the outcome is resolved
starting with the most recent card to be activated at the top of the
Chain and proceeding down to Chain Link 1.
Order of activation
Order of resolution Player A plays "Heavy Storm" and Player B responds by activating
their Set "Threatening Roar." Then, Player A responds to that by
activating "Seven Tools of the Bandit."
In this case, Chain Links are stacked up as seen below.
EXAMPLE OF A CHAIN
Chain Link
Chain Link
Chain Link
"Seven Tools of the Bandit"
Negates the effect of "Threatening Roar"
Spell Speed 3
"Threatening Roar"
Prevents the opponent from declaring attacks this turn.
Spell Speed 2
"Heavy Storm"
Destroys all Spell and Trap Cards on the field.
Spell Speed 1
"Seven Tools of the Bandit" (Chain Link 3) is resolved first and
negates the activation of "Threatening Roar."
"Threatening Roar" (Chain Link 2) would then be resolved, but the
effect of "Seven Tools of the Bandit" stops its activation. The turn
player will still be able to declare attacks.
Then the effect of "Heavy Storm" (Chain Link 1) is resolved
successfully, destroying all Spell and Trap Cards on the field,
allowing the turn player to attack without interference from Spell
or Trap Cards.
4746


## Page 27

Other Rules
5 Other Rules

Normally, your Deck (including Extra Deck and Side Deck) can
contain up to 3 copies of a card that has the same name. However,
certain cards have specific quantity restrictions that further limit the
number that can be included in a Deck.
There are 3 types of restrictions: Limited cards are restricted to
1 copy in a Deck, while Semi-Limited cards are restricted to 2 copies
in a Deck. Forbidden cards are not allowed to be included at all.
The list of Forbidden and Limited cards is updated regularly and is
posted on the Yu-Gi-Oh! TCG Official Website.
This list is applied to official tournaments so please check it before
participating.
Official Website: www.yugioh-card.com
Forbidden & Limited Cards

Monster Tokens are monsters that appear on the field as the result
of a card's effect. They are not included in the Deck, and cannot be
sent anywhere other than the field, such as the hand or Graveyard.
When a Token is destroyed or returned to the hand or Deck, they are
simply removed from the field instead.
You can use official Token cards or use coins,
card sleeves, or any similar marker (as long
as it can indicate Attack Position or Defense
Position) as Monster Tokens and play them in
Monster Zones. Each Monster Token takes up 1
of your 5 Monster Zones. Their battle position
is always either face-up Attack Position or face-
up Defense Position. Tokens cannot be used as
an Xyz Material. Tokens on the field are treated
as Normal Monsters.
Monster Tokens
Battles and Chains
The turn player always starts with Priority, or the choice to
activate a card first, in each phase or step of their turn. As long as
the turn player has Priority, the opponent cannot activate cards
or effects, except for effects that activate automatically, like
Trigger or Flip effects.
The turn player can either:
TURN PLAYER'S PRIORITY
A player must pass Priority to the opponent when moving on to
the next phase or step. Strictly speaking, you would always declare
that you're passing Priority before the end of every phase and
step, and ask your opponent if they wish to play a card. However,
for ease of play, announcing the end of your phases or steps
implies giving up Priority. Therefore, when announcing the end of
a phase, your opponent can just say "Before the end of your phase,
I activate this card" and use a card.
• Use Priority to play a card or activate an effect OR
• Pass Priority to the opponent so they can activate an effect.
• The turn player starts with Priority to activate a card or effect
 first.
• After a card's activation, and at the end of each phase or step,
 Priority passes to the opponent.
4948


## Page 28

Other Rules

The number of cards in a player's hand and Decks, the cards in their
Graveyards, and each player's current LP are all public knowledge
and both players can verify these things at any time. If asked, you
must answer these things to your opponent truthfully. You are
allowed to pick up and verify the cards in your opponent's Graveyard
but you must ask their permission first. Also, you may not change the
order of the cards when verifying their Graveyard.
Public Knowledge

For cases like "Each player targets 1 monster," where both players
resolve an effect simultaneously, the turn player resolves the effect
first. In this example, after the turn player makes their selection, the
other player makes theirs.
If both players conduct actions simultaneously

If effects of Spell Speed 1 cards (like Trigger Effects) are activated at
the same time, they will be resolved in a special Chain. This Chain is
made starting with the turn player's mandatory effects. If there is only
1 effect, that will be Chain Link 1. If there are 2 or more effects, the turn
player builds the Chain starting with their mandatory effects, in any
order. Then the opponent continues the Chain with their mandatory
effects in any order. Afterwards, the turn player adds their optional
effects in any order, and finally the opponent adds their optional
effects in any order.
When multiple cards are activated simultaneously

Monsters with 0 ATK cannot destroy anything by battle. If two Attack
Position monsters with 0 ATK battle each other, neither monster is
destroyed.
0 ATK monsters

If there is a discrepancy between the basic rules and a card's effect, the
card effect takes precedence. For example, a monster can only attack
once per turn, but with a card effect, it is possible to attack twice.
Rules vs. Card Effects

You may need to place these on cards for some card effects. You
cannot place counters unless a card effect allows it. Cards may have
effects that change with the number of counters on them, or require
you to remove counters as a cost. Some counters have specific
names, such as "Spell Counter" or "Clock Counter." Other than their
names, each individual counter itself does not have any effects.
Counters

You can only create a Chain by responding to the activation of a card
or effect. Summoning a monster, Tributing, changing a monster's
battle position and paying costs are not effect activations and
therefore you cannot respond to those actions using a Chain.
Actions which cannot be Chained to

Monsters that are used to Xyz Summon are called "Xyz Materials",
and are placed underneath the Xyz Monster, to show that they are
attached to it. Monsters that have become Xyz Materials are not
treated as cards on the field. When an Xyz Monster leaves the field,
all of the Xyz Materials attached to it are sent to the Graveyard. If
an Xyz Monster is flipped face-down, or becomes controlled by the
opponent, the Xyz Materials are not sent to the Graveyard. They
remain attached to the Xyz Monster.
Xyz Materials

Some monsters have effects that activate when they "leave the field".
For example, these effects activate when the monster is sent to
the Graveyard, or is banished, or is returned to the hand or Extra
Deck. When a monster on the field is shuffled into the Main Deck, or
becomes an Xyz Material, it is no longer a card on the field, however
its effects that activate when it "leaves the field" will not activate.
Leaves the Field
Other Rules
5150


## Page 29

Other Rules
GlossaryGlossary
Other Rules
A card is destroyed when it is sent to the Graveyard due to battle
between monsters or by an effect that destroys a card. A card that
is returned from the field to the hand or Deck, or, that is sent to
the Graveyard as a cost or Tribute, is NOT considered "destroyed."
l Destroy
Discard means to send a card from your hand to the Graveyard.
This can happen because of a card effect or by adjusting the
number of cards in your hand during the End Phase.
l Discard
The effect of a card is the special ability written on it, like the effect
of a Spell, Trap, or Effect Monster. Costs that are needed to activate
an ability are not part of the effect. The conditions that describe
how to play a "Special Summon Monster" are also not an effect.
l Effects of Cards
In addition to Equip Spell Cards, sometimes Trap Cards or Monster Cards
can become equipped to a monster. Equipped Traps remain Trap Cards, but
equipped monsters are considered to be Equip Spells. The term "Equip Card"
includes all 3 kinds (standard Equip Spells, equipped Traps, and monsters
equipped to other monsters).If a Monster Card is equipped to another
monster, it remains equipped to that monster and cannot be moved to a
different target, even by card effects that would normally be able to do so.
EXCEPTION: Union monsters equipped by their own effects can be moved
by appropriate card effects.
l Equip Cards
Attacking directly means that a monster attacks a player instead of
attacking a monster. In this case, the damage to the player will be equal
to the monster's ATK. Some monsters have an effect that allows them to
attack directly even if the opponent controls a monster.
l Attack Directly
Although a card that has been used is normally sent to the Graveyard,
a card which is banished is separated from the field instead. You must
return your banished cards so you can use them for the next Duel.
l Banished Cards (Previously Remove from Play)
Battle damage is damage inflicted to a player by an attacking monster,
or by a battle between two monsters. This is different from damage from
the effect of an Effect Monster, Spell Card or Trap Card.
l Battle Damage
When "cards on the field" is written in card text, it means all the cards on
the Game Mat other than the Graveyard, Deck, and Extra Deck.
l Cards on the Field
Cards you "control" are the cards in your Monster Zone, Spell & Trap Zone,
Field Zone, and Pendulum Zone. Cards in your "possession" include all cards
you control, plus the cards in your hand, Deck, Extra Deck, Graveyard, your
banished cards, cards in the middle of being Summoned to your side of the
field, and Xyz Materials attached to monsters you control. If a player takes
control of a card from their opponent, move it to the new controller's side
of the field. If sent to the Graveyard, or returned to the hand or Deck, it
is always returned to the Graveyard / hand / Deck of the original owner.
l Control / Possess
A monster "battles" (and is "battling") starting from when it attacks or
is attacked. This includes both monsters attacking other monsters, and
monsters attacking a player's Life Points directly. When a card requires a
monster to have "battled" (past tense), the attack had to have reached the
damage calculation portion of the Damage Step in order for the monster to
have "battled". If the attack stops before damage calculation, the monster
did not "battle". (Note that an attack was still declared, however, so in
most cases the attacking monster cannot declare another attack.
l Battle / Battled
Card effects are sometimes separated with a colon (:) and/or semi-colon (;).
Text before the colon gives information on conditions to activate the effect,
and timing on when it happens. Text before a semi-colon is what you do
when the effect is activated. Text at the end of a sentence, after all colons
and semi-colons, is what you do at resolution of the effect.
l Colon (:) and Semi-colon (;)
5352


## Page 30

Other Rules
A card can be sent to the Graveyard in various ways. Destroying a card,
discarding, and Tributing a monster are all actions that send a card to
the Graveyard, and will normally activate "When this card is sent to the
Graveyard…" Trigger Effects.
EXCEPTION: When a banished card is moved to the Graveyard, it is not
considered to be "sent to the Graveyard".
l Send to the Graveyard
Playing a card face-down is called a Set. For Monster Cards, playing it in
face-down Defense Position is called a Set. Any card that is face-down
on the field is a Set card.
l Set
There is no rule for how to shuffle, but while shuffling you cannot look at
the cards you are shuffling, or arrange the cards and then shuffle them.
l Shuff le
Tributing is sending a monster you control to the Graveyard. You can
Tribute a face-up or face-down monster, unless otherwise specified.
Tributing a monster is one possible cost for Summoning a monster or
activating an effect. A monster sent to the Graveyard by Tributing is not
treated as "destroyed."
l Tribute
The Original ATK (or DEF) is the number of ATK (or DEF) points printed on
the Monster Card. This does not include an increase from an Equip Spell
Card or other card effect.
l Original ATK (or DEF)
To pay a cost is an action required by a player in order to activate a card,
an effect, or to Summon a monster. Tributing to Tribute Summon a Level
5 monster is an example of a cost. Other common costs are discarding,
paying LP , or banishing cards. You have to pay any costs before you
declare the activation of the card. Even if the activation of the card is
negated, you cannot get a refund of the cost that you have paid.
l Pay a Cost
Some monsters can inflict piercing battle damage when they attack a
Defense Position monster. This means that you inflict damage to your
opponent's LP equal to the difference between the attacking monster's
ATK and the defending monster's DEF.
l Piercing Battle Damage
When a card effect says to choose a card randomly, there is no official
way of doing so, it is fine as long as neither player has a way of knowing
which card is being chosen.
l Random
When an effect says to reveal a card, you show it to both players. You
may have to reveal a face-down card, a card from your hand, or from the
top of your Deck. Revealing a card does not activate the card or its Flip
effect. Normally, revealed cards are returned to their original position
after being looked at by both players.
l Reveal
Whenever an effect instructs you to add a card from your Deck to your
hand, or to Special Summon a monster from your Deck, you can pick
up your Deck and search through it for the appropriate card. You must
shuffle your Deck after any time you search it and let your opponent
shuffle or cut. You cannot activate an effect to search your Deck for a
card if there are no cards that meet the requirements in your Deck.
l Search your DeckWhen a card says to "excavate" cards from your Deck, you reveal those
cards to both players. Then, before you do anything else, apply the
instructions from the card effect that excavated them. Cards that are
being excavated are still treated as being in the Deck until sent elsewhere
by the card instructions.
l Excavate
Other Rules
A monster that is equipped with an Equip Card is an "equipped monster."
When this monster is destroyed or flipped face-down, the equipped
card loses its target, and is destroyed and sent to the Graveyard.
l Equipped Monster
5554


## Page 31

For further information on
the Yu-Gi-Oh! TRADING CARD GAME,
please vis it
www.yugioh-card.co m
For general questions, Email us at
us-cardsuppo rt@konami.co m
For rules ques tions only,
you can Email us at
us-ygorules@konami.co m
For further inform ation on
the Yu-Gi-Oh! TRADING CARD GAME ,
please visit
www.yugioh-card.co m
For general questions, Email us at
us-cardsupport@ konami.com
at
us-cardsupport@ konami.com
For rules questions on ly,
you can Email us at
us-ygorules@konami.co m
For a complete Rulebook, visit
www.yugioh-card.com/en/rulebook
For a complete Rulebook, visit
www.yugioh-card.com/en/rulebook
For a complete Rulebook, visit
www.yugioh-card.com/en/rulebook
For a complete Rulebook, visit
www.yugioh-card.com/en/rulebook
To watch the Link Summoning
Tutorial, visit
www.yugioh-card.com/en/linksummon
To watch the Link Summoning
Tutorial, visit
www.yugioh-card.com/en/linksummon
To watch the Link Summoning
Tutorial, visit
www.yugioh-card.com/en/linksummon
To watch the Link Summoning
Tutorial, visit
www.yugioh-card.com/en/linksummon
Set content subject to change. No specific card rarity is guaranteed to exist within an individual
pack, box or case unless otherwise indicated. Manufactured and distributed by Konami Digital
Entertainment, Inc. 2381 Rosecrans Avenue, Suite 200, El Segundo, CA 90245, USA. Made in the USA.
For questions please email us at: us-cardsupport@konami.com
Set content subject to change. No specific card rarity is guaranteed to exist within an individual
pack, box or case unless otherwise indicated. Manufactured and distributed by Konami Digital
Entertainment, Inc. 2381 Rosecrans Avenue, Suite 200, El Segundo, CA 90245, USA. Made in the USA.
For questions please email us at: us-cardsupport@konami.com
