"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 消息发送器测试
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from chat.pipeline.sender import MessageSender


class TestMessageSender:
    @pytest.mark.asyncio
    async def test_send_single_message(self) -> None:
        send_func = AsyncMock()
        sender = MessageSender(send_func)
        await sender.send("hello")
        send_func.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_batch(self) -> None:
        send_func = AsyncMock()
        sender = MessageSender(send_func)
        await sender.send_batch(["part1", "part2", "part3"])
        assert send_func.call_count == 3
        send_func.assert_any_call("part1")
        send_func.assert_any_call("part2")
        send_func.assert_any_call("part3")

    @pytest.mark.asyncio
    async def test_send_batch_empty(self) -> None:
        send_func = AsyncMock()
        sender = MessageSender(send_func)
        await sender.send_batch([])
        send_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_without_func_no_error(self) -> None:
        """无 send_func 时不应崩溃。"""
        sender = MessageSender(None)
        await sender.send("hello")  # 不应抛异常

    @pytest.mark.asyncio
    async def test_send_batch_without_func_no_error(self) -> None:
        sender = MessageSender(None)
        await sender.send_batch(["a", "b"])  # 不应抛异常