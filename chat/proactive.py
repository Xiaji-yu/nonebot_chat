"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Proactive reply logic — probabilistic spontaneous responses
"""

__author__ = "Xiaji-yu"

import asyncio
import logging
import random
import time
from threading import Lock
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]


class ProactiveReplier:
    """主动回复控制器。

    在消息处理流中调用，按概率决定是否触发一条与上下文无关的主动回复。
    使用 per-session 锁保证 should_reply 和 generate_and_reply 原子执行，
    避免并发场景下的 TOCTOU 竞态。
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
        # per-session 锁，防止并发时重复触发
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = Lock()

    def should_reply(self, session_id: str) -> bool:
        """检查是否应该触发主动回复（不设置冷却标记）。

        使用 should_reply_and_mark() 进行原子检查+标记。
        此方法保留用于统计/诊断场景。
        """
        if not self._personality.proactive_enabled:
            return False
        if random.random() > self._personality.proactive_probability:
            return False
        last = self._memory.get_last_proactive_time(session_id)
        now = time.time()
        return (now - last) >= self._personality.proactive_cooldown

    def should_reply_and_mark(self, session_id: str) -> bool:
        """原子检查 + 设置冷却标记。

        在 asyncio 事件循环中执行，需要由调用方在 loop 中 await。

        Returns:
            是否允许主动回复。
        """
        if not self.should_reply(session_id):
            return False
        # 通过检查后立即标记冷却
        self._memory.set_last_proactive_time(session_id, time.time())
        return True

    async def generate_and_reply(
        self,
        session_id: str,
        send_func: SendFunc | None = None,
        bot: Any = None,
        event: Any = None,
    ) -> None:
        """生成并发送主动回复（通过 send_func 或 bot.send）。

        Args:
            session_id: 会话 ID。
            send_func: 异步发送函数（优先使用）。
            bot: Bot 实例（send_func 为 None 时使用）。
            event: 消息事件（bot.send 需要）。
        """
        # 使用 per-session 锁防止并发重复触发
        lock = self._get_lock(session_id)
        async with lock:
            if not self.should_reply_and_mark(session_id):
                return

            reply = await self._generate()
            if not reply:
                return

            await self._send(reply, send_func, bot, event)

    async def _generate(self) -> str | None:
        """调用 LLM 生成主动回复文本。"""
        temperature = random.uniform(
            self._personality.temperature_proactive_min,
            self._personality.temperature_proactive_max,
        )
        return await self._llm.chat(
            messages=self._build_proactive_prompt(),
            temperature=temperature,
            max_tokens=100,
        )

    async def _send(
        self,
        text: str,
        send_func: SendFunc | None,
        bot: Any,
        event: Any,
    ) -> None:
        """发送主动回复。"""
        try:
            if send_func is not None:
                await send_func(text)
            elif bot is not None and hasattr(bot, "send"):
                await bot.send(event, text)
            else:
                logger.warning("No send target for proactive reply: %.50s", text)
        except Exception:
            logger.exception("Failed to send proactive reply")

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        """获取或创建 session 级别的 asyncio 锁。"""
        with self._global_lock:
            if session_id not in self._session_locks:
                self._session_locks[session_id] = asyncio.Lock()
            return self._session_locks[session_id]

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
