"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 黑白名单测试 — 三种模式 + fail-closed 设计
"""

from __future__ import annotations

import pytest

from chat.pipeline.access import AccessController

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(
    mode: str = "none",
    users: list[str] | None = None,
    groups: list[str] | None = None,
) -> object:
    cfg = type("AccessConfig", (), {})()
    cfg.mode = mode
    cfg.users = users if users is not None else []
    cfg.groups = groups if groups is not None else []
    return cfg


# ── None 模式 ──────────────────────────────────────────────────────


class TestNoneMode:
    def test_allows_all_users(self) -> None:
        ac = AccessController(make_config("none"))
        assert ac.check("123", None)[0] is True
        assert ac.check("456", "789")[0] is True

    def test_allows_even_with_empty_id(self) -> None:
        """none 模式下空 ID 也会被拦截（安全设计）。"""
        ac = AccessController(make_config("none"))
        allowed, reason = ac.check("", None)
        assert allowed is False
        assert reason == "invalid_user_id"


# ── Whitelist 模式 ─────────────────────────────────────────────────


class TestWhitelistMode:
    def test_allows_whitelisted_user(self) -> None:
        ac = AccessController(make_config("whitelist", users=["123"]))
        assert ac.check("123", None)[0] is True

    def test_blocks_non_whitelisted_user(self) -> None:
        ac = AccessController(make_config("whitelist", users=["123"]))
        allowed, reason = ac.check("456", None)
        assert allowed is False
        assert reason == "not_in_whitelist"

    def test_allows_whitelisted_group(self) -> None:
        ac = AccessController(make_config("whitelist", groups=["789"]))
        assert ac.check("456", "789")[0] is True

    def test_blocks_non_whitelisted_group(self) -> None:
        ac = AccessController(make_config("whitelist", groups=["789"]))
        allowed, reason = ac.check("456", "000")
        assert allowed is False
        assert reason == "not_in_whitelist"

    def test_user_in_whitelist_overrides_group(self) -> None:
        """用户在白名单中：即使群不在白名单也放行。"""
        ac = AccessController(make_config("whitelist", users=["123"], groups=["000"]))
        assert ac.check("123", "999")[0] is True


# ── Blacklist 模式 ─────────────────────────────────────────────────


class TestBlacklistMode:
    def test_blocks_blacklisted_user(self) -> None:
        ac = AccessController(make_config("blacklist", users=["123"]))
        allowed, reason = ac.check("123", None)
        assert allowed is False
        assert reason == "blacklisted_user"

    def test_allows_non_blacklisted_user(self) -> None:
        ac = AccessController(make_config("blacklist", users=["123"]))
        assert ac.check("456", None)[0] is True

    def test_blocks_blacklisted_group(self) -> None:
        ac = AccessController(make_config("blacklist", groups=["789"]))
        allowed, reason = ac.check("456", "789")
        assert allowed is False
        assert reason == "blacklisted_group"

    def test_user_blacklist_overrides(self) -> None:
        """用户被拉黑：即使群不在黑名单也被拦截。"""
        ac = AccessController(make_config("blacklist", users=["123"]))
        assert ac.check("123", "000")[0] is False


# ── 边界条件 ──────────────────────────────────────────────────────


class TestAccessBoundary:
    def test_invalid_mode_raises_on_init(self) -> None:
        with pytest.raises(ValueError, match="Invalid access mode"):
            AccessController(make_config("invalid"))

    def test_empty_user_id_blocked(self) -> None:
        ac = AccessController(make_config("none"))
        allowed, reason = ac.check("", "123")
        assert allowed is False
        assert reason == "invalid_user_id"

    def test_private_chat_no_group_check(self) -> None:
        """私聊（group_id=None）时只检查用户。"""
        ac = AccessController(make_config("blacklist", users=["123"]))
        assert ac.check("123", None)[0] is False
        assert ac.check("456", None)[0] is True

    def test_empty_lists(self) -> None:
        """空名单时行为正常。"""
        ac = AccessController(make_config("whitelist", users=[], groups=[]))
        allowed, reason = ac.check("anyone", None)
        assert allowed is False
        assert reason == "not_in_whitelist"