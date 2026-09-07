"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 黑白名单测试 — 独立开关、黑名单优先、fail-closed
"""

from __future__ import annotations

from chat.pipeline.access import AccessController

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(
    wl_enabled: bool = False,
    wl_users: list[str] | None = None,
    wl_groups: list[str] | None = None,
    bl_enabled: bool = False,
    bl_users: list[str] | None = None,
    bl_groups: list[str] | None = None,
) -> object:
    cfg = type("AccessConfig", (), {})()
    wl = type("AccessListConfig", (), {})()
    wl.enabled = wl_enabled
    wl.users = wl_users if wl_users is not None else []
    wl.groups = wl_groups if wl_groups is not None else []
    bl = type("AccessListConfig", (), {})()
    bl.enabled = bl_enabled
    bl.users = bl_users if bl_users is not None else []
    bl.groups = bl_groups if bl_groups is not None else []
    cfg.whitelist = wl
    cfg.blacklist = bl
    return cfg


# ── 全关闭（默认） ─────────────────────────────────────────────────


class TestAllDisabled:
    def test_allows_all_users(self) -> None:
        ac = AccessController(make_config())
        assert ac.check("123", None)[0] is True
        assert ac.check("456", "789")[0] is True

    def test_blocks_empty_user_id(self) -> None:
        """空 ID 一律拦截（安全设计）。"""
        ac = AccessController(make_config())
        allowed, reason = ac.check("", None)
        assert allowed is False
        assert reason == "invalid_user_id"


# ── 仅白名单 ───────────────────────────────────────────────────────


class TestWhitelistOnly:
    def test_allows_whitelisted_user(self) -> None:
        ac = AccessController(make_config(wl_enabled=True, wl_users=["123"]))
        assert ac.check("123", None)[0] is True

    def test_blocks_non_whitelisted_user(self) -> None:
        ac = AccessController(make_config(wl_enabled=True, wl_users=["123"]))
        allowed, reason = ac.check("456", None)
        assert allowed is False
        assert reason == "not_in_whitelist"

    def test_allows_whitelisted_group(self) -> None:
        ac = AccessController(make_config(wl_enabled=True, wl_groups=["789"]))
        assert ac.check("456", "789")[0] is True

    def test_user_in_whitelist_overrides_group(self) -> None:
        ac = AccessController(make_config(wl_enabled=True, wl_users=["123"]))
        assert ac.check("123", "000")[0] is True


# ── 仅黑名单 ───────────────────────────────────────────────────────


class TestBlacklistOnly:
    def test_blocks_blacklisted_user(self) -> None:
        ac = AccessController(make_config(bl_enabled=True, bl_users=["123"]))
        allowed, reason = ac.check("123", None)
        assert allowed is False
        assert reason == "blacklisted_user"

    def test_allows_non_blacklisted_user(self) -> None:
        ac = AccessController(make_config(bl_enabled=True, bl_users=["123"]))
        assert ac.check("456", None)[0] is True

    def test_blocks_blacklisted_group(self) -> None:
        ac = AccessController(make_config(bl_enabled=True, bl_groups=["789"]))
        allowed, reason = ac.check("456", "789")
        assert allowed is False
        assert reason == "blacklisted_group"


# ── 黑白名单同时启用（黑名单优先） ─────────────────────────────────


class TestBothEnabled:
    def test_blacklist_wins_over_whitelist(self) -> None:
        """同在白名单与黑名单 → 黑名单优先拦截。"""
        ac = AccessController(
            make_config(
                wl_enabled=True, wl_users=["123"],
                bl_enabled=True, bl_users=["123"],
            )
        )
        allowed, reason = ac.check("123", None)
        assert allowed is False
        assert reason == "blacklisted_user"

    def test_whitelisted_and_not_blacklisted_allowed(self) -> None:
        ac = AccessController(
            make_config(
                wl_enabled=True, wl_users=["123"],
                bl_enabled=True, bl_users=["456"],
            )
        )
        assert ac.check("123", None)[0] is True

    def test_not_whitelisted_blocked_even_if_not_blacklisted(self) -> None:
        ac = AccessController(
            make_config(
                wl_enabled=True, wl_users=["123"],
                bl_enabled=True, bl_users=["456"],
            )
        )
        allowed, reason = ac.check("789", None)
        assert allowed is False
        assert reason == "not_in_whitelist"

    def test_blacklisted_group_wins_over_whitelisted_group(self) -> None:
        """群同时在两名单 → 黑名单优先。"""
        ac = AccessController(
            make_config(
                wl_enabled=True, wl_groups=["789"],
                bl_enabled=True, bl_groups=["789"],
            )
        )
        allowed, reason = ac.check("456", "789")
        assert allowed is False
        assert reason == "blacklisted_group"


# ── 边界条件 ──────────────────────────────────────────────────────


class TestAccessBoundary:
    def test_empty_user_id_blocked_always(self) -> None:
        ac = AccessController(make_config(wl_enabled=True))
        allowed, reason = ac.check("", "123")
        assert allowed is False
        assert reason == "invalid_user_id"

    def test_private_chat_only_checks_user(self) -> None:
        """私聊（group_id=None）时只检查用户维度。"""
        ac = AccessController(make_config(bl_enabled=True, bl_groups=["789"]))
        # 群名单不适用于私聊
        assert ac.check("456", None)[0] is True

    def test_empty_whitelist_blocks_everyone(self) -> None:
        """白名单启用但名单为空 → 所有人被拦截（fail-closed）。"""
        ac = AccessController(make_config(wl_enabled=True))
        allowed, reason = ac.check("anyone", None)
        assert allowed is False
        assert reason == "not_in_whitelist"
