"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Sender — final message delivery layer
"""

__author__ = "Xiaji-yu"

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]


class MessageSender:
    """消息发送器。

    负责将格式化后的消息分片发送到目标。
    支持自定义发送回调，用于测试和适配不同 adapter。
    """

    def __init__(self, send_func: SendFunc | None = None) -> None:
        self._send = send_func

    async def send(self, text: str) -> None:
        """发送单条消息。"""
        if self._send is not None:
            await self._send(text)
        else:
            logger.warning("No send function configured, message dropped: %.50s...", text)

    async def send_batch(self, parts: list[str]) -> None:
        """批量发送分片消息。

        Args:
            parts: 消息分片列表。
        """
        for i, part in enumerate(parts):
            logger.debug("Sending part %d/%d (%d chars)", i + 1, len(parts), len(part))
            await self.send(part)
