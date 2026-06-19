"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : AI dispatcher — builds context and calls LLM
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

from .trigger import TriggerDetector

logger = logging.getLogger(__name__)


class AIDispatcher:
    """AI 派发器。

    接收经过各阶段过滤后的消息，构建完整的 prompt 上下文，
    调用 LLM 并返回回复文本。
    """

    def __init__(
        self,
        personality: Any,
        llm_client: Any,
        memory_store: Any,
        distiller: Any,
        trigger_detector: TriggerDetector,
    ) -> None:
        self._personality = personality
        self._llm = llm_client
        self._memory = memory_store
        self._distiller = distiller
        self._trigger = trigger_detector

    async def dispatch(
        self,
        session_id: str,
        user_input: str,
        trigger_type: str,
        user_id: str = "",
        group_id: str | None = None,
    ) -> str | None:
        """派发消息到 AI。

        Args:
            session_id: 会话唯一标识。
            user_input: 用户输入（已清洗）。
            trigger_type: 触发类型（mention/keyword/spectator）。
            user_id: 用户 ID（用于持久化）。
            group_id: 群 ID（用于持久化），私聊时为 None。

        Returns:
            AI 回复文本，失败返回 None。
        """
        # 存储用户消息（含元数据）
        if user_id:
            await self._memory.add_user_message_with_meta(session_id, user_id, user_input, group_id)
        else:
            await self._memory.add_user_message(session_id, user_input)

        # 原子蒸馏检查（防止并发双重蒸馏）
        if await self._memory.try_begin_distill(session_id):
            try:
                await self._distiller.distill(
                    session_id,
                    self._personality.memory_core_memory_max,
                )
            finally:
                await self._memory.end_distill(session_id)

        # 构建消息列表
        messages = await self._build_messages(session_id, user_input, trigger_type)

        # 调用 LLM
        reply = await self._llm.chat(
            messages,
            temperature=self._personality.temperature_default,
        )

        if reply is not None:
            if user_id:
                await self._memory.add_assistant_message_with_meta(
                    session_id, user_id, reply, group_id,
                )
            else:
                await self._memory.add_assistant_message(session_id, reply)

        return reply

    async def _build_messages(
        self,
        session_id: str,
        user_input: str,
        trigger_type: str,
    ) -> list[dict[str, str]]:
        """构建发送给 LLM 的消息列表。"""
        msgs: list[dict[str, str]] = [self._personality.build_system_message()]

        # 加入历史对话
        history = await self._memory.get_history(
            session_id, self._personality.memory_max_history
        )
        msgs.extend(history)

        # 触发类型注入（辅助 LLM 理解上下文）
        if trigger_type and trigger_type != "spectator":
            context_note = self._build_context_note(trigger_type)
            if context_note:
                msgs.append({"role": "system", "content": context_note})

        # 当前用户输入
        msgs.append({"role": "user", "content": user_input})
        return msgs

    def _build_context_note(self, trigger_type: str) -> str:
        """构建触发上下文提示。"""
        if trigger_type == "mention":
            return "(用户通过 @提及 触发了本次对话)"
        if trigger_type.startswith("keyword"):
            return "(用户通过关键词触发了本次对话)"
        return ""
