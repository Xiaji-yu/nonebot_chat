"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 频控器测试 — 滑动窗口、会话隔离、边界条件
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from chat.pipeline.ratelimit import RateLimiter

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(
    enabled: bool = True,
    max_requests: int = 3,
    window: int = 10,
) -> object:
    cfg = type("RateLimitConfig", (), {})()
    cfg.enabled = enabled
    cfg.max_requests = max_requests
    cfg.window = window
    return cfg


# ── 测试 ──────────────────────────────────────────────────────────


class TestRateLimiterDisabled:
    """禁用模式。"""

    @pytest.mark.asyncio
    async def test_allows_all_when_disabled(self) -> None:
        limiter = RateLimiter(make_config(enabled=False))
        for _ in range(100):
            allowed, retry = await limiter.check("session-1")
            assert allowed is True
            assert retry == 0.0

    @pytest.mark.asyncio
    async def test_retry_after_is_zero_when_disabled(self) -> None:
        limiter = RateLimiter(make_config(enabled=False))
        allowed, retry = await limiter.check("any-session")
        assert allowed is True
        assert retry == 0.0


class TestRateLimiterBasic:
    """基本限流行为。"""

    @pytest.mark.asyncio
    async def test_allows_messages_under_limit(self) -> None:
        limiter = RateLimiter(make_config(max_requests=3, window=10))
        for i in range(3):
            allowed, _ = await limiter.check("session-1")
            assert allowed is True, f"message {i} should be allowed"

    @pytest.mark.asyncio
    async def test_blocks_when_exceeds_limit(self) -> None:
        limiter = RateLimiter(make_config(max_requests=3, window=10))
        for _ in range(3):
            await limiter.check("session-1")
        allowed, retry = await limiter.check("session-1")
        assert allowed is False
        assert retry > 0.0

    @pytest.mark.asyncio
    async def test_retry_after_positive(self) -> None:
        limiter = RateLimiter(make_config(max_requests=3, window=10))
        for _ in range(3):
            await limiter.check("session-1")
        allowed, retry = await limiter.check("session-1")
        assert allowed is False
        assert retry > 0.0
        assert retry <= 10.0

    @pytest.mark.asyncio
    async def test_allows_again_after_window_expires(self) -> None:
        mock_time = _make_mock_time(0.0)
        with patch("chat.pipeline.ratelimit.time.time", mock_time):
            limiter = RateLimiter(make_config(max_requests=3, window=10))
            for _ in range(3):
                await limiter.check("session-1")

            allowed, _ = await limiter.check("session-1")
            assert allowed is False

            mock_time.set(11.0)
            allowed, _ = await limiter.check("session-1")
            assert allowed is True


class TestRateLimiterSlidingWindow:
    """滑动窗口防 burst 行为。"""

    @pytest.mark.asyncio
    async def test_prevents_burst_at_window_boundary(self) -> None:
        mock_time = _make_mock_time(0.0)
        with patch("chat.pipeline.ratelimit.time.time", mock_time):
            limiter = RateLimiter(make_config(max_requests=3, window=10))
            for _ in range(3):
                await limiter.check("session-1")

            mock_time.set(9.99)
            allowed, _ = await limiter.check("session-1")
            assert allowed is False

            mock_time.set(10.01)
            allowed, _ = await limiter.check("session-1")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_sliding_window_not_fixed_window(self) -> None:
        mock_time = _make_mock_time(0.0)
        with patch("chat.pipeline.ratelimit.time.time", mock_time):
            limiter = RateLimiter(make_config(max_requests=3, window=10))
            for _ in range(3):
                await limiter.check("session-1")

            mock_time.set(6.0)
            allowed, _ = await limiter.check("session-1")
            assert allowed is False


class TestRateLimiterSessionIsolation:
    """会话隔离。"""

    @pytest.mark.asyncio
    async def test_isolates_between_sessions(self) -> None:
        limiter = RateLimiter(make_config(max_requests=3, window=10))
        for _ in range(3):
            await limiter.check("session-1")
        assert (await limiter.check("session-1"))[0] is False
        assert (await limiter.check("session-2"))[0] is True

    @pytest.mark.asyncio
    async def test_different_sessions_independent_limits(self) -> None:
        limiter = RateLimiter(make_config(max_requests=2, window=10))
        await limiter.check("user-A")
        await limiter.check("user-A")
        assert (await limiter.check("user-A"))[0] is False
        assert (await limiter.check("user-B"))[0] is True
        await limiter.check("user-B")
        assert (await limiter.check("user-B"))[0] is False


class TestRateLimiterReset:
    """重置操作。"""

    @pytest.mark.asyncio
    async def test_reset_clears_session_limit(self) -> None:
        limiter = RateLimiter(make_config(max_requests=3, window=10))
        for _ in range(3):
            await limiter.check("session-1")
        assert (await limiter.check("session-1"))[0] is False

        await limiter.reset("session-1")
        assert (await limiter.check("session-1"))[0] is True

    @pytest.mark.asyncio
    async def test_reset_nonexistent_session_no_error(self) -> None:
        limiter = RateLimiter(make_config())
        await limiter.reset("nonexistent")

    @pytest.mark.asyncio
    async def test_reset_all_clears_everything(self) -> None:
        limiter = RateLimiter(make_config(max_requests=3, window=10))
        for _ in range(3):
            await limiter.check("session-1")
        await limiter.check("session-2")

        await limiter.reset_all()
        assert (await limiter.check("session-1"))[0] is True
        assert (await limiter.check("session-2"))[0] is True


class TestRateLimiterBoundary:
    """边界条件。"""

    @pytest.mark.asyncio
    async def test_max_requests_one(self) -> None:
        limiter = RateLimiter(make_config(max_requests=1, window=10))
        assert (await limiter.check("s"))[0] is True
        assert (await limiter.check("s"))[0] is False

    @pytest.mark.asyncio
    async def test_max_requests_large(self) -> None:
        limiter = RateLimiter(make_config(max_requests=100, window=10))
        for i in range(100):
            assert (await limiter.check("s"))[0] is True, f"message {i} should be allowed"
        assert (await limiter.check("s"))[0] is False

    @pytest.mark.asyncio
    async def test_window_one_second(self) -> None:
        mock_time = _make_mock_time(0.0)
        with patch("chat.pipeline.ratelimit.time.time", mock_time):
            limiter = RateLimiter(make_config(max_requests=1, window=1))
            await limiter.check("s")
            assert (await limiter.check("s"))[0] is False

            mock_time.set(1.01)
            assert (await limiter.check("s"))[0] is True


class TestRateLimiterConcurrent:
    """并发安全性。"""

    @pytest.mark.asyncio
    async def test_concurrent_checks_never_exceed_limit(self) -> None:
        """并发请求不应突破频控上限。"""
        import asyncio

        limiter = RateLimiter(make_config(max_requests=10, window=10))

        async def send_many(session_id: str, count: int) -> int:
            allowed = 0
            for _ in range(count):
                ok, _ = await limiter.check(session_id)
                if ok:
                    allowed += 1
            return allowed

        # 两个并发任务同时发送到同一 session
        results = await asyncio.gather(
            send_many("shared", 10),
            send_many("shared", 10),
        )
        # 不应超过 10（上限）
        assert results[0] + results[1] <= 10


# ── 工具 ──────────────────────────────────────────────────────────


def _make_mock_time(start: float) -> object:
    state = {"now": start}

    def mock_time_fn() -> float:
        return state["now"]

    def set_time(t: float) -> None:
        state["now"] = t

    mock_time_fn.set = set_time  # type: ignore[attr-defined]
    return mock_time_fn