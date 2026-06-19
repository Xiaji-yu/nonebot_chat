"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 去重测试 — 内容哈希 + 时间窗口
"""

from __future__ import annotations

import pytest

from chat.pipeline.dedup import check as dedup_check
from chat.pipeline.dedup import reset as dedup_reset


@pytest.mark.asyncio
async def test_dedup_first_message_not_duplicate() -> None:
    """第一条消息不应被判定为重复。"""
    await dedup_reset()
    result = await dedup_check("session-1", "hello", window=5.0)
    assert result is False


@pytest.mark.asyncio
async def test_dedup_same_content_within_window_is_duplicate() -> None:
    """相同内容在窗口内重复发送应被拦截。"""
    await dedup_reset()
    assert (await dedup_check("session-1", "hello", window=5.0)) is False
    assert (await dedup_check("session-1", "hello", window=5.0)) is True


@pytest.mark.asyncio
async def test_dedup_different_content_not_duplicate() -> None:
    """不同内容不应被拦截。"""
    await dedup_reset()
    assert (await dedup_check("session-1", "hello", window=5.0)) is False
    assert (await dedup_check("session-1", "world", window=5.0)) is False


@pytest.mark.asyncio
async def test_dedup_same_content_different_session_not_duplicate() -> None:
    """不同会话的相同内容互不影响。"""
    await dedup_reset()
    assert (await dedup_check("session-1", "hello", window=5.0)) is False
    assert (await dedup_check("session-2", "hello", window=5.0)) is False


@pytest.mark.asyncio
async def test_dedup_window_expired_not_duplicate() -> None:
    """窗口过期后相同内容不再判重。"""
    from unittest.mock import patch

    await dedup_reset()
    # 使用 mock time 控制时间
    mock_time = _make_mock_time(0.0)
    with patch("chat.pipeline.dedup.time.time", mock_time):
        assert (await dedup_check("session-1", "hello", window=5.0)) is False
        assert (await dedup_check("session-1", "hello", window=5.0)) is True

        # 推进到窗口外
        mock_time.set(6.0)
        assert (await dedup_check("session-1", "hello", window=5.0)) is False


@pytest.mark.asyncio
async def test_dedup_empty_content() -> None:
    """空内容不应导致异常。"""
    await dedup_reset()
    assert (await dedup_check("session-1", "", window=5.0)) is False
    assert (await dedup_check("session-1", "", window=5.0)) is True


@pytest.mark.asyncio
async def test_dedup_unicode_content() -> None:
    """Unicode 内容（中文、emoji）正常去重。"""
    await dedup_reset()
    assert (await dedup_check("session-1", "你好世界 🌍", window=5.0)) is False
    assert (await dedup_check("session-1", "你好世界 🌍", window=5.0)) is True


@pytest.mark.asyncio
async def test_dedup_very_long_content() -> None:
    """超长内容正常去重。"""
    await dedup_reset()
    long_text = "x" * 10000
    assert (await dedup_check("session-1", long_text, window=5.0)) is False
    assert (await dedup_check("session-1", long_text, window=5.0)) is True


@pytest.mark.asyncio
async def test_dedup_reset_clears_all() -> None:
    """reset 后所有记录清空。"""
    await dedup_reset()
    await dedup_check("session-1", "hello", window=5.0)
    await dedup_check("session-2", "world", window=5.0)

    await dedup_reset()
    # reset 后两个都应不重复
    assert (await dedup_check("session-1", "hello", window=5.0)) is False
    assert (await dedup_check("session-2", "world", window=5.0)) is False


# ── 工具 ──────────────────────────────────────────────────────────


def _make_mock_time(start: float) -> object:
    state = {"now": start}

    def mock_time_fn() -> float:
        return state["now"]

    def set_time(t: float) -> None:
        state["now"] = t

    mock_time_fn.set = set_time  # type: ignore[attr-defined]
    return mock_time_fn