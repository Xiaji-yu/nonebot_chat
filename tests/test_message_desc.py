"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : 消息描述工具（图片/引用等非文本段标注）测试
"""

from __future__ import annotations

from unittest.mock import MagicMock

from chat.message_desc import SEG_LABELS, describe


def _make_event(plain: str, segments: list[dict]) -> MagicMock:
    ev = MagicMock()
    ev.get_plaintext.return_value = plain
    ev.message = segments
    return ev


class TestDescribe:
    def test_plain_text_only(self) -> None:
        ev = _make_event("你好", [{"type": "text", "data": {"text": "你好"}}])
        assert describe(ev) == "你好"

    def test_image_appended(self) -> None:
        ev = _make_event("看看这张图", [{"type": "image", "data": {"url": "x"}}])
        assert describe(ev) == "看看这张图 [图片]"

    def test_image_only_message(self) -> None:
        """纯图片消息不应返回空串（此前 get_plaintext 为空 → 模型收到空输入）。"""
        ev = _make_event("", [{"type": "image", "data": {"url": "x"}}])
        assert describe(ev) == "[图片]"

    def test_duplicate_labels_deduped(self) -> None:
        ev = _make_event("", [
            {"type": "image", "data": {}},
            {"type": "image", "data": {}},
            {"type": "face", "data": {}},
        ])
        assert describe(ev) == "[图片] [表情]"

    def test_reply_and_image(self) -> None:
        ev = _make_event("", [
            {"type": "reply", "data": {"id": "123"}},
            {"type": "image", "data": {}},
        ])
        assert describe(ev) == "[引用消息] [图片]"

    def test_empty_event_returns_empty(self) -> None:
        ev = _make_event("", [])
        assert describe(ev) == ""

    def test_object_segments_supported(self) -> None:
        """兼容 OneBot segment 对象（有 .type 属性）。"""
        ev = MagicMock()
        ev.get_plaintext.return_value = ""
        seg = MagicMock()
        seg.type = "image"
        ev.message = [seg]
        assert describe(ev) == "[图片]"

    def test_all_labels_defined(self) -> None:
        assert SEG_LABELS["image"] == "[图片]"
        assert SEG_LABELS["reply"] == "[引用消息]"
