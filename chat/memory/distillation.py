"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Memory distillation — summarise long conversations into core memory
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

from .store import Message, MemoryStore, SessionMemory

logger = logging.getLogger(__name__)

# 蒸馏专用系统提示词
DISTILL_SYSTEM_PROMPT = (
    "你是一个记忆摘要助手。请将以下对话历史浓缩为 {max_points} 条核心要点，"
    "每条要点用一句话概括最重要的信息（如用户偏好、待办事项、关键决定）。"
    "只输出要点列表，每行一条，不要额外说明。"
)


class MemoryDistiller:
    """记忆蒸馏器。

    当会话消息数超过阈值时，调用 LLM 将旧对话摘要为若干条核心记忆，
    替换为 system 角色的消息，释放上下文窗口。
    """

    def __init__(self, memory_store: MemoryStore, llm_client: Any) -> None:
        self._store = memory_store
        self._llm = llm_client

    async def distill(
        self,
        session_id: str,
        max_points: int = 10,
    ) -> list[str] | None:
        """对指定会话执行蒸馏。

        Args:
            session_id: 会话 ID。
            max_points: 摘要条数上限。

        Returns:
            蒸馏后的摘要列表，失败返回 None。
        """
        session = await self._store._get_or_create(session_id)
        user_msgs = [m for m in session.messages if m.role in ("user", "assistant")]
        if not user_msgs:
            return None

        # 构造蒸馏 prompt
        conversation_text = "\n".join(
            f"{m.role}: {m.content}" for m in user_msgs
        )
        prompt = DISTILL_SYSTEM_PROMPT.format(max_points=max_points)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": conversation_text},
        ]

        logger.info(
            "Distilling session %s (%d messages) ...", session_id, len(user_msgs)
        )

        try:
            response = await self._llm.chat(messages, temperature=0.3)
        except Exception as exc:
            logger.error("Distillation failed for %s: %s", session_id, exc)
            return None

        if not response:
            return None

        # 按行拆分摘要
        summaries = [
            line.strip("- ").strip()
            for line in response.strip().split("\n")
            if line.strip()
        ][:max_points]

        if summaries:
            await self._store.set_core_memory(session_id, summaries)
            # set_core_memory 内部会创建新 SessionMemory，需重新获取引用
            session = await self._store._get_or_create(session_id)
            session.messages.clear()
            logger.info(
                "Distillation complete for %s: %d core memories stored.",
                session_id,
                len(summaries),
            )
        return summaries
