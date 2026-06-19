"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 触发检测测试 — mention / keyword / spectator 模式
"""

from __future__ import annotations

import pytest

from chat.pipeline.trigger import TriggerDetector

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(mode: str, keywords: list[str] | None = None) -> object:
    cfg = type("TriggerConfig", (), {})()
    cfg.mode = mode
    cfg.keywords = keywords if keywords is not None else ["小助手", "bot"]
    return cfg


def make_event(text: str, *, is_tome: bool = False, self_id: str = "10000") -> object:
    """创建模拟事件。"""
    event = type("MockEvent", (), {})()
    event.get_plaintext = lambda: text
    event.is_tome = lambda: is_tome
    event.self_id = self_id
    event.message = [{"type": "text", "data": {"text": text}}]
    return event


# ── Keyword 模式 ──────────────────────────────────────────────────


class TestKeywordMode:
    def test_keyword_matches(self) -> None:
        detector = TriggerDetector(make_config("keyword", ["小助手", "bot"]))
        triggered, trigger_type = detector.detect(make_event("小助手 你好"))
        assert triggered is True
        assert trigger_type == "keyword:小助手"

    def test_keyword_case_insensitive(self) -> None:
        detector = TriggerDetector(make_config("keyword", ["Bot"]))
        triggered, trigger_type = detector.detect(make_event("bot hello"))
        assert triggered is True
        assert trigger_type == "keyword:bot"

    def test_keyword_no_match(self) -> None:
        detector = TriggerDetector(make_config("keyword", ["小助手"]))
        triggered, trigger_type = detector.detect(make_event("你好世界"))
        assert triggered is False

    def test_keyword_substring_match(self) -> None:
        """唤醒词为子串匹配。"""
        detector = TriggerDetector(make_config("keyword", ["bot"]))
        triggered, _ = detector.detect(make_event("robot assistant"))
        assert triggered is True

    def test_keyword_multiple_keywords(self) -> None:
        detector = TriggerDetector(make_config("keyword", ["foo", "hello", "bar"]))
        assert detector.detect(make_event("hello there"))[0] is True
        assert detector.detect(make_event("goodbye"))[0] is False

    def test_keyword_empty_keywords_raises(self) -> None:
        with pytest.raises(ValueError, match="keyword"):
            TriggerDetector(make_config("keyword", []))


# ── Mention 模式 ──────────────────────────────────────────────────


class TestMentionMode:
    def test_mention_detected_via_is_tome(self) -> None:
        detector = TriggerDetector(make_config("mention"))
        event = make_event("hello", is_tome=True)
        triggered, trigger_type = detector.detect(event)
        assert triggered is True
        assert trigger_type == "mention"

    def test_mention_not_detected_without_mention(self) -> None:
        detector = TriggerDetector(make_config("mention"))
        event = make_event("hello", is_tome=False)
        triggered, _ = detector.detect(event)
        assert triggered is False

    def test_mention_detected_via_cq_at_segment(self) -> None:
        """is_tome 不可用（抛出异常）时回退到 CQ 段解析。"""
        from unittest.mock import MagicMock

        detector = TriggerDetector(make_config("mention"))

        def _raise(*args, **kwargs):
            raise NotImplementedError

        # 创建有 .type 和 .data 属性的模拟消息段
        at_seg = MagicMock()
        at_seg.type = "at"
        at_seg.data = {"qq": "10000"}

        event = MagicMock()
        event.get_plaintext = MagicMock(return_value="hello")
        event.self_id = "10000"
        event.is_tome = _raise
        event.message = [at_seg]

        triggered, _ = detector.detect(event)
        assert triggered is True

    def test_mention_other_user_not_detected(self) -> None:
        detector = TriggerDetector(make_config("mention"))
        event = type("MockEvent", (), {})()
        event.get_plaintext = lambda: "hello"
        event.self_id = "10000"
        event.is_tome = lambda: False
        event.message = [{"type": "at", "data": {"qq": "99999"}}]
        triggered, _ = detector.detect(event)
        assert triggered is False


# ── Spectator 模式 ────────────────────────────────────────────────


class TestSpectatorMode:
    def test_spectator_always_triggers(self) -> None:
        detector = TriggerDetector(make_config("spectator"))
        assert detector.detect(make_event("任何消息"))[0] is True
        assert detector.detect(make_event(""))[0] is True
        assert detector.detect(make_event("random"))[0] is True


# ── 边界条件 ──────────────────────────────────────────────────────


class TestTriggerBoundary:
    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid trigger mode"):
            TriggerDetector(make_config("invalid"))

    def test_empty_text_no_match_keyword(self) -> None:
        detector = TriggerDetector(make_config("keyword", ["bot"]))
        triggered, _ = detector.detect(make_event(""))
        assert triggered is False

    def test_mode_property(self) -> None:
        detector = TriggerDetector(make_config("spectator"))
        assert detector.mode == "spectator"