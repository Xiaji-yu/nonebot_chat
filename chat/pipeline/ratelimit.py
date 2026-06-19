"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Rate limiter — per-session rate limiting
"""

__author__ = "Xiaji-yu"

import logging
import time
from typing import Any

import asyncio

logger = logging.getLogger(__name__)


class RateLimiter:
    """会话级频控器（滑动窗口）。

    每个 session 在时间窗口内最多触发 N 次。
    """

    def __init__(self, rl_config: Any) -> None:
        self._window: float = float(rl_config.window)
        self._limit: int = int(rl_config.max_requests)
        self._enabled: bool = rl_config.enabled
        self._records: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, session_id: str) -> tuple[bool, float]:
        """检查是否允许通过。

        Args:
            session_id: 会话唯一标识。

        Returns:
            (allowed, retry_after) — 是否允许及建议等待秒数。
        """
        if not self._enabled:
            return True, 0.0

        now = time.time()
        async with self._lock:
            timestamps = self._records.get(session_id, [])
            # 清理窗口外的记录
            cutoff = now - self._window
            timestamps = [t for t in timestamps if t > cutoff]

            if len(timestamps) >= self._limit:
                # 取最早的未过期记录，计算 retry_after
                retry = timestamps[0] + self._window - now
                logger.debug(
                    "Rate limited: session=%s, count=%d/%d",
                    session_id, len(timestamps), self._limit,
                )
                return False, max(retry, 0.0)

            # 仅允许时记录时间戳
            timestamps.append(now)
            self._records[session_id] = timestamps

            return True, 0.0

    async def reset(self, session_id: str) -> None:
        """重置指定会话的频控计数。"""
        async with self._lock:
            self._records.pop(session_id, None)

    async def reset_all(self) -> None:
        """重置所有频控计数。"""
        async with self._lock:
            self._records.clear()
