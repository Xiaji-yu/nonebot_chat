"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Message formatter — long message splitting and Markdown handling
"""

__author__ = "Xiaji-yu"

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class MessageFormatter:
    """消息格式化器。

    功能：
    - 超长消息分片（按 max_length 拆分，尽量在句子边界断开）
    - Markdown 模式：基础 Markdown 转 OneBot CQ 码
    """

    SPLIT_BOUNDARIES = ["\n\n", "\n", "。", "！", "？", ". ", "! ", "? ", "；", "; "]

    def __init__(self, format_config: Any) -> None:
        self._max_length = format_config.max_length
        self._mode = format_config.mode

    def format(self, text: str) -> list[str]:
        """格式化消息，返回分片列表。

        Args:
            text: 原始回复文本。

        Returns:
            分片后的消息列表，每条不超过 max_length。
        """
        if self._mode == "markdown":
            text = self._convert_markdown(text)

        if len(text) <= self._max_length:
            return [text]

        return self._split(text, self._max_length)

    def _convert_markdown(self, text: str) -> str:
        """基础 Markdown → OneBot 友好格式。

        目前只做简单处理：
        - **bold** → CQ bold
        - *italic* → CQ italic
        - `code` → CQ code
        - ```block``` → CQ 引用
        """
        # 代码块 → 引用
        text = re.sub(
            r"```(\w*)\n([\s\S]*?)```",
            lambda m: f"[CQ:quote,text={self._cq_escape(m.group(2).strip())}]",
            text,
        )
        # 行内代码
        text = re.sub(
            r"`([^`]+)`",
            lambda m: f"[CQ:code,{self._cq_escape(m.group(1))}]",
            text,
        )
        # 加粗
        text = re.sub(
            r"\*\*([^*]+)\*\*",
            lambda m: f"[CQ:b,{self._cq_escape(m.group(1))}]",
            text,
        )
        # 斜体
        text = re.sub(
            r"\*([^*]+)\*",
            lambda m: f"[CQ:i,{self._cq_escape(m.group(1))}]",
            text,
        )
        return text

    @staticmethod
    def _cq_escape(text: str) -> str:
        """转义 CQ Code 参数中的特殊字符。

        OneBot CQ 参数以逗号分隔、方括号包裹，
        用户内容中的 \, ] , 会导致参数逃逸。
        """
        text = text.replace("\\", "\\\\")
        text = text.replace(",", "\\,")
        text = text.replace("]", "\\]")
        return text

    def _split(self, text: str, max_len: int) -> list[str]:
        """在边界处拆分文本。"""
        if max_len <= 0:
            return [text]

        parts: list[str] = []
        remaining = text

        while len(remaining) > max_len:
            # 尝试找最佳拆分点
            split_at = max_len
            for boundary in self.SPLIT_BOUNDARIES:
                idx = remaining.rfind(boundary, 0, max_len)
                if idx > 0:
                    split_at = idx + len(boundary)
                    break

            parts.append(remaining[:split_at].rstrip(" \t"))
            remaining = remaining[split_at:].lstrip()

        if remaining:
            parts.append(remaining)
        return parts
