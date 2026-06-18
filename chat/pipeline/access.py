"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Access control — whitelist / blacklist filtering
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AccessController:
    """黑白名单控制器。

    mode:
      - "none": 不过滤，所有用户/群组放行
      - "whitelist": 仅名单内的用户/群组可访问
      - "blacklist": 名单内的用户/群组被拦截
    """

    def __init__(self, access_config: Any) -> None:
        self._mode = access_config.mode
        self._users: set[str] = set(access_config.users)
        self._groups: set[str] = set(access_config.groups)

    def check(self, user_id: str, group_id: str | None = None) -> tuple[bool, str]:
        """检查访问权限。

        Args:
            user_id: 用户 ID（字符串）。
            group_id: 群 ID（字符串），私聊时为 None。

        Returns:
            (allowed, reason) — 是否放行及原因。
        """
        if self._mode == "none":
            return True, ""

        if self._mode == "whitelist":
            if user_id in self._users:
                return True, ""
            if group_id and group_id in self._groups:
                return True, ""
            return False, "not_in_whitelist"

        if self._mode == "blacklist":
            if user_id in self._users:
                return False, "blacklisted_user"
            if group_id and group_id in self._groups:
                return False, "blacklisted_group"
            return True, ""

        # 未知模式，保守放行
        logger.warning("Unknown access mode: %s", self._mode)
        return True, ""
