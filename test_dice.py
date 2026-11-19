"""骰娘核心自测：python test_dice.py（不需要装 AstrBot）。"""

from __future__ import annotations

import random
import re

from dice_core import DiceError, DiceTerm, parse, roll

PASS = 0


def check(cond: bool, label: str) -> None:
    global PASS
    if not cond:
        raise AssertionError(label)
    PASS += 1


def total_of(result: str) -> int:
    return int(result.rsplit(" = ", 1)[1])


class FixedRng:
    """按给定序列出数，用来精确验证爆骰/保留最高最低。"""

    def __init__(self, values: list[int]) -> None:
        self.values = iter(values)

    def randint(self, a: int, b: int) -> int:
        value = next(self.values)
        assert a <= value <= b, (value, a, b)
        return value


# --- 解析 -------------------------------------------------------------------
check(parse(" 2D6 + 3 ") == [(1, DiceTerm(2, 6, None, 0, False)), (1, 3)], "空格与大小写")
check(parse("d%") == [(1, DiceTerm(1, 100, None, 0, False))], "百分骰")
check(parse("1d6-1") == [(1, DiceTerm(1, 6, None, 0, False)), (-1, 1)], "减修正")
check(parse("-1+2d6") == [(-1, 1), (1, DiceTerm(2, 6, None, 0, False))], "前置负号")
check(parse("4d6kh3") == [(1, DiceTerm(4, 6, "kh", 3, False))], "取最高")
check(parse("2d20kl1") == [(1, DiceTerm(2, 20, "kl", 1, False))], "取最低")
check(parse("1d6!") == [(1, DiceTerm(1, 6, None, 0, True))], "爆骰")
check(parse("4d6!kh3") == parse("4d6kh3!") == [(1, DiceTerm(4, 6, "kh", 3, True))], "爆骰与保留两种顺序")

for bad in (
    "",
    "abc",
    "d",
    "1dd6",
    "1d6*2",
    "1d6+",
    "1d6kh0",
    "1d6kh7",
    "0d6",
    "101d6",
    "1d1001",
    "1d6+1000001",
    "x" * 65,
    "__import__('os')",
):
    try:
        parse(bad)
    except DiceError:
        PASS += 1
    else:
        raise AssertionError(f"非法输入没被拦住：{bad!r}")


# --- 掷骰范围 -----------------------------------------------------------------
rng = random.Random(20261119)
for expr, lo, hi in (
    ("1d20", 1, 20),
    ("2d6+3", 5, 15),
    ("1d6-1", 0, 5),
    ("d%", 1, 100),
    ("4d6kh3", 3, 18),
    ("2d20kl1", 1, 20),
    ("2d6+1d20-2", 1, 30),
):
    for _ in range(400):
        check(lo <= total_of(roll(expr, rng)) <= hi, f"范围 {expr}")

vals = [total_of(roll("1d6", rng)) for _ in range(6000)]
check(3.3 < sum(vals) / len(vals) < 3.7, "1d6 均值")
check(set(vals) == {1, 2, 3, 4, 5, 6}, "1d6 六个面都出现")


# --- 保留最高 / 最低、爆骰 ------------------------------------------------------
r = roll("3d6kh2", FixedRng([6, 2, 5]))
check(total_of(r) == 11 and r == "🎲 3d6kh2 = 6+2(弃)+5 = 11", f"kh2: {r}")

r = roll("3d6kl2", FixedRng([6, 2, 5]))
check(total_of(r) == 7 and r == "🎲 3d6kl2 = 6(弃)+2+5 = 7", f"kl2: {r}")

r = roll("1d6!", FixedRng([6, 6, 3]))
check(total_of(r) == 15 and "(6+6+3)" in r, f"爆骰: {r}")

r = roll("1d6!", FixedRng([4]))
check(total_of(r) == 4 and "(" not in r, f"没爆: {r}")

# 一直掷最大面也不能无限循环：最多爆 20 次
always_max = type("AlwaysMax", (), {"randint": lambda self, a, b: b})()
r = roll("1d6!", always_max)
check(total_of(r) == 21 * 6 and r.count("+") == 20, f"爆骰上限: {r}")

# 爆骰总和参与 kh 比较，而不是只看第一次点数
r = roll("2d6!kh1", FixedRng([6, 6, 1, 2]))
check(total_of(r) == 13 and "(弃)" in r, f"爆骰+kh: {r}")


# --- 输出格式 ------------------------------------------------------------------
check(re.fullmatch(r"🎲 1d20 = \d+ = \d+", roll("1d20", rng)) is not None, "输出格式")
check("  " not in roll("  1D20   +   3 ", rng), "显示去掉多余空格")

print(f"骰娘核心自测：{PASS} 项全过")
