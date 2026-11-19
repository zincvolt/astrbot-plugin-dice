"""指令层自测：python test_handler.py（要在装了 AstrBot 的环境里跑）。

验证两件事：
1. CommandFilter 只认这 6 个精确指令，不会吞 `/help`、`/下次展` 之类；
2. handler 命中后一定 stop_event，且只发一条消息。
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

# 本机 AstrBot 源码位置；搬到别的机器用 ASTRBOT_ROOT 覆盖
sys.path.insert(
    0,
    os.environ.get("ASTRBOT_ROOT", r"D:\QQNTBOT\apps\AstrBot"),
)

from astrbot.core.star.filter.command import CommandFilter  # noqa: E402

_PLUGIN_DIR = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location(
    "dice_plugin",
    _PLUGIN_DIR / "main.py",
    submodule_search_locations=[str(_PLUGIN_DIR)],
)
assert _SPEC and _SPEC.loader
_PLUGIN = importlib.util.module_from_spec(_SPEC)
sys.modules["dice_plugin"] = _PLUGIN
_SPEC.loader.exec_module(_PLUGIN)
ALIASES, Main = _PLUGIN.ALIASES, _PLUGIN.Main

PASS = 0


def check(cond: bool, label: str) -> None:
    global PASS
    if not cond:
        raise AssertionError(label)
    PASS += 1


class FakeEvent:
    def __init__(self, text: str, wake: bool = True) -> None:
        self.text = text
        self.is_at_or_wake_command = wake
        self.sent: list[str] = []
        self.stopped = False
        self.extras: dict = {}

    def get_message_str(self) -> str:
        return self.text

    def plain_result(self, text: str) -> str:
        return text

    async def send(self, result: str) -> None:
        self.sent.append(result)

    def stop_event(self) -> None:
        self.stopped = True

    def set_extra(self, key: str, value: object) -> None:
        self.extras[key] = value

    def get_extra(self, key: str, default: object = None) -> object:
        return self.extras.get(key, default)


async def _dummy_handler(self, event) -> None:  # noqa: ANN001
    pass


cmd_filter = CommandFilter("r", set(ALIASES))
cmd_filter.init_handler_md(type("MD", (), {"handler": _dummy_handler})())
for text in (
    "r 1d20",
    "roll 2d6+3",
    "dice d%",
    "骰 4d6kh3",
    "掷骰 2d20kl1",
    "投骰 1d6!",
):
    check(cmd_filter.filter(FakeEvent(text), None), f"应命中：{text}")

for text in (
    "help",
    "sid",
    "下次展",
    "判官 状态",
    "reset",
    "rollcall",
    "骰子",
    "dicey 1d20",
):
    check(not cmd_filter.filter(FakeEvent(text), None), f"不该命中：{text}")

check(
    not cmd_filter.filter(FakeEvent("r 1d20", wake=False), None),
    "没有唤醒前缀时不命中",
)

bot = Main(None)  # type: ignore[arg-type]
for text in ("r 1d20", "骰 4d6kh3", "dice bad", "roll"):
    event = FakeEvent(text)
    asyncio.run(bot.roll_command(event))
    check(event.stopped, f"必须停事件：{text}")
    check(len(event.sent) == 1, f"只发一条：{text}")
    check(bool(event.sent[0]), f"不能发空消息：{text}")

event = FakeEvent("r 1d20")
asyncio.run(bot.roll_command(event))
check(event.sent[0].startswith("🎲 1d20 = "), "输出格式")

print(f"骰娘指令层自测：{PASS} 项全过")
