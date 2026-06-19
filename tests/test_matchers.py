"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 会话 ID 提取测试
"""

from __future__ import annotations

from unittest.mock import MagicMock

from chat.matchers import get_session_id


def make_event(
    user_id: int | None = 12345,
    group_id: int | None = 88888,
    session_id: str | None = None,
    self_id: str = "10000",
    message_id: str = "msg-001",
) -> MagicMock:
    event = MagicMock()
    event.user_id = user_id
    event.group_id = group_id
    event.session_id = None  # pyright: ignore[reportAttributeAccessIssue]
    if session_id is not None:
        event.session_id = session_id  # pyright: ignore[reportAttributeAccessIssue]
    event.self_id = self_id
    event.message_id = message_id
    return event


class TestGetSessionId:
    def test_group_chat_session_id(self) -> None:
        event = make_event(user_id=123, group_id=456)
        sid = get_session_id(event)
        assert sid == "g456_u123"

    def test_private_chat_session_id(self) -> None:
        event = make_event(user_id=123, group_id=None)
        sid = get_session_id(event)
        assert sid == "u123"

    def test_fallback_to_session_id(self) -> None:
        event = make_event(user_id=None, group_id=None, session_id="fallback-sid")
        sid = get_session_id(event)
        assert sid == "fallback-sid"

    def test_fallback_to_hash(self) -> None:
        """无 user_id / group_id / session_id 时回退到哈希。"""
        event = make_event(user_id=None, group_id=None, session_id=None)
        sid = get_session_id(event)
        assert sid.startswith("evt_")
        assert len(sid) == 16  # "evt_" + 12 hex chars

    def test_same_event_same_hash(self) -> None:
        """相同事件属性应产生相同哈希。"""
        e1 = make_event(
            user_id=None, group_id=None, session_id=None,
            self_id="10000", message_id="msg-1",
        )
        e2 = make_event(
            user_id=None, group_id=None, session_id=None,
            self_id="10000", message_id="msg-1",
        )
        assert get_session_id(e1) == get_session_id(e2)

    def test_different_event_different_hash(self) -> None:
        """不同事件属性应产生不同哈希。"""
        e1 = make_event(user_id=None, group_id=None, session_id=None, message_id="msg-1")
        e2 = make_event(user_id=None, group_id=None, session_id=None, message_id="msg-2")
        assert get_session_id(e1) != get_session_id(e2)