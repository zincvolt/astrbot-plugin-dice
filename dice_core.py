"""骰式解析与掷骰核心，纯标准库，不依赖 AstrBot，可单独测试。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

MAX_EXPR_LEN = 64
MAX_COUNT = 100
MAX_SIDES = 1000
MAX_MODIFIER = 1_000_000
MAX_EXPLODE = 20
MAX_TOTAL_ROLLS = 200

USAGE = (
    "用法：/r 1d20、/r 2d6+3、/r d%、/r 4d6kh3、/r 2d20kl1、/r 1d6!\n"
    "kh=取最高，kl=取最低，!=爆骰重掷"
)

# keep 与爆骰标记允许两种顺序：4d6kh3! 和 4d6!kh3
_DICE_RE = re.compile(
    r"(?P<count>\d*)d(?P<sides>\d+|%)"
    r"(?P<keep>(?:kh|kl)\d+)?(?P<explode>!?)(?P<keep2>(?:kh|kl)\d+)?",
    re.I,
)
_INT_RE = re.compile(r"\d+")


class DiceError(ValueError):
    """骰式写得不合法，或者超出上限。"""


@dataclass(frozen=True)
class DiceTerm:
    count: int
    sides: int
    keep: str | None
    keep_n: int
    explode: bool


def parse(expr: str) -> list[tuple[int, int | DiceTerm]]:
    """把骰式解析成 `[(符号, 常数或骰子项), ...]`，符号 +1 / -1。"""
    s = re.sub(r"\s+", "", expr).lower()
    if not s:
        raise DiceError("没写骰式")
    if len(s) > MAX_EXPR_LEN:
        raise DiceError(f"骰式太长（最多 {MAX_EXPR_LEN} 字符）")

    terms: list[tuple[int, int | DiceTerm]] = []
    pos = 0
    sign = 1
    if s[0] in "+-":
        sign = -1 if s[0] == "-" else 1
        pos = 1

    while pos < len(s):
        dice = _DICE_RE.match(s, pos)
        if dice:
            count_raw = dice.group("count")
            count = int(count_raw) if count_raw else 1
            sides_raw = dice.group("sides")
            sides = 100 if sides_raw == "%" else int(sides_raw)
            keep_raw = dice.group("keep") or dice.group("keep2")
            keep: str | None = None
            keep_n = 0
            if keep_raw:
                keep = keep_raw[:2].lower()
                keep_n = int(keep_raw[2:])
            explode = bool(dice.group("explode"))

            if not 1 <= count <= MAX_COUNT:
                raise DiceError(f"一次最多掷 {MAX_COUNT} 颗骰子")
            if not 1 <= sides <= MAX_SIDES:
                raise DiceError(f"骰子最多 {MAX_SIDES} 面")
            if keep and not 1 <= keep_n <= count:
                raise DiceError(f"保留数量要在 1~{count} 之间")
            if count > MAX_TOTAL_ROLLS:
                raise DiceError("总掷骰次数超限")
            terms.append((sign, DiceTerm(count, sides, keep, keep_n, explode)))
            pos = dice.end()
        else:
            number = _INT_RE.match(s, pos)
            if not number:
                raise DiceError(f"看不懂：{s[pos:pos + 8]}")
            value = int(number.group())
            if value > MAX_MODIFIER:
                raise DiceError("修正值太大")
            terms.append((sign, value))
            pos = number.end()

        if pos == len(s):
            break
        op = s[pos]
        if op not in "+-":
            raise DiceError(f"只能写 + 或 -，不能写 {op}")
        sign = -1 if op == "-" else 1
        pos += 1
        if pos >= len(s):
            raise DiceError("式子末尾缺数字")

    return terms


def _roll_term(term: DiceTerm, rng: random.Random) -> tuple[int, str]:
    """掷一组骰子，返回（计入的合计，用于展示的式子）。"""
    groups: list[list[int]] = []
    rolled = 0
    for _ in range(term.count):
        group: list[int] = []
        face = rng.randint(1, term.sides)
        group.append(face)
        rolled += 1
        while (
            term.explode
            and face == term.sides
            and len(group) <= MAX_EXPLODE
            and rolled < MAX_TOTAL_ROLLS
        ):
            face = rng.randint(1, term.sides)
            group.append(face)
            rolled += 1
        groups.append(group)

    values = [sum(group) for group in groups]
    kept = set(range(len(groups)))
    if term.keep:
        ordered = sorted(
            range(len(groups)),
            key=lambda i: values[i],
            reverse=(term.keep == "kh"),
        )
        kept = set(ordered[: term.keep_n])

    pieces: list[str] = []
    for i, group in enumerate(groups):
        if len(group) == 1:
            text = str(group[0])
        else:
            text = "(" + "+".join(str(x) for x in group) + ")"
        if i not in kept:
            text += "(弃)"
        pieces.append(text)
    return sum(values[i] for i in kept), "+".join(pieces)


def roll(expr: str, rng: random.Random | None = None) -> str:
    """解析并掷骰；返回一行可直接发出去的结果。"""
    terms = parse(expr)
    rng = rng or random.SystemRandom()
    total = 0
    pieces: list[str] = []
    for sign, item in terms:
        if isinstance(item, DiceTerm):
            value, text = _roll_term(item, rng)
        else:
            value, text = item, str(item)
        total += sign * value
        if not pieces:
            pieces.append(("-" if sign < 0 else "") + text)
        else:
            pieces.append(("-" if sign < 0 else "+") + text)

    shown = re.sub(r"\s+", "", expr).lower()
    return f"🎲 {shown} = {''.join(pieces)} = {total}"
