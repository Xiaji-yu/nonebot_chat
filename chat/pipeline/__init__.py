"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Pipeline orchestrator — chains all stages into a single flow
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

from .sleep import SleepController
from .dedup import check as dedup_check
from .access import AccessController
from .silent import SilentFilter
from .ratelimit import RateLimiter
from .trigger import TriggerDetector
from .admin import AdminInterceptor, CMD_CLEAR_MEMORY, CMD_STATUS, CMD_SLEEP, CMD_WAKE
from .dispatcher import AIDispatcher
from .debounce import Debouncer
from .formatter import MessageFormatter
from .sender import MessageSender

logger = logging.getLogger(__name__)


class Pipeline:
    """聊天 Pipeline 编排器。

    处理流程：

        Event → sleep → dedup → access → silent → ratelimit
              → admin → debounce_accumulate → trigger → dispatcher → formatter → sender

    防抖在触发检测之后、AI 派发之前生效，窗口内消息合并为一条再发送给 LLM。
    """

    def __init__(
        self,
        pipeline_config: Any,
        personality: Any,
        llm_client: Any,
        memory_store: Any,
        distiller: Any,
    ) -> None:
        self._cfg = pipeline_config
        self._sleep = SleepController(pipeline_config.sleep)
        self._access = AccessController(pipeline_config.access)
        self._silent = SilentFilter(pipeline_config.silent)
        self._ratelimit = RateLimiter(pipeline_config.ratelimit)
        self._trigger = TriggerDetector(pipeline_config.trigger)
        self._admin = AdminInterceptor(pipeline_config.admin)
        self._debounce = Debouncer(pipeline_config.debounce)
        self._formatter = MessageFormatter(pipeline_config.format)

        self._dispatcher = AIDispatcher(
            personality=personality,
            llm_client=llm_client,
            memory_store=memory_store,
            distiller=distiller,
            trigger_detector=self._trigger,
        )

        self._personality = personality
        self._memory_store = memory_store
        self._proactive = None  # 可选注入

    # ------------------------------------------------------------------
    # Pipeline 入口
    # ------------------------------------------------------------------

    async def process(
        self,
        event: Any,
        session_id: str,
        send_func: Any,
    ) -> None:
        """执行完整 Pipeline。"""
        text = event.get_plaintext().strip()
        user_id = str(getattr(event, "user_id", ""))
        group_id = getattr(event, "group_id", None)
        if group_id is not None:
            group_id = str(group_id)

        # Stage 0: 休眠检测
        if await self._sleep.is_sleeping():
            is_mention = self._trigger.is_mention(event)
            if not is_mention or not await self._sleep.is_override_allowed():
                logger.debug("Dropped: sleeping mode, no mention override")
                return
            logger.debug("Sleep override by mention")

        # Stage 1: 去重
        if self._cfg.dedup.enabled and await dedup_check(session_id, text):
            logger.debug("Dropped: duplicate message")
            return

        # Stage 2: 黑白名单
        allowed, reason = self._access.check(user_id, group_id)
        if not allowed:
            logger.debug("Dropped: access denied (%s) user=%s", reason, user_id)
            return

        # Stage 3: 静默关键词
        if self._cfg.silent.enabled and self._silent.is_silent(text):
            logger.debug("Dropped: silent keyword matched")
            return

        # Stage 4: 频控
        allowed, retry = await self._ratelimit.check(session_id)
        if not allowed:
            logger.debug("Dropped: rate limited (retry in %.1fs)", retry)
            return

        # Stage 5: 管理命令拦截（不走 debounce，立即执行）
        admin_reply = self._admin.intercept(text)
        if admin_reply is not None:
            await self._handle_admin(admin_reply, session_id, send_func)
            return

        # Stage 6: 防抖合并
        if self._cfg.debounce.enabled:
            original_send = send_func

            async def _send_and_proactive(text: str) -> None:
                await original_send(text)
                await self._maybe_proactive(session_id, original_send)

            await self._debounce.submit(session_id, text, _send_and_proactive)
            return

        # 防抖关闭：直接走触发检测 → AI 派发
        await self._process_once(event, session_id, text, send_func)

        # 主动回复（经过 sleep/access/ratelimit 检查后）
        await self._maybe_proactive(session_id, send_func)

    def set_proactive(self, proactive: Any) -> None:
        """注入主动回复器。"""
        self._proactive = proactive

    async def _process_once(
        self,
        event: Any,
        session_id: str,
        text: str,
        send_func: Any,
    ) -> None:
        """单次处理（触发检测 → AI 派发 → 发送）。"""
        triggered, trigger_type = self._trigger.detect(event)
        if not triggered:
            logger.debug("Dropped: trigger not matched")
            return

        reply = await self._dispatcher.dispatch(session_id, text, trigger_type)
        if reply is None:
            await send_func("抱歉，我暂时无法回复，请稍后再试。")
            return

        sender = MessageSender(send_func)
        parts = self._formatter.format(reply)
        await sender.send_batch(parts)

    async def _maybe_proactive(self, session_id: str, send_func: Any) -> None:
        """条件性主动回复。经过 sleep/access/ratelimit 检查。"""
        if self._proactive is None:
            return
        await self._proactive.generate_and_reply(
            session_id, send_func=send_func,
        )

    async def _handle_admin(self, cmd: str, session_id: str, send_func: Any) -> None:
        """处理管理命令。"""
        if cmd == CMD_CLEAR_MEMORY:
            self._memory_store.clear_session(session_id)
            await send_func("记忆已清空 ✓")
        elif cmd == CMD_STATUS:
            await self._send_status(session_id, send_func)
        elif cmd == CMD_SLEEP:
            sleeping = await self._sleep.toggle()
            state = "已进入休眠模式 😴" if sleeping else "已唤醒 🌅"
            await send_func(state)
        elif cmd == CMD_WAKE:
            await self._sleep.force_wake()
            await send_func("已强制唤醒 🌅")
        else:
            await send_func(cmd)

    async def _send_status(self, session_id: str, send_func: Any) -> None:
        """发送状态信息。"""
        mem_count = len(await self._memory_store.get_history(session_id))
        core_count = self._memory_store.get_core_memory_count(session_id)
        sleeping = await self._sleep.is_sleeping()
        status_text = (
            f"📊 状态报告\n"
            f"  会话消息: {mem_count} 条\n"
            f"  核心记忆: {core_count} 条\n"
            f"  休眠模式: {'开启 😴' if sleeping else '关闭 🌅'}\n"
            f"  触发模式: {self._trigger.mode}"
        )
        await send_func(status_text)

    # ------------------------------------------------------------------
    # 属性访问（供外部组件引用）
    # ------------------------------------------------------------------

    @property
    def sleep_controller(self) -> SleepController:
        return self._sleep

    @property
    def rate_limiter(self) -> RateLimiter:
        return self._ratelimit

    @property
    def trigger_detector(self) -> TriggerDetector:
        return self._trigger

    @property
    def debouncer(self) -> Debouncer:
        return self._debounce

    @property
    def formatter(self) -> MessageFormatter:
        return self._formatter

    @property
    def dispatcher(self) -> AIDispatcher:
        return self._dispatcher
