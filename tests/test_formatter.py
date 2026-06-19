"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 消息格式化器测试 — 超长分片 + Markdown 转换
"""

from __future__ import annotations

from chat.pipeline.formatter import MessageFormatter

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(max_length: int = 500, mode: str = "plain") -> object:
    cfg = type("FormatConfig", (), {})()
    cfg.max_length = max_length
    cfg.mode = mode
    return cfg


# ── Plain 模式 ────────────────────────────────────────────────────


class TestPlainFormat:
    def test_short_message_no_split(self) -> None:
        mf = MessageFormatter(make_config(max_length=500))
        parts = mf.format("hello")
        assert parts == ["hello"]

    def test_exact_max_length_no_split(self) -> None:
        mf = MessageFormatter(make_config(max_length=5))
        parts = mf.format("hello")
        assert parts == ["hello"]

    def test_long_message_split(self) -> None:
        mf = MessageFormatter(make_config(max_length=10))
        parts = mf.format("hello world this is long")
        assert len(parts) > 1
        for part in parts:
            assert len(part) <= 10

    def test_split_at_sentence_boundary(self) -> None:
        """拆分时优先在句号处断开。"""
        mf = MessageFormatter(make_config(max_length=5))
        parts = mf.format("你好。世界。")
        assert len(parts) >= 2

    def test_split_at_newline(self) -> None:
        mf = MessageFormatter(make_config(max_length=20))
        parts = mf.format("line one\nline two\nline three")
        assert len(parts) >= 2

    def test_empty_text(self) -> None:
        mf = MessageFormatter(make_config())
        parts = mf.format("")
        assert parts == [""]

    def test_all_parts_within_max_length(self) -> None:
        mf = MessageFormatter(make_config(max_length=50))
        long_text = "这是一段很长的文本。" * 20
        parts = mf.format(long_text)
        for part in parts:
            assert len(part) <= 50, f"part length {len(part)} > 50: {part[:30]}..."


# ── Markdown 模式 ─────────────────────────────────────────────────


class TestMarkdownFormat:
    def test_bold_conversion(self) -> None:
        mf = MessageFormatter(make_config(mode="markdown"))
        parts = mf.format("hello **world**")
        assert "[CQ:b," in parts[0]
        assert "world" in parts[0]

    def test_italic_conversion(self) -> None:
        mf = MessageFormatter(make_config(mode="markdown"))
        parts = mf.format("hello *world*")
        assert "[CQ:i," in parts[0]
        assert "world" in parts[0]

    def test_inline_code_conversion(self) -> None:
        mf = MessageFormatter(make_config(mode="markdown"))
        parts = mf.format("use `print()` function")
        assert "[CQ:code," in parts[0]

    def test_code_block_conversion(self) -> None:
        mf = MessageFormatter(make_config(mode="markdown"))
        parts = mf.format("```\nhello world\n```")
        assert "[CQ:quote," in parts[0]

    def test_no_markdown_in_plain_mode(self) -> None:
        mf = MessageFormatter(make_config(mode="plain"))
        parts = mf.format("hello **world**")
        assert "**world**" in parts[0]  # 原样保留


# ── CQ 转义 ────────────────────────────────────────────────────────


class TestCQEscape:
    def test_comma_escaped(self) -> None:
        mf = MessageFormatter(make_config(mode="markdown"))
        parts = mf.format("hello **a,b**")
        # 逗号应被转义
        assert "a\\,b" in parts[0] or "a,b" not in parts[0]

    def test_bracket_escaped(self) -> None:
        mf = MessageFormatter(make_config(mode="markdown"))
        parts = mf.format("hello **a]b**")
        # 右括号应被转义
        assert "a\\]b" in parts[0] or "\\]" in parts[0]


# ── 边界条件 ──────────────────────────────────────────────────────


class TestFormatBoundary:
    def test_max_length_zero(self) -> None:
        """max_length=0 时不拆分。"""
        mf = MessageFormatter(make_config(max_length=0))
        parts = mf.format("hello")
        assert parts == ["hello"]

    def test_exactly_at_boundary(self) -> None:
        mf = MessageFormatter(make_config(max_length=5))
        parts = mf.format("hello")
        assert len(parts) == 1
        assert parts == ["hello"]

    def test_one_char_over_boundary(self) -> None:
        mf = MessageFormatter(make_config(max_length=5))
        parts = mf.format("hello!")
        assert len(parts) == 2
        assert "".join(parts) == "hello!"