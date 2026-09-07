"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : 日志脱敏工具测试
"""

from __future__ import annotations

from chat.mask import mask_id, mask_session, mask_user


class TestMaskSession:
    def test_group_session_masked(self) -> None:
        assert mask_session("g123456789_u987654321") == "g1***789_u9***321"

    def test_private_session_masked(self) -> None:
        assert mask_session("u987654321") == "u9***321"

    def test_short_ids_untouched(self) -> None:
        assert mask_session("g12_u34") == "g12_u34"

    def test_plain_text_unchanged(self) -> None:
        assert mask_session("hello world") == "hello world"


class TestMaskUser:
    def test_long_id_masked(self) -> None:
        assert mask_user("2224513919") == "2***919"

    def test_short_id_untouched(self) -> None:
        assert mask_user("123") == "123"


class TestMaskId:
    def test_raw_qq_masked_in_text(self) -> None:
        assert mask_id("用户 3629537600 异常") == "用户 3***600 异常"

    def test_short_number_untouched(self) -> None:
        assert mask_id("count=42") == "count=42"
