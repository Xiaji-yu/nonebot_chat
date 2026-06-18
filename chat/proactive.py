"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Proactive reply logic — probabilistic spontaneous responses
"""

__author__ = "Xiaji-yu"

import logging
import random
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]
SessionIdFunc = Callable[[Any], str]


class ProactiveReplier:
    """主动回复控制器。

    在消息处理流中调用，按概率决定是否触发一条与上下文无关的主动回复。
    """

    def __init__(
        self,
        personality: Any,  # Personality
        memory_store: Any,  # MemoryStore
        llm_client: Any,    # LLMClient
    ) -> None:
        self._personality = personality
        self._memory = memory_store
        self._llm = llm_client

    def should_reply(self, session_id: str) -> bool:
        """检查是否应该触发主动回复。

        Args:
            session_id: 会话唯一标识。

        Returns:
            是否满足主动回复条件。
        """
        if not self._personality.proactive_enabled:
            return False

        # 概率检查
        if random.random() > self._personality.proactive_probability:
            return False

        # 冷却检查
        last = self._memory.get_last_proactive_time(session_id)
        now = time.time()
        cooldown = self._personality.proactive_cooldown
        if now - last < cooldown:
            return False

        return True

    async def generate_and_reply(
        self,
        session_id: str,
        bot: Any,
        event: Any,
        bot_send: SendFunc | None = None,
    ) -> None:
        """生成并发送主动回复。

        Args:
            session_id: 会话 ID。
            bot: Bot 实例。
            event: 消息事件。
            bot_send: 可选的自定义发送函数。
        """
        prompt = self._build_proactive_prompt()

        temperature = random.uniform(
            self._personality.temperature_proactive_min,
            self._personality.temperature_proactive_max,
        )

        reply = await self._llm.chat(
            messages=prompt,
            temperature=temperature,
            max_tokens=100,
        )

        if not reply:
            return

        self._memory.set_last_proactive_time(session_id, time.time())
        try:
            if bot_send is not None:
                await bot_send(reply)
            elif hasattr(bot, "send"):
                await bot.send(event, reply)
        except Exception:
            logger.exception("Failed to send proactive reply")

    def _build_proactive_prompt(self) -> list[dict[str, str]]:
        """构建主动回复的 prompt。"""
        system_text = (
            f"你是{self._personality.name}。"
            "现在你决定主动和用户说一句话，可以是关心、分享趣事、或简单打招呼。"
            "只输出一句话，自然口语化，不要超过30字。"
        )
        return [
            {"role": "system", "content": system_text},
            {"role": "user", "content": "(主动发起对话)"},
        ]
