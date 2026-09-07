"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Trigger detection — mention / keyword / mention_keyword / spectator / disabled
"""

__author__ = "Xiaji-yu"

from typing import Any

# 常量
SEG_TYPE_AT = "at"
SEG_DATA_QQ = "qq"


class TriggerDetector:
    """触发检测器（群聊触发规则，私聊不经此检测）。

    支持五种模式：
    - mention:          仅 @机器人 触发
    - keyword:          消息命中关键词触发
    - mention_keyword:  @机器人 或 命中关键词，任一即触发
    - spectator:        所有消息都视为"触发"
    - disabled:         不触发（群聊不回复，私聊仍直接处理）
    """

    MODE_MENTION = "mention"
    MODE_KEYWORD = "keyword"
    MODE_MENTION_KEYWORD = "mention_keyword"
    MODE_SPECTATOR = "spectator"
    MODE_DISABLED = "disabled"

    VALID_MODES = frozenset({
        MODE_MENTION,
        MODE_KEYWORD,
        MODE_MENTION_KEYWORD,
        MODE_SPECTATOR,
        MODE_DISABLED,
    })

    def __init__(self, trigger_config: Any) -> None:
        self._mode = trigger_config.mode
        if self._mode not in self.VALID_MODES:
            raise ValueError(
                f"Invalid trigger mode: {self._mode!r}. "
                f"Must be one of: {', '.join(sorted(self.VALID_MODES))}"
            )
        self._keywords: list[str] = [kw.lower() for kw in trigger_config.keywords]

        keyword_based = {self.MODE_KEYWORD, self.MODE_MENTION_KEYWORD}
        if self._mode in keyword_based and not self._keywords:
            raise ValueError(
                f"{self._mode} trigger mode requires at least one keyword"
            )

    @property
    def mode(self) -> str:
        """当前触发模式。"""
        return self._mode

    def enabled(self) -> bool:
        """是否启用触发（disabled 返回 False）。"""
        return self._mode != self.MODE_DISABLED

    def detect(self, event: Any) -> tuple[bool, str]:
        """检测消息是否满足触发条件。

        Args:
            event: NoneBot MessageEvent。

        Returns:
            (triggered, trigger_type) — 是否触发及触发类型。
        """
        if self._mode == self.MODE_DISABLED:
            return False, ""

        if self._mode == self.MODE_SPECTATOR:
            return True, "spectator"

        mentioned = self._is_mentioned(event)

        if self._mode == self.MODE_MENTION:
            if mentioned:
                return True, "mention"
            return False, ""

        # keyword / mention_keyword
        raw = event.get_plaintext()
        text = (raw or "").lower()
        hit = next((kw for kw in self._keywords if kw in text), None)

        if self._mode == self.MODE_MENTION_KEYWORD:
            if mentioned:
                return True, "mention"
            if hit:
                return True, f"keyword:{hit}"
            return False, ""

        # MODE_KEYWORD
        if hit:
            return True, f"keyword:{hit}"
        return False, ""

    def is_mention(self, event: Any) -> bool:
        """检查是否为 @mention 事件。"""
        return self._is_mentioned(event)

    @staticmethod
    def _is_mentioned(event: Any) -> bool:
        """检查消息是否 @了机器人。

        优先使用 NoneBot 内置的 is_tome()，回退到手动 CQ 段解析。
        """
        # NoneBot 内置方法（v11 adapter 支持）
        if hasattr(event, "is_tome"):
            try:
                return event.is_tome()  # type: ignore[no-any-return]
            except Exception:
                pass

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
