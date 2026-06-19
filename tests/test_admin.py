"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 管理命令拦截器测试
"""

from __future__ import annotations

import pytest

from chat.pipeline.admin import (
    CMD_CLEAR_MEMORY,
    CMD_SLEEP,
    CMD_STATUS,
    CMD_WAKE,
    AdminInterceptor,
)

# ── Mock 工厂 ──────────────────────────────────────────────────────


def make_config(enabled: bool = True) -> object:
    cfg = type("AdminConfig", (), {})()
    cfg.enabled = enabled
    return cfg


# ── 测试 ──────────────────────────────────────────────────────────


class TestAdminInterceptor:
    @pytest.mark.asyncio
    async def test_clear_memory_command(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("清空记忆")
        assert result == CMD_CLEAR_MEMORY

    @pytest.mark.asyncio
    async def test_clear_alias(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("clear")
        assert result == CMD_CLEAR_MEMORY

    @pytest.mark.asyncio
    async def test_status_command(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("状态")
        assert result == CMD_STATUS

    @pytest.mark.asyncio
    async def test_status_alias(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("status")
        assert result == CMD_STATUS

    @pytest.mark.asyncio
    async def test_sleep_command(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("休眠")
        assert result == CMD_SLEEP

    @pytest.mark.asyncio
    async def test_sleep_alias(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("sleep")
        assert result == CMD_SLEEP

    @pytest.mark.asyncio
    async def test_wake_command(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("唤醒")
        assert result == CMD_WAKE

    @pytest.mark.asyncio
    async def test_wake_alias(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("wake")
        assert result == CMD_WAKE

    @pytest.mark.asyncio
    async def test_non_command_returns_none(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("你好世界")
        assert result is None

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self) -> None:
        ai = AdminInterceptor(make_config(enabled=False))
        result = await ai.intercept("清空记忆")
        assert result is None

    @pytest.mark.asyncio
    async def test_command_with_args(self) -> None:
        """命令带参数时仍应识别（如 '清空记忆 全部'）。"""
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("清空记忆 全部")
        assert result == CMD_CLEAR_MEMORY

    @pytest.mark.asyncio
    async def test_command_with_extra_spaces(self) -> None:
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("  状态  ")
        assert result == CMD_STATUS

    @pytest.mark.asyncio
    async def test_custom_handler_overrides_builtin(self) -> None:
        """自定义 handler 可以覆盖内置命令的行为。"""
        ai = AdminInterceptor(make_config())

        async def custom_handler(args: str) -> str | None:
            return f"custom_reply:{args}"

        # 注册覆盖 "清空记忆" 命令
        ai.register("clear_memory", custom_handler)
        result = await ai.intercept("清空记忆 全部")
        assert result == "custom_reply:全部"

    @pytest.mark.asyncio
    async def test_custom_handler_case_insensitive_key(self) -> None:
        """注册命令 key 应大小写不敏感。"""
        ai = AdminInterceptor(make_config())

        async def handler(args: str) -> str | None:
            return "ok"

        ai.register("Clear_Memory", handler)
        # clear_memory 是内置命令 "清空记忆" / "clear" 的解析结果
        result = await ai.intercept("clear")
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_command_not_in_builtin_list(self) -> None:
        """不在内置命令列表中的文本不应被识别。"""
        ai = AdminInterceptor(make_config())
        result = await ai.intercept("你好")
        assert result is None