"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Reply debouncer — merge rapid messages into single reply
"""

__author__ = "Xiaji-yu"

import asyncio
import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]


class Debouncer:
    """回复防抖合并器。

    在防抖窗口内收集多条用户消息，合并后只回复一次。
    窗口结束后触发实际回复。
    """

    def __init__(self, debounce_config: Any) -> None:
        self._enabled = debounce_config.enabled
        self._window: float = float(debounce_config.window)
        # session_id -> (task, messages)
        self._pending: dict[str, tuple[asyncio.Task | None, list[str]]] = {}
        self._lock = asyncio.Lock()

    def is_enabled(self) -> bool:
        """是否启用防抖。"""
        return self._enabled

    async def submit(
        self,
        session_id: str,
        message: str,
        reply_callback: SendFunc,
    ) -> None:
        """提交一条消息到防抖窗口。

        Args:
            session_id: 会话唯一标识。
            message: 用户消息内容。
            reply_callback: 最终回复的回调函数。
        """
        if not self._enabled:
            await reply_callback(message)
            return

        # 获取或创建会话条目（加锁防止并发竞态）
        async with self._lock:
            if session_id not in self._pending:
                self._pending[session_id] = (None, [])

            task, messages = self._pending[session_id]
            messages.append(message)

            # 取消已有计时器
            if task is not None:
                task.cancel()

            # 设置新计时器
            new_task = asyncio.create_task(self._wait_and_flush(session_id, reply_callback))
            self._pending[session_id] = (new_task, messages)

    async def _wait_and_flush(self, session_id: str, reply_callback: SendFunc) -> None:
        """等待防抖窗口后发送合并回复。"""
        try:
            await asyncio.sleep(self._window)
        except asyncio.CancelledError:
            return

        # 身份校验：只有当前活跃 task 才能弹出条目
        # 防止被取消的旧 task 弹出新 task 的条目
        entry = self._pending.get(session_id)
        if entry is None or entry[0] is not asyncio.current_task():
            return
        self._pending.pop(session_id, None)
        _, messages = entry
        if not messages:
            return

        merged = "\n".join(messages)
        try:
            await reply_callback(merged)
        except Exception:
            logger.exception("Debounced reply failed for session %s", session_id)

    def cancel(self, session_id: str) -> None:
        """取消指定会话的防抖计时。"""
        entry = self._pending.pop(session_id, None)
        if entry is not None:
            task, _ = entry
            if task is not None:
                task.cancel()
