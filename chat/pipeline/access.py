"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Access control — whitelist / blacklist filtering
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

logger = logging.getLogger(__name__)

VALID_MODES = frozenset({"whitelist", "blacklist", "none"})


class AccessController:
    """黑白名单控制器。

    mode:
      - "none": 不过滤，所有用户/群组放行
      - "whitelist": 仅名单内的用户/群组可访问
      - "blacklist": 名单内的用户/群组被拦截

    安全默认：未知模式或配置错误时 deny-all（fail-closed）。
    """

    def __init__(self, access_config: Any) -> None:
        mode = getattr(access_config, "mode", None)
        if mode not in VALID_MODES:
            raise ValueError(
                f"Invalid access mode: {mode!r}. "
                f"Must be one of: {', '.join(sorted(VALID_MODES))}"
            )
        self._mode = mode
        self._users: set[str] = set(getattr(access_config, "users", []))
        self._groups: set[str] = set(getattr(access_config, "groups", []))

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

        if self._mode == "none":
            return True, ""

        if self._mode == "whitelist":
            if user_id in self._users:
                return True, ""
            if group_id is not None and group_id in self._groups:
                return True, ""
            return False, "not_in_whitelist"

        if self._mode == "blacklist":
            if user_id in self._users:
                return False, "blacklisted_user"
            if group_id is not None and group_id in self._groups:
                return False, "blacklisted_group"
            return True, ""

        # 防御性：不应到达此处（__init__ 已校验）
        logger.error("Unknown access mode: %s", self._mode)
        return False, "unknown_mode"
