"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : Pydantic 配置模型验证测试
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from chat.config import (
    AccessConfig,
    MemoryConfig,
    PipelineConfig,
    SleepScheduleConfig,
    TemperatureConfig,
    TriggerConfig,
)

# ── TemperatureConfig ──────────────────────────────────────────────


class TestTemperatureConfig:
    def test_valid_config(self) -> None:
        tc = TemperatureConfig(default=0.7, proactive_min=0.5, proactive_max=1.0)
        assert tc.default == 0.7
        assert tc.proactive_min == 0.5
        assert tc.proactive_max == 1.0

    def test_proactive_min_gt_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            TemperatureConfig(proactive_min=1.0, proactive_max=0.5)

    def test_proactive_min_equals_max_is_valid(self) -> None:
        """min == max 是合法配置。"""
        tc = TemperatureConfig(proactive_min=0.7, proactive_max=0.7)
        assert tc.proactive_min == 0.7
        assert tc.proactive_max == 0.7

    def test_default_values(self) -> None:
        tc = TemperatureConfig()
        assert tc.default == 0.7
        assert tc.proactive_min == 0.5
        assert tc.proactive_max == 1.0

    def test_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            TemperatureConfig(default=3.0)  # > 2.0

        with pytest.raises(ValidationError):
            TemperatureConfig(default=-0.1)  # < 0.0


# ── MemoryConfig ───────────────────────────────────────────────────


class TestMemoryConfig:
    def test_valid_config(self) -> None:
        mc = MemoryConfig(max_history=50, distillation_threshold=40, core_memory_max=10)
        assert mc.max_history == 50
        assert mc.distillation_threshold == 40
        assert mc.core_memory_max == 10

    def test_threshold_gte_max_history_raises(self) -> None:
        with pytest.raises(ValidationError, match="distillation_threshold"):
            MemoryConfig(max_history=50, distillation_threshold=50)

    def test_threshold_gt_max_history_raises(self) -> None:
        with pytest.raises(ValidationError, match="distillation_threshold"):
            MemoryConfig(max_history=50, distillation_threshold=60)

    def test_core_memory_gt_max_history_raises(self) -> None:
        with pytest.raises(ValidationError, match="core_memory_max"):
            MemoryConfig(max_history=10, core_memory_max=20)

    def test_default_values(self) -> None:
        mc = MemoryConfig()
        assert mc.max_history == 50
        assert mc.distillation_threshold == 40
        assert mc.core_memory_max == 10

    def test_out_of_range_max_history_raises(self) -> None:
        with pytest.raises(ValidationError):
            MemoryConfig(max_history=3)  # < 5

        with pytest.raises(ValidationError):
            MemoryConfig(max_history=501)  # > 500


# ── AccessConfig ───────────────────────────────────────────────────


class TestAccessConfig:
    def test_valid_modes(self) -> None:
        for mode in ("whitelist", "blacklist", "none"):
            ac = AccessConfig(mode=mode)
            assert ac.mode == mode

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            AccessConfig(mode="invalid")

    def test_default_mode_none(self) -> None:
        ac = AccessConfig()
        assert ac.mode == "none"


# ── TriggerConfig ──────────────────────────────────────────────────


class TestTriggerConfig:
    def test_valid_modes(self) -> None:
        for mode in ("mention", "keyword", "spectator"):
            tc = TriggerConfig(mode=mode)
            assert tc.mode == mode

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValidationError):
            TriggerConfig(mode="invalid")

    def test_default_keywords(self) -> None:
        tc = TriggerConfig(mode="keyword")
        assert "小助手" in tc.keywords
        assert "bot" in tc.keywords


# ── SleepScheduleConfig ────────────────────────────────────────────


class TestSleepScheduleConfig:
    def test_valid_time(self) -> None:
        sc = SleepScheduleConfig(start="23:00", end="08:00")
        assert sc.start == "23:00"
        assert sc.end == "08:00"

    def test_invalid_time_format_raises(self) -> None:
        with pytest.raises(ValidationError):
            SleepScheduleConfig(start="25:00", end="08:00")

        with pytest.raises(ValidationError):
            SleepScheduleConfig(start="23:00", end="abc")  # 非时间格式

    def test_default_values(self) -> None:
        sc = SleepScheduleConfig()
        assert sc.start == "23:00"
        assert sc.end == "08:00"


# ── PipelineConfig ─────────────────────────────────────────────────


class TestPipelineConfig:
    def test_default_construction(self) -> None:
        pc = PipelineConfig()
        assert pc.sleep.enabled is False
        assert pc.dedup.enabled is True
        assert pc.access.mode == "none"
        assert pc.trigger.mode == "keyword"

    def test_nested_override(self) -> None:
        pc = PipelineConfig(
            sleep={"enabled": True, "mode": "manual"},
            trigger={"mode": "spectator"},
        )
        assert pc.sleep.enabled is True
        assert pc.sleep.mode == "manual"
        assert pc.trigger.mode == "spectator"