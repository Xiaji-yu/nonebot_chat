"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Sleep mode controller
"""

__author__ = "Xiaji-yu"

import asyncio
import logging
from datetime import datetime, time
from typing import Any

logger = logging.getLogger(__name__)


class SleepController:
    """休眠模式控制器。

    支持两种模式：
    - schedule: 固定时间段休眠
    - manual: 手动开关（通过管理命令 /sleep /wake）

    休眠期间行为：
    - @mention → 正常响应（override_by_mention=true 时）
    - 其他触发 → 全部静默（drop）
    """

    def __init__(self, sleep_config: Any) -> None:
        self._cfg = sleep_config
        self._manual_sleeping: bool = False
        self._lock = asyncio.Lock()

    def is_sleeping(self) -> bool:
        """检查当前是否处于休眠状态。"""
        try:
            if not self._cfg.enabled:
                return False
            if self._cfg.mode == "manual":
                return self._manual_sleeping
            if self._cfg.mode == "schedule":
                return self._is_in_schedule()
            logger.warning("Unknown sleep mode: %s", self._cfg.mode)
            return False
        except AttributeError as exc:
            logger.warning("Sleep config missing attributes: %s", exc)
            return False

    def is_override_allowed(self) -> bool:
        """休眠期间 @mention 是否允许唤醒。"""
        try:
            return bool(self._cfg.override_by_mention)
        except AttributeError:
            return True  # 安全默认值

    async def toggle(self) -> bool:
        """切换休眠状态（manual 模式，线程安全）。

        Returns:
            切换后的休眠状态。
        """
        async with self._lock:
            self._manual_sleeping = not self._manual_sleeping
            logger.info("Sleep mode toggled: %s", self._manual_sleeping)
            return self._manual_sleeping

    async def force_wake(self) -> None:
        """强制唤醒（取消休眠，线程安全）。"""
        async with self._lock:
            self._manual_sleeping = False
            logger.info("Sleep mode force-woken")

    # ------------------------------------------------------------------

    def _is_in_schedule(self) -> bool:
        """检查当前时间是否在休眠时间段内。"""
        try:
            now = datetime.now().time()
            start = time.fromisoformat(self._cfg.schedule.start)
            end = time.fromisoformat(self._cfg.schedule.end)
        except (ValueError, AttributeError) as exc:
            logger.warning("Invalid sleep schedule config: %s", exc)
            return False

        if start == end:
            logger.warning(
                "Sleep schedule start equals end (%s), schedule disabled", start
            )
            return False

        if start <= end:
            return start <= now <= end
        # 跨天（如 23:00 - 08:00）
        return now >= start or now <= end
