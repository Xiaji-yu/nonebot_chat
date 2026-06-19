"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : 持久化层测试 — SQLite 消息/摘要 CRUD、清理、按用户查询
"""

from __future__ import annotations

import os
import tempfile
import time

import pytest

from chat.memory.persistence import ChatPersistence
from chat.memory.store import MemoryStore

# ── Fixture ────────────────────────────────────────────────────────


@pytest.fixture
def db() -> ChatPersistence:
    """创建临时数据库的持久化实例。"""
    fd, path = tempfile.mkstemp(suffix=".db", prefix="test_chat_")
    os.close(fd)
    db = ChatPersistence(path)
    yield db
    db.close()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def db_disabled() -> ChatPersistence:
    """禁用的持久化实例。"""
    return ChatPersistence(None)


# ── 初始化 ─────────────────────────────────────────────────────────


class TestPersistenceInit:
    def test_enabled_when_db_path_provided(self, db: ChatPersistence) -> None:
        assert db.enabled is True

    def test_disabled_when_no_db_path(self) -> None:
        db = ChatPersistence(None)
        assert db.enabled is False

    def test_disabled_when_empty_db_path(self) -> None:
        db = ChatPersistence("")
        assert db.enabled is False


# ── 消息写入/读取 ──────────────────────────────────────────────────


class TestMessagePersistence:
    def test_save_and_get_messages(self, db: ChatPersistence) -> None:
        db.save_message("sess-1", "user-1", "group-1", "user", "hello")
        db.save_message("sess-1", "user-1", "group-1", "assistant", "hi")

        msgs = db.get_messages("sess-1")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "hi"

    def test_save_message_disabled_no_error(self, db_disabled: ChatPersistence) -> None:
        """禁用时写入不应该抛异常。"""
        db_disabled.save_message("sess-1", "user-1", None, "user", "hello")

    def test_get_messages_respects_limit(self, db: ChatPersistence) -> None:
        for i in range(20):
            db.save_message("sess-1", "user-1", None, "user", f"msg{i}")

        msgs = db.get_messages("sess-1", limit=5)
        assert len(msgs) == 5
        # 返回最后 5 条
        assert msgs[-1]["content"] == "msg19"

    def test_get_messages_disabled_returns_empty(self, db_disabled: ChatPersistence) -> None:
        assert db_disabled.get_messages("sess-1") == []

    def test_messages_contain_timestamps(self, db: ChatPersistence) -> None:
        db.save_message("sess-1", "user-1", None, "user", "hello")
        msgs = db.get_messages("sess-1")
        assert "created_at" in msgs[0]
        assert msgs[0]["created_at"] > 0


# ── 摘要写入/读取 ──────────────────────────────────────────────────


class TestSummaryPersistence:
    def test_save_and_get_summaries(self, db: ChatPersistence) -> None:
        db.save_summary("sess-1", "核心要点1")
        db.save_summary("sess-1", "核心要点2")

        summaries = db.get_summaries("sess-1")
        assert len(summaries) == 2
        assert "核心要点1" in summaries
        assert "核心要点2" in summaries

    def test_save_summaries_batch(self, db: ChatPersistence) -> None:
        db.save_summaries("sess-1", ["a", "b", "c"])
        assert len(db.get_summaries("sess-1")) == 3

    def test_save_summaries_empty_list(self, db: ChatPersistence) -> None:
        """空列表不应写入。"""
        db.save_summaries("sess-1", [])
        assert db.get_summaries("sess-1") == []

    def test_summaries_isolated_by_session(self, db: ChatPersistence) -> None:
        db.save_summary("sess-1", "摘要A")
        db.save_summary("sess-2", "摘要B")

        assert len(db.get_summaries("sess-1")) == 1
        assert len(db.get_summaries("sess-2")) == 1
        assert db.get_summaries("sess-1")[0] == "摘要A"

    def test_get_summaries_disabled_returns_empty(self, db_disabled: ChatPersistence) -> None:
        assert db_disabled.get_summaries("sess-1") == []


# ── 按用户查询 ─────────────────────────────────────────────────────


class TestUserMessages:
    def test_get_user_messages(self, db: ChatPersistence) -> None:
        db.save_message("sess-1", "user-A", "group-1", "user", "msg from A")
        db.save_message("sess-2", "user-B", "group-2", "user", "msg from B")
        db.save_message("sess-1", "user-A", "group-1", "assistant", "reply to A")

        msgs = db.get_user_messages("user-A")
        assert len(msgs) == 2
        assert all(m["role"] in ("user", "assistant") for m in msgs)

    def test_get_user_messages_respects_limit(self, db: ChatPersistence) -> None:
        for i in range(10):
            db.save_message(f"sess-{i}", "user-X", None, "user", f"msg{i}")

        msgs = db.get_user_messages("user-X", limit=3)
        assert len(msgs) == 3

    def test_get_user_messages_disabled_returns_empty(self, db_disabled: ChatPersistence) -> None:
        assert db_disabled.get_user_messages("user-1") == []


# ── 清理 ───────────────────────────────────────────────────────────


class TestCleanup:
    def test_cleanup_old_messages(self, db: ChatPersistence) -> None:
        # 写入一条"旧"消息
        old_time = time.time() - 8 * 86400  # 8 天前
        db._conn.execute(
            "INSERT INTO messages (session_id, user_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("sess-1", "user-1", "user", "old message", old_time),
        )
        db._conn.commit()

        # 写入一条新消息
        db.save_message("sess-1", "user-1", None, "user", "new message")

        # 清理 7 天前的消息
        deleted = db.cleanup_old_messages(retention_days=7)
        assert deleted == 1

        msgs = db.get_messages("sess-1")
        assert len(msgs) == 1
        assert msgs[0]["content"] == "new message"

    def test_cleanup_disabled_returns_zero(self, db_disabled: ChatPersistence) -> None:
        assert db_disabled.cleanup_old_messages(7) == 0


# ── 统计 ───────────────────────────────────────────────────────────


class TestStats:
    def test_get_stats(self, db: ChatPersistence) -> None:
        db.save_message("sess-1", "user-1", None, "user", "hello")
        db.save_message("sess-1", "user-1", None, "assistant", "hi")
        db.save_summary("sess-1", "summary")

        stats = db.get_stats()
        assert stats["message_count"] == 2
        assert stats["summary_count"] == 1

    def test_get_stats_disabled(self, db_disabled: ChatPersistence) -> None:
        stats = db_disabled.get_stats()
        assert stats["message_count"] == 0
        assert stats["summary_count"] == 0


# ── MemoryStore 集成 ───────────────────────────────────────────────


class TestMemoryStoreWithPersistence:
    @pytest.mark.asyncio
    async def test_add_user_message_with_meta(self, db: ChatPersistence) -> None:
        ms = MemoryStore(persistence=db)
        await ms.add_user_message_with_meta("sess-1", "user-1", "hello", group_id="group-1")

        # 内存中应有
        history = await ms.get_history("sess-1")
        assert len(history) == 1
        assert history[0]["content"] == "hello"

        # 数据库中应有
        msgs = db.get_messages("sess-1")
        assert len(msgs) == 1
        assert msgs[0]["user_id"] == "user-1"  # type: ignore[typeddict-item]

    @pytest.mark.asyncio
    async def test_add_assistant_message_with_meta(self, db: ChatPersistence) -> None:
        ms = MemoryStore(persistence=db)
        await ms.add_assistant_message_with_meta("sess-1", "user-1", "reply", group_id="group-1")

        msgs = db.get_messages("sess-1")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "assistant"  # type: ignore[typeddict-item]

    @pytest.mark.asyncio
    async def test_add_message_without_persistence_no_error(self) -> None:
        """无持久化时不应抛异常。"""
        ms = MemoryStore(persistence=None)
        await ms.add_user_message_with_meta("sess-1", "user-1", "hello")
        history = await ms.get_history("sess-1")
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_persistence_failure_does_not_block(self) -> None:
        """持久化失败时不应阻断消息写入内存。"""
        # 使用一个会失败的持久化（关闭后写入）
        fd, path = tempfile.mkstemp(suffix=".db", prefix="test_fail_")
        os.close(fd)
        db = ChatPersistence(path)
        db.close()  # 关闭连接，后续写入会失败但不阻断

        ms = MemoryStore(persistence=db)
        await ms.add_user_message_with_meta("sess-1", "user-1", "hello")

        # 内存中应仍有消息
        history = await ms.get_history("sess-1")
        assert len(history) == 1

        try:
            os.unlink(path)
        except OSError:
            pass