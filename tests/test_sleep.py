"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 休眠模式控制器测试 — schedule / manual 模式
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from chat.pipeline.sleep import SleepController

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(
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


# ── 测试 ──────────────────────────────────────────────────────────


class TestSleepDisabled:
    @pytest.mark.asyncio
    async def test_disabled_never_sleeping(self) -> None:
        sc = SleepController(make_config(enabled=False))
        assert (await sc.is_sleeping()) is False


class TestSleepSchedule:
    @pytest.mark.asyncio
    async def test_sleeping_during_schedule(self) -> None:
        """在休眠时间段内应返回 True。"""
        sc = SleepController(make_config(start="23:00", end="08:00"))
        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(0, 30)  # 00:30
            assert (await sc.is_sleeping()) is True

    @pytest.mark.asyncio
    async def test_not_sleeping_outside_schedule(self) -> None:
        """不在休眠时间段内应返回 False。"""
        sc = SleepController(make_config(start="23:00", end="08:00"))
        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(12, 0)  # 12:00
            assert (await sc.is_sleeping()) is False

    @pytest.mark.asyncio
    async def test_sleeping_same_day_schedule(self) -> None:
        """同一天内的休眠时段（如 01:00-05:00）。"""
        sc = SleepController(make_config(start="01:00", end="05:00"))
        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(3, 0)
            assert (await sc.is_sleeping()) is True

            mock_dt.now.return_value.time.return_value = _make_time(6, 0)
            assert (await sc.is_sleeping()) is False

    @pytest.mark.asyncio
    async def test_equal_start_and_end_disables_schedule(self) -> None:
        """start == end 时调度应禁用（不进入休眠）。"""
        sc = SleepController(make_config(start="12:00", end="12:00"))
        with patch("chat.pipeline.sleep.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = _make_time(12, 0)
            assert (await sc.is_sleeping()) is False


class TestSleepManual:
    @pytest.mark.asyncio
    async def test_manual_toggle(self) -> None:
        sc = SleepController(make_config(mode="manual"))
        assert (await sc.is_sleeping()) is False

        new_state = await sc.toggle()
        assert new_state is True
        assert (await sc.is_sleeping()) is True

        new_state = await sc.toggle()
        assert new_state is False
        assert (await sc.is_sleeping()) is False

    @pytest.mark.asyncio
    async def test_force_wake(self) -> None:
        sc = SleepController(make_config(mode="manual"))
        await sc.toggle()  # 进入休眠
        assert (await sc.is_sleeping()) is True

        await sc.force_wake()
        assert (await sc.is_sleeping()) is False


class TestSleepOverride:
    @pytest.mark.asyncio
    async def test_override_allowed_by_default(self) -> None:
        sc = SleepController(make_config(override_by_mention=True))
        assert (await sc.is_override_allowed()) is True

    @pytest.mark.asyncio
    async def test_override_disabled(self) -> None:
        sc = SleepController(make_config(override_by_mention=False))
        assert (await sc.is_override_allowed()) is False


class TestSleepBoundary:
    @pytest.mark.asyncio
    async def test_unknown_mode_defaults_to_not_sleeping(self) -> None:
        sc = SleepController(make_config(mode="unknown"))
        assert (await sc.is_sleeping()) is False

    @pytest.mark.asyncio
    async def test_missing_attributes_safe(self) -> None:
        """配置缺失属性时不应崩溃。"""
        cfg = type("BadConfig", (), {})()
        cfg.enabled = True
        cfg.mode = "schedule"
        cfg.schedule = type("BadSchedule", (), {})()
        cfg.schedule.start = "invalid"
        cfg.schedule.end = "also_invalid"
        sc = SleepController(cfg)
        # 不应抛异常
        assert (await sc.is_sleeping()) is False


# ── 工具 ──────────────────────────────────────────────────────────


def _make_time(hour: int, minute: int) -> object:
    """创建模拟的 time 对象。"""
    from datetime import time as dt_time

    return dt_time(hour, minute)