"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 防抖合并器测试 — 窗口合并、取消、错误恢复
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from chat.pipeline.debounce import Debouncer

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(enabled: bool = True, window: float = 3.0) -> object:
    cfg = type("DebounceConfig", (), {})()
    cfg.enabled = enabled
    cfg.window = window
    return cfg


# ── 测试 ──────────────────────────────────────────────────────────


class TestDebounceBasic:
    @pytest.mark.asyncio
    async def test_disabled_passes_through_immediately(self) -> None:
        """禁用时消息直接透传，不合并。"""
        db = Debouncer(make_config(enabled=False))
        callback = AsyncMock()

        await db.submit("session-1", "hello", callback)
        callback.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_single_message_flushed_after_window(self) -> None:
        """单条消息在窗口结束后发送。"""
        db = Debouncer(make_config(window=0.1))
        callback = AsyncMock()

        await db.submit("session-1", "hello", callback)
        assert callback.call_count == 0  # 尚未发送

        await asyncio.sleep(0.15)
        callback.assert_called_once_with("hello")

    @pytest.mark.asyncio
    async def test_multiple_messages_merged(self) -> None:
        """窗口内多条消息合并为一条。"""
        db = Debouncer(make_config(window=0.1))
        callback = AsyncMock()

        await db.submit("session-1", "part1", callback)
        await db.submit("session-1", "part2", callback)
        await db.submit("session-1", "part3", callback)

        await asyncio.sleep(0.15)
        callback.assert_called_once_with("part1\npart2\npart3")

    @pytest.mark.asyncio
    async def test_window_resets_on_each_message(self) -> None:
        """每条新消息重置窗口计时。"""
        db = Debouncer(make_config(window=0.1))
        callback = AsyncMock()

        await db.submit("session-1", "a", callback)
        await asyncio.sleep(0.06)
        await db.submit("session-1", "b", callback)  # 重置窗口
        await asyncio.sleep(0.06)
        assert callback.call_count == 0  # 仍未发送（窗口重置了）

        await asyncio.sleep(0.08)
        callback.assert_called_once_with("a\nb")

    @pytest.mark.asyncio
    async def test_different_sessions_independent(self) -> None:
        """不同会话独立防抖。"""
        db = Debouncer(make_config(window=0.1))
        cb1 = AsyncMock()
        cb2 = AsyncMock()

        await db.submit("session-1", "a", cb1)
        await db.submit("session-2", "x", cb2)

        await asyncio.sleep(0.15)
        cb1.assert_called_once_with("a")
        cb2.assert_called_once_with("x")


class TestDebounceCancel:
    @pytest.mark.asyncio
    async def test_cancel_stops_timer(self) -> None:
        """取消后不应触发回调。"""
        db = Debouncer(make_config(window=0.5))
        callback = AsyncMock()

        await db.submit("session-1", "hello", callback)
        db.cancel("session-1")

        await asyncio.sleep(0.6)
        assert callback.call_count == 0

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_session_no_error(self) -> None:
        """取消不存在的会话不应抛异常。"""
        db = Debouncer(make_config())
        db.cancel("nonexistent")


class TestDebounceEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_message(self) -> None:
        """空消息不应导致问题。"""
        db = Debouncer(make_config(window=0.1))
        callback = AsyncMock()

        await db.submit("session-1", "", callback)
        await asyncio.sleep(0.15)
        callback.assert_called_once_with("")

    @pytest.mark.asyncio
    async def test_callback_error(self) -> None:
        """回调抛异常不应崩溃。"""
        db = Debouncer(make_config(window=0.1))
        callback = AsyncMock(side_effect=RuntimeError("send failed"))

        await db.submit("session-1", "hello", callback)
        await asyncio.sleep(0.15)
        # 不应抛异常，callback 被调用后异常被捕获
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_enabled(self) -> None:
        db = Debouncer(make_config(enabled=True))
        assert db.is_enabled() is True

        db2 = Debouncer(make_config(enabled=False))
        assert db2.is_enabled() is False