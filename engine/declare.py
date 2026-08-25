"""Evaluating the card-declaration filter that MSG_ANNOUNCE_CARD carries.

"Declare a card name" - Crush Card Virus, Deck Devastation Virus, the older
virus cards - does not come with a menu. The engine sends a filter written in
a small stack language, and any card in the pool that satisfies it is a legal
answer. `is_declarable` in playerop.cpp is the evaluator; this is a port of it,
plus a search over the card database for something the filter accepts.

Ported rather than approximated because the alternative is guessing a card
name and being rejected, which the engine reports as MSG_RETRY with no
explanation - and a policy that keeps guessing simply hangs.
"""

from __future__ import annotations

from engine import constants as K

_TYPE_TOKEN_MONSTER = K.TYPE_MONSTER + K.TYPE_TOKEN

#: Two cards the core exempts by code, because they print two names.
CARD_MARINE_DOLPHIN = 78734254
CARD_TWINKLE_MOSS = 13857930


def _setcodes(packed: int) -> list[int]:
    """Unpack the cdb's setcode column: up to four 16-bit archetype codes."""
    return [(packed >> (16 * i)) & 0xFFFF for i in range(4)]


def is_declarable(row: tuple, opcodes: list[int]) -> bool:
    """Whether a `CardDB.row` tuple satisfies the filter.

    `row` is (id, ot, alias, setcode, type, atk, def, level, race, attribute),
    which carries every field the opcode language can read.
    """
    code, _ot, alias, setcode, ctype, _atk, _def, _lv, race, attribute = row
    stack: list[int] = []
    allow_alias = allow_token = False

    def binary(fn):
        if len(stack) >= 2:
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(int(fn(lhs, rhs)))

    def unary(fn):
        if stack:
            stack.append(int(fn(stack.pop())))

    for op in opcodes:
        if op == K.OPCODE_ADD:
            binary(lambda a, b: a + b)
        elif op == K.OPCODE_SUB:
            binary(lambda a, b: a - b)
        elif op == K.OPCODE_MUL:
            binary(lambda a, b: a * b)
        elif op == K.OPCODE_DIV:
            binary(lambda a, b: a // b if b else 0)
        elif op == K.OPCODE_AND:
            binary(lambda a, b: bool(a) and bool(b))
        elif op == K.OPCODE_OR:
            binary(lambda a, b: bool(a) or bool(b))
        elif op == K.OPCODE_NEG:
            unary(lambda a: -a)
        elif op == K.OPCODE_NOT:
            unary(lambda a: not a)
        elif op == K.OPCODE_BAND:
            binary(lambda a, b: a & b)
        elif op == K.OPCODE_BOR:
            binary(lambda a, b: a | b)
        elif op == K.OPCODE_BXOR:
            binary(lambda a, b: a ^ b)
        elif op == K.OPCODE_BNOT:
            unary(lambda a: ~a)
        elif op == K.OPCODE_LSHIFT:
            binary(lambda a, b: a << b)
        elif op == K.OPCODE_RSHIFT:
            binary(lambda a, b: a >> b)
        elif op == K.OPCODE_ISCODE:
            unary(lambda a: code == (a & 0xFFFFFFFF))
        elif op == K.OPCODE_ISTYPE:
            unary(lambda a: ctype & a)
        elif op == K.OPCODE_ISRACE:
            unary(lambda a: race & a)
        elif op == K.OPCODE_ISATTRIBUTE:
            unary(lambda a: attribute & a)
        elif op == K.OPCODE_GETCODE:
            stack.append(code)
        elif op == K.OPCODE_GETTYPE:
            stack.append(ctype)
        elif op == K.OPCODE_GETRACE:
            stack.append(race)
        elif op == K.OPCODE_GETATTRIBUTE:
            stack.append(attribute)
        elif op == K.OPCODE_ISSETCARD:
            if stack:
                want = stack.pop()
                settype, setsubtype = want & 0xFFF, want & 0xF000
                stack.append(int(any(
                    (sc & 0xFFF) == settype and (sc & 0xF000 & setsubtype) == setsubtype
                    for sc in _setcodes(setcode)
                )))
        elif op == K.OPCODE_ALLOW_ALIASES:
            allow_alias = True
        elif op == K.OPCODE_ALLOW_TOKENS:
            allow_token = True
        else:
            stack.append(op)

    if len(stack) != 1 or stack[0] == 0:
        return False
    if code in (CARD_MARINE_DOLPHIN, CARD_TWINKLE_MOSS):
        return True
    if not allow_alias and alias:
        return False
    if not allow_token and (ctype & _TYPE_TOKEN_MONSTER) == _TYPE_TOKEN_MONSTER:
        return False
    return True


def find_declarable(db, opcodes: list[int], prefer: list[int] | None = None) -> int | None:
    """A card code the filter accepts, or None if the pool holds none.

    `prefer` is tried first - pass codes already in the duel, since a filter
    is usually written around cards that are actually in play, and checking a
    handful beats scanning thirteen thousand.
    """
    for code in prefer or []:
        row = db.row(code)
        if row and is_declarable(row, opcodes):
            return code
    for row in db.all_rows():
        if is_declarable(row, opcodes):
            return row[0]
    return None
