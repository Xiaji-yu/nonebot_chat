"""
@Author         : Xiaji-yu
@Date           : 2026-09-07
@Description    : 统一日志器 — NoneBot 环境用 loguru，独立/测试环境回退标准 logging

NoneBot 只桥接自己模块的日志到 loguru；插件若用标准 logging，
Python lastResort 只放行 WARNING+，导致 INFO 日志（如 LLM 耗时、
回复来源）在 LOG_LEVEL=INFO 下不可见。此处统一处理。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger

try:  # NoneBot 运行时：日志经 loguru（跟随 LOG_LEVEL，INFO 可见）
    from nonebot.log import logger as _nb_logger

    logger: Logger = _nb_logger
except ImportError:  # 独立运行 / 测试：回退标准 logging
    logger = logging.getLogger("chat")  # type: ignore[assignment]

__all__ = ["logger"]
