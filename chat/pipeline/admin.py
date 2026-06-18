"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Admin command interceptor — handles management commands before AI dispatch
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]
AdminHandler = Callable[[str], Awaitable[str | None]]


class AdminInterceptor:
    """管理命令拦截器。

    在 AI 派发之前拦截管理命令，直接执行并返回回复。
    不经过 LLM，降低延迟和 token 消耗。
    """

    # 内置命令
    BUILTIN_COMMANDS: dict[str, str] = {
        "清空记忆": "clear_memory",
        "clear": "clear_memory",
        "状态": "status",
        "status": "status",
        "sleep": "sleep",
        "wake": "wake",
        "休眠": "sleep",
        "唤醒": "wake",
    }

    def __init__(self, admin_config: Any) -> None:
        self._enabled = admin_config.enabled
        self._custom_handlers: dict[str, AdminHandler] = {}

    def register(self, command: str, handler: AdminHandler) -> None:
        """注册自定义管理命令处理器。

        Args:
            command: 命令关键词。
            handler: 异步处理函数，接收参数字符串，返回回复文本或 None。
        """
        self._custom_handlers[command.lower()] = handler

    def intercept(self, text: str) -> str | None:
        """检查是否命中管理命令。

        Args:
            text: 消息纯文本。

        Returns:
            命令回复文本，非管理命令返回 None。
        """
        if not self._enabled:
            return None

        cmd_name, args = self._parse_command(text)
        if cmd_name is None:
            return None

        # 检查自定义处理器
        handler = self._custom_handlers.get(cmd_name)
        if handler is not None:
            import asyncio
            return asyncio.get_event_loop().run_until_complete(handler(args))

        # 内置命令
        return self._handle_builtin(cmd_name, args)

    def _parse_command(self, text: str) -> tuple[str | None, str]:
        """解析命令。

        Returns:
            (command_name, args) 或 (None, "")。
        """
        stripped = text.strip()
        for keyword, cmd in self.BUILTIN_COMMANDS.items():
            if stripped == keyword or stripped.startswith(keyword + " "):
                args = stripped[len(keyword):].strip()
                return cmd, args
        return None, ""

    def _handle_builtin(self, cmd: str, args: str) -> str | None:
        """处理内置命令。"""
        if cmd == "clear_memory":
            # 由外部注入 memory_store 处理
            return "__CLEAR_MEMORY__"
        if cmd == "status":
            return "__STATUS__"
        if cmd == "sleep":
            return "__SLEEP__"
        if cmd == "wake":
            return "__WAKE__"
        return None
