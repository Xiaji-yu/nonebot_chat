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
    ChatConfig,
    LLMConfig,
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
    def test_independent_whitelist_and_blacklist(self) -> None:
        """白名单与黑名单应相互独立、可同时启用。"""
        ac = AccessConfig(
            whitelist={"enabled": True, "users": ["123"], "groups": []},
            blacklist={"enabled": True, "users": ["456"], "groups": []},
        )
        assert ac.whitelist.enabled is True
        assert ac.whitelist.users == ["123"]
        assert ac.blacklist.enabled is True
        assert ac.blacklist.users == ["456"]

    def test_defaults_disabled(self) -> None:
        """默认两个名单都未启用（不过滤）。"""
        ac = AccessConfig()
        assert ac.whitelist.enabled is False
        assert ac.blacklist.enabled is False
        assert ac.whitelist.users == []
        assert ac.blacklist.groups == []

    def test_numeric_ids_coerced_to_str(self) -> None:
        """数字 ID（QQ/群号不带引号）应自动转字符串。"""
        ac = AccessConfig(
            whitelist={"enabled": True, "users": [123], "groups": [1051425116, 757335552]},
            blacklist={"users": [456789]},
        )
        assert ac.whitelist.users == ["123"]
        assert ac.whitelist.groups == ["1051425116", "757335552"]
        assert ac.blacklist.users == ["456789"]

    def test_mixed_id_types_coerced_to_str(self) -> None:
        """混合 str/int 列表应统一为 str。"""
        ac = AccessConfig(
            whitelist={"enabled": True, "users": ["123", 456]},
        )
        assert ac.whitelist.users == ["123", "456"]


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
        assert pc.access.whitelist.enabled is False
        assert pc.access.blacklist.enabled is False
        assert pc.trigger.mode == "keyword"

    def test_nested_override(self) -> None:
        pc = PipelineConfig(
            sleep={"enabled": True, "mode": "manual"},
            trigger={"mode": "spectator"},
        )
        assert pc.sleep.enabled is True
        assert pc.sleep.mode == "manual"
        assert pc.trigger.mode == "spectator"


# ── LLMConfig fallbacks ─────────────────────────────────────────────


class TestLLMConfigFallbacks:
    def test_fallbacks_empty_by_default(self) -> None:
        cfg = LLMConfig()
        assert cfg.fallbacks == []

    def test_fallbacks_parse_list(self) -> None:
        cfg = LLMConfig(
            fallbacks=[
                {"base_url": "http://a.com/v1", "model": "m-a"},
                {"base_url": "http://b.com/v1", "model": "m-b", "api_key": "k"},
            ]
        )
        assert len(cfg.fallbacks) == 2
        assert cfg.fallbacks[0].base_url == "http://a.com/v1"
        assert cfg.fallbacks[0].model == "m-a"
        assert cfg.fallbacks[0].api_key == ""
        assert cfg.fallbacks[1].api_key == "k"

    def test_fallback_requires_base_url_and_model(self) -> None:
        with pytest.raises(ValidationError):
            LLMConfig(fallbacks=[{"model": "m"}])  # 缺 base_url
        with pytest.raises(ValidationError):
            LLMConfig(fallbacks=[{"base_url": "http://a.com/v1"}])  # 缺 model

# ── ChatConfig validation_alias ─────────────────────────────────────


class TestChatConfigAlias:
    """ChatConfig 的 validation_alias 应匹配 CHAT_ 前缀环境变量。"""

    def test_alias_matches_chat_prefix(self) -> None:
        cfg = ChatConfig(
            chat_config_path="/tmp/x.yaml",
            chat_chat_enabled=False,
            chat_only_superusers=False,
        )
        assert cfg.config_path == "/tmp/x.yaml"
        assert cfg.chat_enabled is False
        assert cfg.only_superusers is False

    def test_field_name_still_accepted(self) -> None:
        """populate_by_name 允许直接按字段名构造。"""
        cfg = ChatConfig(config_path="/tmp/y.yaml")
        assert cfg.config_path == "/tmp/y.yaml"

    def test_defaults(self) -> None:
        cfg = ChatConfig()
        assert cfg.chat_enabled is True
        assert cfg.only_superusers is True
