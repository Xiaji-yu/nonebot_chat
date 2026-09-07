"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Reply debouncer — merge rapid messages into single reply
"""

__author__ = "Xiaji-yu"

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from ..log import logger

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
        # session_id -> (task, first_msg_time, any_triggered, messages)
        self._pending: dict[str, tuple[asyncio.Task | None, float, bool, list[str]]] = {}
        self._lock = asyncio.Lock()

    def is_enabled(self) -> bool:
        """是否启用防抖。"""
        return self._enabled

    async def submit(
        self,
        session_id: str,
        message: str,
        reply_callback: SendFunc,
        triggered: bool = True,
    ) -> None:
        """提交一条消息到防抖窗口。

        调用方保证 enabled=True，否则应直接调用 reply_callback。

        Args:
            session_id: 会话唯一标识。
            message: 用户消息内容。
            reply_callback: 最终回复的回调函数（仅在批内任一消息触发时调用）。
            triggered: 本条消息是否满足触发条件（@/关键词等）。
        """

        # 获取或创建会话条目（加锁防止并发竞态）
        async with self._lock:
            now = time.monotonic()
            if session_id not in self._pending:
                self._pending[session_id] = (None, now, False, [])

            task, first_ts, any_triggered, messages = self._pending[session_id]
            messages.append(message)
            any_triggered = any_triggered or triggered

            # 取消已有计时器
            if task is not None:
                task.cancel()

            # 设置新计时器
            new_task = asyncio.create_task(self._wait_and_flush(session_id, reply_callback))
            self._pending[session_id] = (new_task, first_ts, any_triggered, messages)

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
        _, first_ts, any_triggered, messages = entry
        if not messages:
            return

        # 批内没有任何触发消息 → 整批丢弃（群聊触发语义）
        if not any_triggered:
            logger.debug(
                f"[debounce] 批内无触发消息，丢弃 {len(messages)} 条 "
                f"(session={session_id})"
            )
            return

        merged = "\n".join(messages)
        wait = time.monotonic() - first_ts
        if len(messages) > 1:
            logger.info(
                f"[debounce] 合并 {len(messages)} 条消息，"
                f"自首条起等待 {wait:.1f}s 后统一处理"
            )
        try:
            await reply_callback(merged)
        except Exception:
            logger.exception(f"Debounced reply failed for session {session_id}")

    def cancel(self, session_id: str) -> None:
        """取消指定会话的防抖计时。"""
        entry = self._pending.pop(session_id, None)
        if entry is not None:
            task, _, _, _ = entry
            if task is not None:
                task.cancel()
