"""
@Author         : Xiaji-yu
@Date           : 2026-09-08
@Description    : 消息描述 — 在纯文本之外标注图片/引用/语音等非文本段

QQ 的 ``get_plaintext()`` 只返回文本段；图片、回复引用、表情、语音
等会静默丢失，导致机器人对"只有一张图"的消息收到空输入。本模块把
非文本段转成占位标注（如 ``[图片]``），使模型至少感知到它们的
存在，能正确回应而不是凭空发挥。
"""

from __future__ import annotations

from typing import Any

# 段类型 → 标注
SEG_LABELS: dict[str, str] = {
    "image": "[图片]",
    "face": "[表情]",
    "record": "[语音]",
    "video": "[视频]",
    "reply": "[引用消息]",
    "forward": "[聊天记录]",
    "json": "[卡片消息]",
}


def _seg_type(seg: Any) -> str | None:
    """取消息段的 type（兼容 OneBot segment 对象与 dict）。"""
    if hasattr(seg, "type"):
        return seg.type
    if isinstance(seg, dict):
        return seg.get("type")
    return None


def _iter_segments(event: Any) -> list[Any]:
    """取事件携带的消息段列表（兼容 dict 与对象列表）。"""
    message = getattr(event, "message", None)
    if message is None:
        return []
    return list(message)


def describe(event: Any) -> str:
    """构造发送给 LLM 的消息描述文本。

    纯文本（经 get_plaintext）在前，媒体标注按出现顺序追加，
    去重相邻同类标注避免重复刷屏。

    Args:
        event: NoneBot MessageEvent。

    Returns:
        描述文本，如 ``"看看这张图 [图片]"`` 或仅 ``"[图片]"``。
    """
    plain = (event.get_plaintext() or "").strip()
    labels: list[str] = []
    for seg in _iter_segments(event):
        stype = _seg_type(seg)
        label = SEG_LABELS.get(stype or "")
        if label and (not labels or labels[-1] != label):
            labels.append(label)

    if not plain and not labels:
        return ""
    if not labels:
        return plain
    if not plain:
        return " ".join(labels)
    return f"{plain} {' '.join(labels)}"
