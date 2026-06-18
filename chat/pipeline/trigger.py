"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Trigger detection — mention / keyword / spectator modes
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

logger = logging.getLogger(__name__)

# 常量
SEG_TYPE_AT = "at"
SEG_DATA_QQ = "qq"


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

    VALID_MODES = frozenset({MODE_MENTION, MODE_KEYWORD, MODE_SPECTATOR})

    def __init__(self, trigger_config: Any) -> None:
        self._mode = trigger_config.mode
        if self._mode not in self.VALID_MODES:
            raise ValueError(
                f"Invalid trigger mode: {self._mode!r}. "
                f"Must be one of: {', '.join(sorted(self.VALID_MODES))}"
            )
        self._keywords: list[str] = [kw.lower() for kw in trigger_config.keywords]

        if self._mode == self.MODE_KEYWORD and not self._keywords:
            raise ValueError("keyword trigger mode requires at least one keyword")

    @property
    def mode(self) -> str:
        """当前触发模式。"""
        return self._mode

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
            raw = event.get_plaintext()
            text = (raw or "").lower()
            for kw in self._keywords:
                if kw in text:
                    return True, f"keyword:{kw}"
            return False, ""

        # 不应到达（__init__ 已校验）
        logger.error("Unknown trigger mode: %s", self._mode)
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
        bot_qq = str(getattr(event, "self_id", ""))
        if not bot_qq:
            return False
        for seg in message:
            seg_type = getattr(seg, "type", "")
            if seg_type == SEG_TYPE_AT:
                data = getattr(seg, "data", None)
                if isinstance(data, dict):
                    target_qq = data.get(SEG_DATA_QQ, "")
                    if str(target_qq) == bot_qq:
                        return True
        return False
