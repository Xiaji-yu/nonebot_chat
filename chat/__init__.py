"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Chat plugin — personality-driven conversational AI with memory & proactive replies
"""

from __future__ import annotations
# Author: Xiaji-yu

import logging

logger = logging.getLogger(__name__)

__plugin_meta__: PluginMetadata | None = None
_chat_config: ChatConfig | None = None
_personality: Personality | None = None
_llm_client: LLMClient | None = None
_distiller: MemoryDistiller | None = None
_proactive: ProactiveReplier | None = None

# 纯 Python 实例，无需 NoneBot 或 aiohttp
_memory_store: MemoryStore | None = None


def _init() -> None:
    """延迟初始化：在 NoneBot 运行时调用。"""
    global _chat_config, _personality, _llm_client, _distiller, _proactive
    global _memory_store, __plugin_meta__

    if _chat_config is not None:
        return

    # 延迟导入（仅 NoneBot 运行时执行）
    from nonebot import get_plugin_config, get_driver
    from nonebot.plugin import PluginMetadata

    from .config import ChatConfig as _ChatConfig
    from .personality import Personality as _Personality
    from .llm import LLMClient as _LLMClient
    from .memory import MemoryStore as _MemoryStore, MemoryDistiller as _MemoryDistiller
    from .proactive import ProactiveReplier as _ProactiveReplier
    from .matchers import setup_matchers

    _chat_config = get_plugin_config(_ChatConfig)
    _personality = _Personality(_chat_config)
    _llm_client = _LLMClient(
        base_url=_personality.llm_base_url,
        model=_personality.llm_model,
        api_key=_personality.llm_api_key,
        max_tokens=_personality.llm_max_tokens,
        timeout=_personality.llm_timeout,
    )
    _memory_store = _MemoryStore()
    _distiller = _MemoryDistiller(_memory_store, _llm_client)
    _proactive = _ProactiveReplier(_personality, _memory_store, _llm_client)

    __plugin_meta__ = PluginMetadata(
        name="智能聊天",
        description="具有人格、记忆系统和主动回复能力的 AI 聊天插件",
        usage=(
            "发送唤醒词（如「小助手」）+ 消息，触发 AI 回复\n"
            "或直接发送 /chat 命令开始对话\n"
            "配置项位于项目目录下的 chat_config.yaml"
        ),
        type="application",
        homepage="",
        config=_ChatConfig,
        supported_adapters=None,
    )

    driver = get_driver()

    @driver.on_startup
    async def _on_startup() -> None:
        logger.info(
            "Chat plugin initializing: personality=%s, model=%s, base_url=%s",
            _personality.name,
            _personality.llm_model,
            _personality.llm_base_url,
        )

        setup_matchers(
            config=_chat_config,
            personality=_personality,
            llm_client=_llm_client,
            memory_store=_memory_store,
            distiller=_distiller,
            proactive=_proactive,
        )

        logger.info(
            "Memory store ready (max_history=%d).",
            _personality.memory_max_history,
        )

    @driver.on_shutdown
    async def _on_shutdown() -> None:
        _memory_store.clear_all()
        logger.info("Chat plugin shut down, memory cleared.")


def __getattr__(name: str):  # type: ignore[override]
    """延迟导出 NoneBot 相关符号。

    子模块（config / personality / llm / memory / proactive / matchers）
    不经过此函数，可以独立导入（不触发 NoneBot 依赖）。
    """
    _exports = {
        "chat_config": "_chat_config",
        "personality": "_personality",
        "llm_client": "_llm_client",
        "distiller": "_distiller",
        "proactive": "_proactive",
        "__plugin_meta__": "__plugin_meta__",
    }
    if name in _exports:
        _init()
        return globals()[_exports[name]]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
