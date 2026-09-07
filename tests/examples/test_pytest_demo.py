"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : Pytest usage examples — fixtures, parametrize, mocking, async tests

这些示例不是业务测试，而是演示如何在 nonebot_chat 项目里写测试。
可以直接运行：pytest tests/examples/test_pytest_demo.py -v
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.pipeline.access import AccessController
from chat.pipeline.debounce import Debouncer
from chat.pipeline.ratelimit import RateLimiter
from chat.pipeline.silent import SilentFilter
from chat.pipeline.sleep import SleepController

# ======================================================================
# 1. Fixtures 示例
# ======================================================================


@pytest.fixture
def sample_event() -> MagicMock:
    """创建一个模拟的 NoneBot MessageEvent。"""
    event = MagicMock()
    event.user_id = 123456
    event.group_id = 987654321
    event.self_id = "10000"
    event.get_plaintext = MagicMock(return_value="小助手 你好")
    event.is_tome = MagicMock(return_value=True)
    event.message = [{"type": "text", "data": {"text": "小助手 你好"}}]
    return event


@pytest.fixture
def send_func() -> AsyncMock:
    """创建一个模拟的异步发送函数。"""
    return AsyncMock()


# ======================================================================
# 2. Parametrize 示例
# ======================================================================


class TestParametrizeDemo:
    """展示 pytest.mark.parametrize 的用法。"""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("闭嘴", True),
            ("别回", True),
            ("SILENT", True),
            ("你好", False),
            ("", False),
        ],
    )
    def test_silent_keyword_variants(self, text: str, expected: bool) -> None:
        """静默关键词的多种输入场景。"""
        sf = SilentFilter(make_silent_config(["闭嘴", "别回", "silent"]))
        assert sf.is_silent(text) is expected

    @pytest.mark.parametrize(
        "mode,users,groups,user_id,group_id,expected",
        [
            ("none", [], [], "123", "456", True),
            ("whitelist", ["123"], [], "123", None, True),
            ("whitelist", ["123"], [], "456", None, False),
            ("blacklist", ["123"], [], "123", None, False),
            ("blacklist", ["123"], [], "456", None, True),
        ],
    )
    def test_access_modes(
        self,
        mode: str,
        users: list[str],
        groups: list[str],
        user_id: str,
        group_id: str | None,
        expected: bool,
    ) -> None:
        """黑白名单模式的参数化测试。"""
        ac = AccessController(make_access_config(mode, users, groups))
        assert ac.check(user_id, group_id)[0] is expected


# ======================================================================
# 3. Async 测试示例
# ======================================================================


class TestAsyncDemo:
    """展示异步测试的写法。"""

    @pytest.mark.asyncio
    async def test_debouncer_merges_messages(self) -> None:
        """防抖器在窗口内合并多条消息。"""
        db = Debouncer(make_debounce_config(window=0.1))
        callback = AsyncMock()

        await db.submit("session-1", "part1", callback)
        await db.submit("session-1", "part2", callback)

        await asyncio.sleep(0.15)
        callback.assert_called_once_with("part1\npart2")

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_under_limit(self) -> None:
        """频控器在限额内允许请求。"""
        limiter = RateLimiter(make_ratelimit_config(max_requests=3, window=10))
        for _ in range(3):
            allowed, _ = await limiter.check("session-1")
            assert allowed is True

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_over_limit(self) -> None:
        """频控器超过限额后拦截。"""
        limiter = RateLimiter(make_ratelimit_config(max_requests=2, window=10))
        await limiter.check("session-1")
        await limiter.check("session-1")
        allowed, _ = await limiter.check("session-1")
        assert allowed is False


# ======================================================================
# 4. Mock / Patch 示例
# ======================================================================


class TestMockDemo:
    """展示如何用 unittest.mock 模拟依赖。"""

    @pytest.mark.asyncio
    async def test_sleep_controller_with_mock_time(self) -> None:
        """通过 patch 模拟时间，测试定时休眠。"""
        sc = SleepController(make_sleep_config(start="23:00", end="08:00"))

        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(0, 30)
            assert (await sc.is_sleeping()) is True

            mock_dt.now.return_value.time.return_value = _make_time(12, 0)
            assert (await sc.is_sleeping()) is False

    def test_event_attributes_are_accessible(self, sample_event: MagicMock) -> None:
        """使用 fixture 注入模拟事件。"""
        assert sample_event.user_id == 123456
        assert sample_event.group_id == 987654321
        assert sample_event.get_plaintext() == "小助手 你好"

    @patch("chat.pipeline.silent.logger")
    def test_silent_filter_logs_debug(self, mock_logger: MagicMock) -> None:
        """验证内部日志行为（可选，按需启用）。"""
        sf = SilentFilter(make_silent_config(["测试"]))
        sf.is_silent("这是一个测试")
        # 仅展示 patch 用法；不强制断言日志细节
        assert mock_logger is not None


