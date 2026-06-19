"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Content deduplication — hash-based dedup within time window
"""

__author__ = "Xiaji-yu"

import asyncio
import hashlib
import logging
import time

logger = logging.getLogger(__name__)

# 存储结构: {(session_id, content_hash): timestamp}
_dedup_store: dict[tuple[str, str], float] = {}
_dedup_lock = asyncio.Lock()


async def reset() -> None:
    """清空去重缓存（测试/重启时调用）。"""
    async with _dedup_lock:
        _dedup_store.clear()


async def check(session_id: str, content: str, window: float = 5.0) -> bool:
    """检查内容是否在时间窗口内重复。

    Args:
        session_id: 会话唯一标识。
        content: 消息内容。
        window: 时间窗口（秒）。

    Returns:
        True 表示是重复内容，应跳过。
    """
    key = _session_key(session_id, content)
    now = time.time()

    async with _dedup_lock:
        # 清理过期条目
        _purge_expired(now)

        last = _dedup_store.get(key)
        if last is not None and (now - last) < window:
            logger.debug("Dedup hit: session=%s, age=%.1fs", session_id, now - last)
            return True

        _dedup_store[key] = now
        return False


def _session_key(session_id: str, content: str) -> tuple[str, str]:
    """生成去重键：会话 ID + 内容 MD5。"""
    digest = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
    return (session_id, digest)


def _purge_expired(now: float, max_age: float = 300.0) -> None:
    """清理超过 max_age 秒的过期条目（必须在锁内调用）。"""
    expired = [k for k, t in _dedup_store.items() if now - t > max_age]
    for k in expired:
        del _dedup_store[k]
