"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Chat matchers — command and message event handlers with proactive support
"""

__author__ = "Xiaji-yu"

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .config import ChatConfig
from .personality import Personality
from .llm import LLMClient
from .memory import MemoryStore, MemoryDistiller
from .proactive import ProactiveReplier

logger = logging.getLogger(__name__)

# 类型检查时使用 NoneBot 类型（不触发运行时导入）
if TYPE_CHECKING:
    from nonebot import on_command, on_message
    from nonebot.adapters import Bot, MessageEvent

# 运行时类型别名（使用 Any 避免 NoneBot 导入）
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

    延迟导入 NoneBot 相关模块，避免在无 NoneBot 环境（如测试）中导入失败。

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

    # 延迟导入 NoneBot（运行时才需要）
    from nonebot import on_command, on_message
    from nonebot.permission import SUPERUSER

    permission = (config.only_superusers or None) and SUPERUSER

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
        await _handle_chat(
            bot, event, personality, llm_client, memory_store,
            distiller, proactive, bot_send, wake_required=False,
        )

    # ── 消息匹配器（唤醒词触发） ──────────────────────────────────
    async def _wake_rule(event: Any) -> bool:
        text = event.get_plaintext().strip()
        if not text:
            return False
        return personality.is_wake_word(text)

    msg_matcher = on_message(
        _wake_rule,
        permission=permission,
        priority=15,
        block=True,
    )

    @msg_matcher.handle()
    async def _handle_message(bot: Any, event: Any) -> None:
        await _handle_chat(
            bot, event, personality, llm_client, memory_store,
            distiller, proactive, bot_send, wake_required=False,
        )

    logger.info(
        "Chat matchers registered (only_superusers=%s).",
        config.only_superusers,
    )


# ── 核心处理逻辑 ──────────────────────────────────────────────────

async def _handle_chat(
    bot: Any,
    event: Any,
    personality: Personality,
    llm_client: LLMClient,
    memory_store: MemoryStore,
    distiller: MemoryDistiller,
    proactive: ProactiveReplier,
    bot_send: SendFunc | None,
    wake_required: bool,
) -> None:
    """统一的聊天处理入口。"""
    plain = event.get_plaintext().strip()
    session_id = get_session_id(event)

    # 移除唤醒词前缀
    for word in personality.wake_words:
        if plain.lower().startswith(word.lower()):
            plain = plain[len(word):].strip()
            break

    if not plain:
        await _send(bot, event, "我在，请说～", bot_send)
        return

    # 存储用户消息
    memory_store.add_user_message(session_id, plain)

    # 检查是否需要蒸馏
    if memory_store.needs_distillation(
        session_id,
        personality.memory_max_history,
        personality.memory_distillation_threshold,
    ):
        await distiller.distill(
            session_id,
            personality.memory_core_memory_max,
        )

    # 构建 prompt
    messages = _build_messages(personality, memory_store, session_id, plain)

    # 调用 LLM
    reply = await llm_client.chat(
        messages,
        temperature=personality.temperature_default,
    )

    if reply is None:
        await _send(bot, event, "抱歉，我暂时无法回复，请稍后再试。", bot_send)
        return

    # 存储助手回复
    memory_store.add_assistant_message(session_id, reply)

    # 发送回复
    await _send(bot, event, reply, bot_send)

    # 主动回复检查
    if proactive.should_reply(session_id):
        await proactive.generate_and_reply(session_id, bot, event, bot_send)


# ── 辅助函数 ──────────────────────────────────────────────────────

def _build_messages(
    personality: Personality,
    memory_store: MemoryStore,
    session_id: str,
    user_input: str,
) -> list[dict[str, str]]:
    """构建发送给 LLM 的消息列表。"""
    msgs: list[dict[str, str]] = [personality.build_system_message()]

    # 加入核心记忆 + 历史对话
    history = memory_store.get_history(
        session_id, personality.memory_max_history
    )
    msgs.extend(history)

    # 当前用户输入
    msgs.append({"role": "user", "content": user_input})
    return msgs


async def _send(
    bot: Any,
    event: Any,
    text: str,
    custom_send: SendFunc | None,
) -> None:
    """发送消息。"""
    if custom_send is not None:
        await custom_send(text)
    else:
        # NoneBot 内置发送（在 NoneBot 环境中有 Bot 实例）
        if hasattr(bot, "send"):
            await bot.send(event, text)
