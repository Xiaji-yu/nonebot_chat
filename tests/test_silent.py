"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 静默关键词过滤器测试
"""

from __future__ import annotations

from chat.pipeline.silent import SilentFilter

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(enabled: bool = True, keywords: list[str] | None = None) -> object:
    cfg = type("SilentConfig", (), {})()
    cfg.enabled = enabled
    cfg.keywords = keywords if keywords is not None else ["闭嘴", "别回", "silent"]
    return cfg


# ── 测试 ──────────────────────────────────────────────────────────


class TestSilentFilter:
    def test_matches_keyword(self) -> None:
        sf = SilentFilter(make_config(keywords=["闭嘴"]))
        assert sf.is_silent("给我闭嘴") is True

    def test_no_match(self) -> None:
        sf = SilentFilter(make_config(keywords=["闭嘴"]))
        assert sf.is_silent("你好世界") is False

    def test_case_insensitive(self) -> None:
        sf = SilentFilter(make_config(keywords=["Silent"]))
        assert sf.is_silent("SILENT mode") is True

    def test_substring_match(self) -> None:
        sf = SilentFilter(make_config(keywords=["闭嘴"]))
        assert sf.is_silent("请闭嘴吧") is True

    def test_multiple_keywords(self) -> None:
        sf = SilentFilter(make_config(keywords=["闭嘴", "别回", "silent"]))
        assert sf.is_silent("别回了") is True
        assert sf.is_silent("please be silent") is True

    def test_disabled_filter_never_matches(self) -> None:
        sf = SilentFilter(make_config(enabled=False, keywords=["闭嘴"]))
        assert sf.is_silent("闭嘴") is False

    def test_empty_keywords_never_matches(self) -> None:
        sf = SilentFilter(make_config(keywords=[]))
        assert sf.is_silent("闭嘴") is False

    def test_empty_text_never_matches(self) -> None:
        sf = SilentFilter(make_config(keywords=["闭嘴"]))
        assert sf.is_silent("") is False

    def test_partial_match_only(self) -> None:
        """子串匹配：'闭' 和 '嘴' 分开不应匹配。"""
        sf = SilentFilter(make_config(keywords=["闭嘴"]))
        assert sf.is_silent("闭") is False
        assert sf.is_silent("嘴") is False