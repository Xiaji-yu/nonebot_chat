"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Memory store — per-session conversation history with thread safety
"""

__author__ = "Xiaji-yu"

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """单条消息记录。"""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """转换为 OpenAI Chat 格式的字典。"""
        return {"role": self.role, "content": self.content}


@dataclass
class SessionMemory:
    """单会话记忆容器。"""

    session_id: str
    messages: list[Message] = field(default_factory=list)
    core_memory: list[Message] = field(default_factory=list)
    """蒸馏后的核心记忆（摘要）。"""

    last_proactive_time: float = 0.0
    """上次主动回复的时间戳。"""

    _distilling: bool = field(default=False, compare=False)
    """蒸馏锁：防止并发双重蒸馏。"""

    def add_message(self, role: str, content: str) -> None:
        """添加一条消息。"""
        self.messages.append(Message(role=role, content=content))

    def get_history(self, max_count: int) -> list[dict[str, Any]]:
        """获取对话历史（含核心记忆），返回 OpenAI Chat 格式。

        Args:
            max_count: 最多返回的消息条数（含核心记忆）。
        """
        result: list[dict[str, Any]] = [m.to_dict() for m in self.core_memory]
        remaining = max_count - len(result)
        if remaining > 0 and self.messages:
            result.extend(m.to_dict() for m in self.messages[-remaining:])
        return result

    def prune(self, max_count: int, threshold: int) -> bool:
        """裁剪消息数至 max_count，超过 threshold 时触发蒸馏标记。

        Returns:
            是否需要蒸馏（消息数 >= threshold）。
        """
        # 先判断是否达到蒸馏阈值
        if len(self.messages) < threshold:
            return False

        # 再裁剪到 max_count
        if len(self.messages) > max_count:
            self.messages = self.messages[-max_count:]

        return True

    def clear(self) -> None:
        """清空当前会话记忆。"""
        self.messages.clear()
        self.core_memory.clear()
        self.last_proactive_time = 0.0


class MemoryStore:
    """全局记忆存储。

    按 session_id 管理独立会话，线程安全。
    可选集成 ChatPersistence 进行持久化存储。
    """

    def __init__(self, persistence: Any = None) -> None:
        """初始化记忆存储。

        Args:
            persistence: 可选的 ChatPersistence 实例，用于持久化消息和摘要。
        """
        self._sessions: dict[str, SessionMemory] = {}
        self._lock = asyncio.Lock()
        self._persistence = persistence

    async def _get_or_create(self, session_id: str) -> SessionMemory:
        async with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionMemory(session_id=session_id)
            return self._sessions[session_id]

    async def add_user_message(self, session_id: str, content: str) -> None:
        """添加用户消息。"""
        (await self._get_or_create(session_id)).add_message("user", content)

    async def add_user_message_with_meta(
        self,
        session_id: str,
        user_id: str,
        content: str,
        group_id: str | None = None,
    ) -> None:
        """添加用户消息（含用户/群元数据，用于持久化）。

        Args:
            session_id: 会话唯一标识。
            user_id: 用户 ID。
            content: 消息内容。
            group_id: 群 ID，私聊时为 None。
        """
        (await self._get_or_create(session_id)).add_message("user", content)
        self._persist_message(session_id, user_id, group_id, "user", content)

    async def add_assistant_message(self, session_id: str, content: str) -> None:
        """添加助手消息。"""
        (await self._get_or_create(session_id)).add_message("assistant", content)

    async def add_assistant_message_with_meta(
        self,
        session_id: str,
        user_id: str,
        content: str,
        group_id: str | None = None,
    ) -> None:
        """添加助手消息（含用户/群元数据，用于持久化）。

        Args:
            session_id: 会话唯一标识。
            user_id: 用户 ID（消息来源用户）。
            content: 消息内容。
            group_id: 群 ID，私聊时为 None。
        """
        (await self._get_or_create(session_id)).add_message("assistant", content)
        self._persist_message(session_id, user_id, group_id, "assistant", content)

    def _persist_message(
        self,
        session_id: str,
        user_id: str,
        group_id: str | None,
        role: str,
        content: str,
    ) -> None:
        """旁路持久化消息（失败不阻断）。"""
        if self._persistence is None:
            return
        try:
            self._persistence.save_message(session_id, user_id, group_id, role, content)
        except Exception:
            logger.warning(
                "Failed to persist message (session=%s, role=%s)",
                session_id, role, exc_info=True,
            )

    async def get_history(self, session_id: str, max_count: int = 50) -> list[dict[str, Any]]:
        """获取会话历史。"""
        return (await self._get_or_create(session_id)).get_history(max_count)

    async def needs_distillation(
        self, session_id: str, max_count: int, threshold: int
    ) -> bool:
        """检查是否需要蒸馏。"""
        return (await self._get_or_create(session_id)).prune(max_count, threshold)

    async def try_begin_distill(self, session_id: str) -> bool:
        """尝试开始蒸馏（原子操作）。

        Returns:
            True 表示获取蒸馏锁成功，调用方应执行蒸馏。
            False 表示已有其他协程在蒸馏此会话。
        """
        async with self._lock:
            mem = self._sessions.get(session_id)
            if mem is None:
                return False
            if mem._distilling:
                return False
            mem._distilling = True
            return True

    async def end_distill(self, session_id: str) -> None:
        """结束蒸馏，释放锁。"""
        async with self._lock:
            mem = self._sessions.get(session_id)
            if mem is not None:
                mem._distilling = False

    async def set_core_memory(self, session_id: str, summaries: list[str]) -> None:
        """设置核心记忆（蒸馏摘要）。"""
        mem = await self._get_or_create(session_id)
        mem.core_memory = [
            Message(role="system", content=s) for s in summaries
        ]

    async def get_last_proactive_time(self, session_id: str) -> float:
        """获取上次主动回复时间戳。"""
        return (await self._get_or_create(session_id)).last_proactive_time

    async def set_last_proactive_time(self, session_id: str, timestamp: float) -> None:
        """设置上次主动回复时间戳。"""
        (await self._get_or_create(session_id)).last_proactive_time = timestamp

    async def clear_session(self, session_id: str) -> None:
        """清空指定会话。"""
        async with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].clear()

    async def clear_all(self) -> None:
        """清空所有会话。"""
        async with self._lock:
            for session in self._sessions.values():
                session.clear()

    def session_count(self) -> int:
        """当前活跃会话数。"""
        return len(self._sessions)

    def get_core_memory_count(self, session_id: str) -> int:
        """获取指定会话的核心记忆条数。"""
        mem = self._sessions.get(session_id)
        if mem is None:
            return 0
        return len(mem.core_memory)
