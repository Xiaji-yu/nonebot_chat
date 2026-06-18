"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Memory store — per-session conversation history with thread safety
"""

__author__ = "Xiaji-yu"

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
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
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionMemory] = {}
        self._lock = Lock()

    def _get_or_create(self, session_id: str) -> SessionMemory:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionMemory(session_id=session_id)
            return self._sessions[session_id]

    def add_user_message(self, session_id: str, content: str) -> None:
        """添加用户消息。"""
        self._get_or_create(session_id).add_message("user", content)

    def add_assistant_message(self, session_id: str, content: str) -> None:
        """添加助手消息。"""
        self._get_or_create(session_id).add_message("assistant", content)

    def get_history(self, session_id: str, max_count: int = 50) -> list[dict[str, Any]]:
        """获取会话历史。"""
        return self._get_or_create(session_id).get_history(max_count)

    def needs_distillation(
        self, session_id: str, max_count: int, threshold: int
    ) -> bool:
        """检查是否需要蒸馏。"""
        return self._get_or_create(session_id).prune(max_count, threshold)

    def set_core_memory(self, session_id: str, summaries: list[str]) -> None:
        """设置核心记忆（蒸馏摘要）。"""
        mem = self._get_or_create(session_id)
        mem.core_memory = [
            Message(role="system", content=s) for s in summaries
        ]

    def get_last_proactive_time(self, session_id: str) -> float:
        """获取上次主动回复时间戳。"""
        return self._get_or_create(session_id).last_proactive_time

    def set_last_proactive_time(self, session_id: str, timestamp: float) -> None:
        """设置上次主动回复时间戳。"""
        self._get_or_create(session_id).last_proactive_time = timestamp

    def clear_session(self, session_id: str) -> None:
        """清空指定会话。"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].clear()

    def clear_all(self) -> None:
        """清空所有会话。"""
        with self._lock:
            for session in self._sessions.values():
                session.clear()

    def session_count(self) -> int:
        """当前活跃会话数。"""
        return len(self._sessions)
