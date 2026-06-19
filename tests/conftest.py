"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : Shared test fixtures and utilities
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# ── 常量 ──────────────────────────────────────────────────────────

TEST_USER_ID = "123456789"
TEST_GROUP_ID = "987654321"
TEST_SESSION_ID = f"g{TEST_GROUP_ID}_u{TEST_USER_ID}"
TEST_PRIVATE_SESSION_ID = f"u{TEST_USER_ID}"


# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_event(
    *,
    user_id: str = TEST_USER_ID,
    group_id: str | None = TEST_GROUP_ID,
    text: str = "hello",
    message_type: str = "group",
    self_id: str = "10000",
    message: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> MagicMock:
    """创建模拟的 NoneBot MessageEvent。

    Args:
        user_id: 用户 ID。
        group_id: 群 ID，None 表示私聊。
        text: 消息纯文本。
        message_type: 消息类型（group/private）。
        self_id: 机器人自身 QQ 号。
        message: 消息段列表，None 则自动生成文本段。
        **kwargs: 其他事件属性。

    Returns:
        模拟的 MessageEvent 对象。
    """
    event = MagicMock()
    event.user_id = int(user_id)
    event.group_id = int(group_id) if group_id is not None else None
    event.self_id = self_id
    event.message_type = message_type
    event.message_id = kwargs.get("message_id", "msg-001")

    if message is not None:
        event.message = message
    else:
        event.message = [{"type": "text", "data": {"text": text}}]

    event.get_plaintext = MagicMock(return_value=text)
    event.get_message = MagicMock(return_value=event.message)
    event.is_tome = MagicMock(return_value=False)

    for k, v in kwargs.items():
        setattr(event, k, v)

    return event


def make_send_func() -> AsyncMock:
    """创建模拟的发送函数。"""
    return AsyncMock()


def make_bot() -> MagicMock:
    """创建模拟的 NoneBot Bot 对象。"""
    bot = MagicMock()
    bot.send = AsyncMock()
    return bot


# ── 时间工具 ──────────────────────────────────────────────────────


class MockTime:
    """可控的时间模拟器。

    使用方式：
        with patch('time.time', mock_time.time):
            mock_time.advance(5.0)
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def set(self, timestamp: float) -> None:
        self._now = timestamp


# ── 异步工具 ──────────────────────────────────────────────────────


async def gather_with_timeout(*coros: Any, timeout: float = 5.0) -> list[Any]:
    """带超时的 gather，避免测试挂起。"""
    return await asyncio.wait_for(asyncio.gather(*coros), timeout=timeout)