"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : 日志脱敏工具 — 避免 QQ 号/用户 ID 明文入日志

会话标识形如 ``g123456789_u987654321``，群 ID 亦为用户可辨识的 QQ 号。
输出到日志时统一掩码，只保留末 3 位，前缀按 g/u 保留。
"""

from __future__ import annotations

import re

# 匹配 g<数字>_u<数字> 会话 ID 或裸数字 QQ 号（>=5 位视为敏感）。
# 数字段后可能是 _（继续会话 ID）或单词边界（独立 ID）。
_SESSION_ID_RE = re.compile(r"(?<![A-Za-z0-9])([gu])(\d{5,})(?![0-9])")
_RAW_QQ_RE = re.compile(r"(?<![0-9])(\d{5,})(?![0-9])")


def mask_session(session_id: str) -> str:
    """将会话 ID 中的 QQ/群号掩码（保留 g/u 前缀与首末位）。

    Args:
        session_id: 形如 g123_u456 / u789 / g1_u2 的会话标识。

    Returns:
        掩码后的字符串，如 g1***789_u9***321；短 ID 原样返回。
    """

    def _mask(match: re.Match[str]) -> str:
        prefix, num = match.group(1), match.group(2)
        if len(num) <= 3:
            return match.group(0)
        return f"{prefix}{num[:1]}***{num[-3:]}"

    return _SESSION_ID_RE.sub(_mask, session_id)


def mask_id(text: str) -> str:
    """将文本中的裸数字 ID（QQ 号等）掩码。

    Args:
        text: 任意含数字 ID 的日志文本。

    Returns:
        掩码后的文本；短数字（<5 位）不做处理。
    """

    def _mask(match: re.Match[str]) -> str:
        num = match.group(1)
        return f"{num[:1]}***{num[-3:]}"

    return _RAW_QQ_RE.sub(_mask, text)


def mask_user(user_id: str) -> str:
    """掩码单个用户/群 ID。"""
    if len(user_id) <= 3:
        return user_id
    return f"{user_id[:1]}***{user_id[-3:]}"
