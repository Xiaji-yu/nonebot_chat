"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Access control — independent whitelist / blacklist filtering
"""

__author__ = "Xiaji-yu"

from typing import Any


class AccessController:
    """访问控制器 — 白名单与黑名单相互独立，可同时启用。

    判定规则（黑名单优先）：
      1. 黑名单命中（用户或群在 blacklist 中）→ 直接拦截；
      2. 白名单启用 → 用户或群必须命中 whitelist 才放行；
      3. 白名单未启用 → 放行。

    安全默认：非法/缺失配置时 deny-all（fail-closed）。
    """

    def __init__(self, access_config: Any) -> None:
        wl = getattr(access_config, "whitelist", None)
        bl = getattr(access_config, "blacklist", None)
        self._wl_enabled = bool(getattr(wl, "enabled", False))
        self._bl_enabled = bool(getattr(bl, "enabled", False))
        self._wl_users: set[str] = set(getattr(wl, "users", []) or [])
        self._wl_groups: set[str] = set(getattr(wl, "groups", []) or [])
        self._bl_users: set[str] = set(getattr(bl, "users", []) or [])
        self._bl_groups: set[str] = set(getattr(bl, "groups", []) or [])

    def check(self, user_id: str, group_id: str | None = None) -> tuple[bool, str]:
        """检查访问权限。

        Args:
            user_id: 用户 ID（字符串，不可为空）。
            group_id: 群 ID（字符串），私聊时为 None。

        Returns:
            (allowed, reason) — 是否放行及原因。
        """
        if not user_id:
            return False, "invalid_user_id"

        # 黑名单优先：命中即拦截
        if self._bl_enabled:
            if user_id in self._bl_users:
                return False, "blacklisted_user"
            if group_id is not None and group_id in self._bl_groups:
                return False, "blacklisted_group"

        # 白名单启用：必须命中名单
        if self._wl_enabled:
            if user_id in self._wl_users:
                return True, ""
            if group_id is not None and group_id in self._wl_groups:
                return True, ""
            return False, "not_in_whitelist"

        # 白名单未启用且未被拉黑 → 放行
        return True, ""