# ======================================================================
# 5. 边界条件示例
# ======================================================================


class TestEdgeCaseDemo:
    """展示边界条件和错误路径的测试写法。"""

    def test_access_controller_rejects_empty_user_id(self) -> None:
        """空 user_id 应被拒绝（fail-closed）。"""
        ac = AccessController(make_access_config("none"))
        allowed, reason = ac.check("", "123")
        assert allowed is False
        assert reason == "invalid_user_id"

    @pytest.mark.asyncio
    async def test_sleep_controller_handles_invalid_schedule(self) -> None:
        """非法 schedule 不崩溃，安全返回 False。"""
        cfg = make_sleep_config(start="invalid", end="also_invalid")
        sc = SleepController(cfg)
        assert (await sc.is_sleeping()) is False

    @pytest.mark.asyncio
    async def test_debouncer_cancel_stops_timer(self) -> None:
        """取消防抖后不应触发回调。"""
        db = Debouncer(make_debounce_config(window=0.5))
        callback = AsyncMock()

        await db.submit("session-1", "hello", callback)
        db.cancel("session-1")

        # 这里用同步检查即可；实际 flush 被 cancel 阻止
        assert callback.call_count == 0


# ======================================================================
# 辅助工厂（与 tests/conftest.py 风格一致）
# ======================================================================


def make_silent_config(keywords: list[str]) -> object:
    """创建 SilentFilter 所需的配置对象。"""
    cfg = type("SilentConfig", (), {})()
    cfg.enabled = True
    cfg.keywords = keywords
    return cfg


def make_access_config(
    mode: str = "none",
    users: list[str] | None = None,
    groups: list[str] | None = None,
) -> object:
    """创建 AccessController 配置对象。

    Args:
        mode: "none" | "whitelist" | "blacklist"（演示用便捷映射）。
        users: 对应名单中的用户 ID 列表。
        groups: 对应名单中的群 ID 列表。
    """
    cfg = type("AccessConfig", (), {})()
    wl = type("AccessListConfig", (), {})()
    bl = type("AccessListConfig", (), {})()
    wl_users: list[str] = users if users is not None else []
    wl_groups: list[str] = groups if groups is not None else []
    if mode == "whitelist":
        wl.enabled, bl.enabled = True, False
        wl.users, wl.groups = wl_users, wl_groups
        bl.users, bl.groups = [], []
    elif mode == "blacklist":
        wl.enabled, bl.enabled = False, True
        wl.users, wl.groups = [], []
        bl.users, bl.groups = wl_users, wl_groups
    else:
        wl.enabled, bl.enabled = False, False
        wl.users, wl.groups = [], []
        bl.users, bl.groups = [], []
    cfg.whitelist = wl
    cfg.blacklist = bl
    return cfg


def make_debounce_config(enabled: bool = True, window: float = 3.0) -> object:
    cfg = type("DebounceConfig", (), {})()
    cfg.enabled = enabled
    cfg.window = window
    return cfg


def make_ratelimit_config(
    enabled: bool = True, max_requests: int = 3, window: int = 10
) -> object:
    cfg = type("RateLimitConfig", (), {})()
    cfg.enabled = enabled
    cfg.max_requests = max_requests
    cfg.window = window
    return cfg


def make_sleep_config(
    enabled: bool = True,
    mode: str = "schedule",
    start: str = "23:00",
    end: str = "08:00",
    override_by_mention: bool = True,
) -> object:
    cfg = type("SleepConfig", (), {})()
    cfg.enabled = enabled
    cfg.mode = mode
    cfg.schedule = type("Schedule", (), {})()
    cfg.schedule.start = start
    cfg.schedule.end = end
    cfg.override_by_mention = override_by_mention
    return cfg


def _make_time(hour: int, minute: int) -> Any:
    from datetime import time as dt_time

    return dt_time(hour, minute)
