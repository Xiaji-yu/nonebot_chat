"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Admin command interceptor — handles management commands before AI dispatch
"""

__author__ = "Xiaji-yu"

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

# 类型别名
SendFunc = Callable[[str], Awaitable[Any]]
AdminHandler = Callable[[str], Awaitable[str | None]]

# 管理命令 sentinel（pipeline/__init__.py 中匹配）
CMD_CLEAR_MEMORY = "__CLEAR_MEMORY__"
CMD_STATUS = "__STATUS__"
CMD_SLEEP = "__SLEEP__"
CMD_WAKE = "__WAKE__"


class AdminInterceptor:
    """管理命令拦截器。

    在 AI 派发之前拦截管理命令，直接执行并返回回复。
    不经过 LLM，降低延迟和 token 消耗。
    """

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
        """注册自定义管理命令处理器。"""
        self._custom_handlers[command.lower()] = handler

    async def intercept(self, text: str) -> str | None:
        """检查是否命中管理命令（async 版本）。

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
            return await handler(args)

        # 内置命令
        return self._handle_builtin(cmd_name, args)

    def _parse_command(self, text: str) -> tuple[str | None, str]:
        """解析命令。"""
        stripped = text.strip()
        for keyword, cmd in self.BUILTIN_COMMANDS.items():
            if stripped == keyword or stripped.startswith(keyword + " "):
                args = stripped[len(keyword):].strip()
                return cmd, args
        return None, ""

    def _handle_builtin(self, cmd: str, args: str) -> str | None:
        """处理内置命令（返回标记，由 Pipeline 执行副作用）。"""
        if cmd == "clear_memory":
            return CMD_CLEAR_MEMORY
        if cmd == "status":
            return CMD_STATUS
        if cmd == "sleep":
            return CMD_SLEEP
        if cmd == "wake":
            return CMD_WAKE
        return None
