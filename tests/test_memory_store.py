"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 记忆存储测试 — 会话 CRUD、并发安全、蒸馏锁
"""

from __future__ import annotations

import asyncio

import pytest

from chat.memory.store import MemoryStore, Message, SessionMemory

# ── Message ────────────────────────────────────────────────────────


class TestMessage:
    def test_to_dict(self) -> None:
        msg = Message(role="user", content="hello")
        d = msg.to_dict()
        assert d == {"role": "user", "content": "hello"}

    def test_timestamp_default(self) -> None:
        msg = Message(role="user", content="hello")
        assert msg.timestamp > 0.0

    def test_custom_timestamp(self) -> None:
        msg = Message(role="assistant", content="hi", timestamp=100.0)
        assert msg.timestamp == 100.0


# ── SessionMemory ──────────────────────────────────────────────────


class TestSessionMemory:
    def test_add_message(self) -> None:
        sm = SessionMemory(session_id="test")
        sm.add_message("user", "hello")
        assert len(sm.messages) == 1
        assert sm.messages[0].role == "user"
        assert sm.messages[0].content == "hello"

    def test_get_history_with_core_memory(self) -> None:
        sm = SessionMemory(session_id="test")
        sm.core_memory = [Message(role="system", content="core info")]
        sm.add_message("user", "hello")
        sm.add_message("assistant", "hi")

        history = sm.get_history(max_count=10)
        assert len(history) == 3
        assert history[0]["role"] == "system"  # core memory first
        assert history[0]["content"] == "core info"

    def test_get_history_respects_max_count(self) -> None:
        sm = SessionMemory(session_id="test")
        for i in range(10):
            sm.add_message("user", f"msg{i}")

        history = sm.get_history(max_count=3)
        assert len(history) == 3
        # 应返回最后 3 条
        assert history[-1]["content"] == "msg9"

    def test_prune_returns_false_below_threshold(self) -> None:
        sm = SessionMemory(session_id="test")
        for i in range(5):
            sm.add_message("user", f"msg{i}")

        needs_distill = sm.prune(max_count=10, threshold=10)
        assert needs_distill is False
        assert len(sm.messages) == 5  # 未裁剪

    def test_prune_returns_true_at_threshold(self) -> None:
        sm = SessionMemory(session_id="test")
        for i in range(10):
            sm.add_message("user", f"msg{i}")

        needs_distill = sm.prune(max_count=20, threshold=10)
        assert needs_distill is True

    def test_prune_trims_to_max_count(self) -> None:
        sm = SessionMemory(session_id="test")
        for i in range(20):
            sm.add_message("user", f"msg{i}")

        sm.prune(max_count=5, threshold=15)  # threshold <= 20 to trigger prune
        assert len(sm.messages) == 5
        # 保留最后 5 条
        assert sm.messages[-1].content == "msg19"

    def test_clear(self) -> None:
        sm = SessionMemory(session_id="test")
        sm.add_message("user", "hello")
        sm.core_memory = [Message(role="system", content="core")]
        sm.last_proactive_time = 123.0

        sm.clear()
        assert len(sm.messages) == 0
        assert len(sm.core_memory) == 0
        assert sm.last_proactive_time == 0.0


# ── MemoryStore ────────────────────────────────────────────────────


class TestMemoryStore:
    @pytest.mark.asyncio
    async def test_add_and_get_history(self) -> None:
        ms = MemoryStore()
        await ms.add_user_message("session-1", "hello")
        await ms.add_assistant_message("session-1", "hi")

        history = await ms.get_history("session-1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_sessions_isolated(self) -> None:
        ms = MemoryStore()
        await ms.add_user_message("session-1", "msg1")
        await ms.add_user_message("session-2", "msg2")

        h1 = await ms.get_history("session-1")
        h2 = await ms.get_history("session-2")
        assert len(h1) == 1
        assert len(h2) == 1
        assert h1[0]["content"] == "msg1"
        assert h2[0]["content"] == "msg2"

    @pytest.mark.asyncio
    async def test_clear_session(self) -> None:
        ms = MemoryStore()
        await ms.add_user_message("session-1", "hello")
        await ms.clear_session("session-1")

        history = await ms.get_history("session-1")
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_clear_all(self) -> None:
        ms = MemoryStore()
        await ms.add_user_message("session-1", "hello")
        await ms.add_user_message("session-2", "world")

        await ms.clear_all()
        assert len(await ms.get_history("session-1")) == 0
        assert len(await ms.get_history("session-2")) == 0

    @pytest.mark.asyncio
    async def test_session_count(self) -> None:
        ms = MemoryStore()
        assert ms.session_count() == 0

        await ms.add_user_message("session-1", "hello")
        assert ms.session_count() == 1

        await ms.add_user_message("session-2", "world")
        assert ms.session_count() == 2

    @pytest.mark.asyncio
    async def test_core_memory(self) -> None:
        ms = MemoryStore()
        await ms.set_core_memory("session-1", ["核心要点1", "核心要点2"])

        history = await ms.get_history("session-1")
        assert len(history) == 2
        assert history[0]["role"] == "system"
        assert history[0]["content"] == "核心要点1"

    @pytest.mark.asyncio
    async def test_get_core_memory_count(self) -> None:
        ms = MemoryStore()
        assert ms.get_core_memory_count("session-1") == 0

        await ms.set_core_memory("session-1", ["a", "b", "c"])
        assert ms.get_core_memory_count("session-1") == 3

    @pytest.mark.asyncio
    async def test_proactive_time(self) -> None:
        ms = MemoryStore()
        assert await ms.get_last_proactive_time("session-1") == 0.0

        await ms.set_last_proactive_time("session-1", 123.456)
        assert await ms.get_last_proactive_time("session-1") == 123.456

    @pytest.mark.asyncio
    async def test_try_begin_distill(self) -> None:
        ms = MemoryStore()
        await ms.add_user_message("session-1", "hello")

        # 第一次尝试应成功
        assert (await ms.try_begin_distill("session-1")) is True

        # 第二次尝试应失败（已在蒸馏中）
        assert (await ms.try_begin_distill("session-1")) is False

        # 结束后可以再次蒸馏
        await ms.end_distill("session-1")
        assert (await ms.try_begin_distill("session-1")) is True

    @pytest.mark.asyncio
    async def test_try_begin_distill_nonexistent(self) -> None:
        ms = MemoryStore()
        assert (await ms.try_begin_distill("nonexistent")) is False


class TestMemoryStoreConcurrent:
    """并发安全性测试。"""

    @pytest.mark.asyncio
    async def test_concurrent_add_messages(self) -> None:
        """并发添加消息不应丢失数据。"""
        ms = MemoryStore()

        async def add_many(session_id: str, start: int, count: int) -> None:
            for i in range(start, start + count):
                await ms.add_user_message(session_id, f"msg{i}")

        await asyncio.gather(
            add_many("shared", 0, 50),
            add_many("shared", 50, 50),
        )

        history = await ms.get_history("shared", max_count=200)
        assert len(history) == 100

    @pytest.mark.asyncio
    async def test_concurrent_distill_lock(self) -> None:
        """并发蒸馏只有一个能获取锁。"""
        ms = MemoryStore()
        await ms.add_user_message("session-1", "hello")

        async def try_distill() -> bool:
            return await ms.try_begin_distill("session-1")

        results = await asyncio.gather(
            try_distill(),
            try_distill(),
            try_distill(),
        )
        # 只有一个成功
        assert sum(results) == 1