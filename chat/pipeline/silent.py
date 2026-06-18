"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Silent keyword filter — drop messages containing silent triggers
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SilentFilter:
    """静默关键词过滤器。

    消息内容命中任意静默关键词时，直接跳过回复。
    """

    def __init__(self, silent_config: Any) -> None:
        self._keywords: list[str] = []
        if silent_config.enabled:
            self._keywords = [kw.lower() for kw in silent_config.keywords]

    def is_silent(self, text: str) -> bool:
        """检查消息是否命中静默关键词。

        Args:
            text: 消息纯文本内容。

        Returns:
            True 表示应静默处理（不回复）。
        """
        if not self._keywords:
            return False
        lower = text.lower()
        return any(kw in lower for kw in self._keywords)
