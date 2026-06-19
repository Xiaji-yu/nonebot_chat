"""
@Author         : Xiaji-yu
@Date           : 2026-06-19
@Description    : Chat persistence layer — SQLite storage for messages and summaries
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────

DEFAULT_DB_NAME = "chat_history.db"
DEFAULT_RETENTION_DAYS = 7
CLEANUP_INTERVAL_SECONDS = 86400  # 24 小时

# 数据库 DDL
_DDL = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    group_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_msg_session_time ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_user_time ON messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_sum_session ON summaries(session_id);
"""


class ChatPersistence:
    """聊天记录持久化层。

    使用 SQLite 存储原始消息和蒸馏摘要，支持按会话/用户/时间查询。
    所有数据库操作在同步方法中完成，由调用方在异步上下文中通过
    asyncio.to_thread 或直接调用（sqlite3 本身线程安全）。

    设计原则：
    - 旁路写入：失败时记录日志，不阻断主流程
    - 零外部依赖：使用 Python 标准库 sqlite3
    - WAL 模式：支持并发读写
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """初始化持久化层。

        Args:
            db_path: SQLite 数据库文件路径。None 或空字符串表示禁用持久化。
        """
        self._db_path: str | None = None
        self._conn: sqlite3.Connection | None = None

        if db_path:
            self._db_path = str(Path(db_path).resolve())
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_DDL)
            self._conn.commit()
            logger.info("Chat persistence initialized: %s", self._db_path)

    @property
    def enabled(self) -> bool:
        """是否已启用持久化。"""
        return self._conn is not None

    # ------------------------------------------------------------------
    # 消息写入
    # ------------------------------------------------------------------

    def save_message(
        self,
        session_id: str,
        user_id: str,
        group_id: str | None,
        role: str,
        content: str,
    ) -> None:
        """保存一条消息到数据库。

        Args:
            session_id: 会话唯一标识。
            user_id: 用户 ID。
            group_id: 群 ID，私聊时为 None。
            role: 角色（user / assistant）。
            content: 消息内容。
        """
        if not self.enabled:
            return
        try:
            self._conn.execute(
                "INSERT INTO messages (session_id, user_id, group_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, user_id, group_id, role, content, time.time()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("Failed to persist message (session=%s): %s", session_id, exc)

    # ------------------------------------------------------------------
    # 摘要写入
    # ------------------------------------------------------------------

    def save_summary(self, session_id: str, content: str) -> None:
        """保存一条蒸馏摘要（永久保留）。

        Args:
            session_id: 会话唯一标识。
            content: 摘要内容。
        """
        if not self.enabled:
            return
        try:
            self._conn.execute(
                "INSERT INTO summaries (session_id, content, created_at) VALUES (?, ?, ?)",
                (session_id, content, time.time()),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("Failed to persist summary (session=%s): %s", session_id, exc)

    def save_summaries(self, session_id: str, summaries: list[str]) -> None:
        """批量保存蒸馏摘要。

        Args:
            session_id: 会话唯一标识。
            summaries: 摘要列表。
        """
        if not self.enabled or not summaries:
            return
        try:
            now = time.time()
            rows = [(session_id, s, now) for s in summaries]
            self._conn.executemany(
                "INSERT INTO summaries (session_id, content, created_at) VALUES (?, ?, ?)",
                rows,
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            logger.warning("Failed to persist summaries (session=%s): %s", session_id, exc)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_summaries(self, session_id: str) -> list[str]:
        """获取指定会话的所有摘要。

        Args:
            session_id: 会话唯一标识。

        Returns:
            摘要内容列表。
        """
        if not self.enabled:
            return []
        try:
            rows = self._conn.execute(
                "SELECT content FROM summaries WHERE session_id = ? ORDER BY created_at",
                (session_id,),
            ).fetchall()
            return [row[0] for row in rows]
        except sqlite3.Error as exc:
            logger.warning("Failed to get summaries (session=%s): %s", session_id, exc)
            return []

    def get_messages(
        self,
        session_id: str,
        since_days: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询指定会话的消息。

        Args:
            session_id: 会话唯一标识。
            since_days: 最近 N 天的消息，None 表示不限。
            limit: 最多返回条数。

        Returns:
            消息字典列表，含 role/content/created_at。
        """
        if not self.enabled:
            return []
        try:
            if since_days is not None:
                cutoff = time.time() - since_days * 86400
                rows = self._conn.execute(
                    "SELECT role, content, created_at, session_id, user_id, group_id FROM messages "
                    "WHERE session_id = ? AND created_at >= ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (session_id, cutoff, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT role, content, created_at, session_id, user_id, group_id FROM messages "
                    "WHERE session_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            return [
                {
                    "role": row[0],
                    "content": row[1],
                    "created_at": row[2],
                    "session_id": row[3],
                    "user_id": row[4],
                    "group_id": row[5],
                }
                for row in reversed(rows)  # 按时间升序返回
            ]
        except sqlite3.Error as exc:
            logger.warning("Failed to get messages (session=%s): %s", session_id, exc)
            return []

    def get_user_messages(
        self,
        user_id: str,
        since_days: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """查询指定用户在所有会话中的消息。

        Args:
            user_id: 用户 ID。
            since_days: 最近 N 天的消息。
            limit: 最多返回条数。

        Returns:
            消息字典列表。
        """
        if not self.enabled:
            return []
        try:
            if since_days is not None:
                cutoff = time.time() - since_days * 86400
                rows = self._conn.execute(
                    "SELECT session_id, role, content, created_at FROM messages "
                    "WHERE user_id = ? AND created_at >= ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, cutoff, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT session_id, role, content, created_at FROM messages "
                    "WHERE user_id = ? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (user_id, limit),
                ).fetchall()
            return [
                {"session_id": row[0], "role": row[1], "content": row[2], "created_at": row[3]}
                for row in reversed(rows)
            ]
        except sqlite3.Error as exc:
            logger.warning("Failed to get user messages (user=%s): %s", user_id, exc)
            return []

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def cleanup_old_messages(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
        """删除超过保留期限的原始消息。

        Args:
            retention_days: 保留天数。

        Returns:
            删除的记录数。
        """
        if not self.enabled:
            return 0
        try:
            cutoff = time.time() - retention_days * 86400
            cursor = self._conn.execute(
                "DELETE FROM messages WHERE created_at < ?", (cutoff,)
            )
            self._conn.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(
                "Cleaned up %d old messages (retention=%d days)", deleted, retention_days
            )
            return deleted
        except sqlite3.Error as exc:
            logger.warning("Failed to cleanup old messages: %s", exc)
            return 0

    def get_stats(self) -> dict[str, int]:
        """获取存储统计信息。

        Returns:
            包含 message_count 和 summary_count 的字典。
        """
        if not self.enabled:
            return {"message_count": 0, "summary_count": 0}
        try:
            msg_count = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            sum_count = self._conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
            return {"message_count": msg_count, "summary_count": sum_count}
        except sqlite3.Error:
            return {"message_count": 0, "summary_count": 0}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Chat persistence closed: %s", self._db_path)
            except sqlite3.Error as exc:
                logger.warning("Failed to close persistence: %s", exc)
            self._conn = None