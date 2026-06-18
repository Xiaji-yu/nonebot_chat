"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Trigger detection — mention / keyword / spectator modes
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TriggerDetector:
    """触发检测器。

    支持三种模式：
    - mention: 必须 @机器人 才触发
    - keyword: 消息命中关键词才触发
    - spectator: 旁观模式，所有消息都视为"触发"
    """

    MODE_MENTION = "mention"
    MODE_KEYWORD = "keyword"
    MODE_SPECTATOR = "spectator"

    def __init__(self, trigger_config: Any) -> None:
        self._mode = trigger_config.mode
        self._keywords: list[str] = [kw.lower() for kw in trigger_config.keywords]

    def detect(self, event: Any) -> tuple[bool, str]:
        """检测消息是否满足触发条件。

        Args:
            event: NoneBot MessageEvent。

        Returns:
            (triggered, trigger_type) — 是否触发及触发类型。
        """
        if self._mode == self.MODE_SPECTATOR:
            return True, "spectator"

        if self._mode == self.MODE_MENTION:
            if self._is_mentioned(event):
                return True, "mention"
            return False, ""

        if self._mode == self.MODE_KEYWORD:
            text = event.get_plaintext().lower()
            for kw in self._keywords:
                if kw in text:
                    return True, f"keyword:{kw}"
            return False, ""

        logger.warning("Unknown trigger mode: %s", self._mode)
        return False, ""

    def is_mention(self, event: Any) -> bool:
        """检查是否为 @mention 事件。"""
        return self._is_mentioned(event)

    @staticmethod
    def _is_mentioned(event: Any) -> bool:
        """检查消息是否 @了机器人。"""
        message = getattr(event, "message", None)
        if message is None:
            return False
        for seg in message:
            seg_type = getattr(seg, "type", "")
            if seg_type == "at":
                # OneBot v11: at 段的 data 中有 qq 字段
                data = getattr(seg, "data", {})
                bot_qq = getattr(event, "self_id", None)
                target_qq = data.get("qq", "")
                if str(target_qq) == str(bot_qq):
                    return True
        return False
