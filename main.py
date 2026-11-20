"""桌游骰娘：按标准骰式输出随机数，不跟其他插件抢指令。

只注册一条精确指令 `/r`（别名 `/roll` `/dice` `/骰` `/掷骰` `/投骰`）。
没有全局 `event_message_type(ALL)` 处理器，没有正则兜底，也不会去猜没写清楚的
消息——只有指令名完全命中才会接管事件（`stop_event()`），其他 `/` 指令一律
不碰。这一点是刻意的：本项目的兽聚插件曾用「带地名就当展会查询」的兜底把
别人的斜杠指令吞掉，修了很久。

支持的骰式（大小写不敏感，空格随意）：

    /r 1d20          一颗二十面骰
    /r 2d6+3         两颗六面骰加 3
    /r 1d6-1         减修正
    /r d%            百分骰（1~100）
    /r 4d6kh3        四颗六面骰取最高三颗
    /r 2d20kl1       两颗二十面骰取最低一颗（劣势）
    /r 1d6!          掷出最大面时重掷，最多 20 次

解析和掷骰逻辑在 `dice_core.py`，纯标准库、可单测。不用 `eval` / `exec`；
骰子数、面数、修正值、总掷骰次数都有上限。随机数用 `random.SystemRandom()`。

零配置：没有 json、没有管理员开关、不记录状态，复制到插件目录就能用。
"""

from __future__ import annotations

import re
from sys import maxsize

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, filter

from .dice_core import DiceError, USAGE, roll

# 指令自声明：/权限 列表 按插件分组展示用（插件开发规范要求，见 docs/PLUGIN-DEV.md）
DECLARED_COMMANDS: dict[str, tuple[str, str]] = {
    "/r <表达式>": ("掷骰（同义别名：roll/dice/骰/掷骰/投骰）", "公开"),
}

ALIASES = {"roll", "dice", "骰", "掷骰", "投骰"}


class Main(star.Star):
    """骰娘插件入口：只有精确指令命中才说话。"""

    def __init__(self, context: star.Context) -> None:
        self.context = context
        logger.info("[dice] ready")

    @staticmethod
    def _expr_from_event(event: AstrMessageEvent) -> str:
        """去掉指令名，拿到骰式；指令名由框架保证一定命中。"""
        text = re.sub(r"\s+", " ", (event.get_message_str() or "").strip())
        if not text or " " not in text:
            return ""
        return text.split(" ", 1)[1].strip()

    # priority=maxsize：和 furcon 的展会卡同档，高于复读机/判官/群聊上下文。
    # 命中后 stop_event，后面的 handler 直接 break（框架在调用每个 handler 前
    # 都查 is_stopped），不会复读、不会由大模型补一句；不命中时框架根本不会
    # 激活这个 handler。
    @filter.command("r", alias=ALIASES, priority=maxsize)
    async def roll_command(self, event: AstrMessageEvent) -> None:
        """掷骰：/r 1d20、/r 2d6+3、/r 4d6kh3、/r d%"""
        expr = self._expr_from_event(event)
        if not expr:
            event.stop_event()
            await event.send(event.plain_result(USAGE))
            return
        try:
            result = roll(expr)
        except DiceError as e:
            logger.info(f"[dice] bad expr {expr!r}: {e}")
            event.stop_event()
            await event.send(event.plain_result(f"骰子没读懂：{e}\n{USAGE}"))
            return
        logger.info(f"[dice] {expr} -> {result}")
        event.stop_event()
        await event.send(event.plain_result(result))
