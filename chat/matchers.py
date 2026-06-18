"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Chat matchers — pipeline entry points
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any, Awaitable, Callable

from .config import ChatConfig
from .personality import Personality
from .llm import LLMClient
from .memory import MemoryStore, MemoryDistiller
from .pipeline import Pipeline
from .proactive import ProactiveReplier

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]
SessionIdFunc = Callable[[Any], str]


def get_session_id(event: Any) -> str:
    """从事件中提取会话唯一标识。

    优先使用 group_id + user_id（群聊），
    降级到 user_id（私聊），最后使用 session_id 兜底。
    """
    gid = getattr(event, "group_id", None)
    uid = getattr(event, "user_id", None)
    if gid is not None and uid is not None:
        return f"g{gid}_u{uid}"
    if uid is not None:
        return f"u{uid}"
    return str(getattr(event, "session_id", id(event)))


def setup_matchers(
    config: ChatConfig,
    personality: Personality,
    llm_client: LLMClient,
    memory_store: MemoryStore,
    distiller: MemoryDistiller,
    proactive: ProactiveReplier,
    bot_send: SendFunc | None = None,
) -> None:
    """注册聊天相关的命令和消息匹配器。

    Args:
        config: 聊天插件配置。
        personality: 人格配置。
        llm_client: LLM 客户端。
        memory_store: 记忆存储。
        distiller: 记忆蒸馏器。
        proactive: 主动回复器。
        bot_send: 可选，异步发送函数。None 则使用 NoneBot 默认发送。
    """
    if not config.chat_enabled:
        logger.info("Chat plugin disabled by config.")
        return

    # 构建 Pipeline（配置从 YAML 加载）
    pipeline = Pipeline(
        pipeline_config=personality.pipeline_config,
        personality=personality,
        llm_client=llm_client,
        memory_store=memory_store,
        distiller=distiller,
    )

    # 延迟导入 NoneBot（运行时才需要）
    from nonebot import on_command, on_message
    from nonebot.permission import SUPERUSER

    permission = (config.only_superusers or None) and SUPERUSER

    def _make_send(bot: Any, event: Any) -> SendFunc:
        """创建发送函数闭包。"""
        async def _send(text: str) -> None:
            if bot_send is not None:
                await bot_send(text)
            elif hasattr(bot, "send"):
                await bot.send(event, text)
        return _send

    # ── 命令匹配器 /chat ──────────────────────────────────────────
    cmd_matcher = on_command(
        "chat",
        aliases={"聊天", "对话"},
        permission=permission,
        priority=20,
        block=True,
    )

    @cmd_matcher.handle()
    async def _handle_command(bot: Any, event: Any) -> None:
        await pipeline.process(event, get_session_id(event), _make_send(bot, event))

        # 主动回复检查
        sid = get_session_id(event)
        if proactive.should_reply(sid):
            await proactive.generate_and_reply(sid, bot, event, bot_send)

    # ── 消息匹配器（触发检测） ─────────────────────────────────────
    msg_matcher = on_message(
        permission=permission,
        priority=15,
        block=True,
    )

    @msg_matcher.handle()
    async def _handle_message(bot: Any, event: Any) -> None:
        await pipeline.process(event, get_session_id(event), _make_send(bot, event))

    logger.info(
        "Chat matchers registered (only_superusers=%s, trigger=%s).",
        config.only_superusers,
        config.pipeline.trigger.mode,
    )
