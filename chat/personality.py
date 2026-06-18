"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Personality system — loads and exposes persona config
"""

__author__ = "Xiaji-yu"

import logging
from pathlib import Path
from typing import Any

import yaml

from .config import ChatConfig

logger = logging.getLogger(__name__)


class Personality:
    """人格配置管理器。

    从 chat_config.yaml 加载人格、LLM、温度和记忆相关配置，
    对外提供统一的访问接口。
    """

    def __init__(self, config: ChatConfig) -> None:
        self._config = config
        self._raw: dict[str, Any] = {}
        self._personality_cfg: dict[str, Any] = {}
        self._llm_cfg: dict[str, Any] = {}
        self._temp_cfg: dict[str, Any] = {}
        self._memory_cfg: dict[str, Any] = {}
        self._proactive_cfg: dict[str, Any] = {}
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        path = Path(self._config.config_path)
        if not path.is_file():
            logger.warning("Chat config file not found: %s, using defaults", path)
            return
        try:
            self._raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.error("Failed to load chat config from %s: %s", path, exc)
            self._raw = {}

        self._personality_cfg = self._raw.get("personality", {})
        self._llm_cfg = self._raw.get("llm", {})
        self._temp_cfg = self._raw.get("temperature", {})
        self._memory_cfg = self._raw.get("memory", {})
        self._proactive_cfg = self._raw.get("proactive", {})

    # ------------------------------------------------------------------
    # Personality
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """人格名称。"""
        return self._personality_cfg.get("name", "小助手")

    @property
    def system_prompt(self) -> str:
        """系统提示词。"""
        return self._personality_cfg.get(
            "system_prompt",
            "你是一个友善的助手。",
        )

    @property
    def wake_words(self) -> list[str]:
        """唤醒词列表（小写）。"""
        return [w.lower() for w in self._personality_cfg.get("wake_words", [])]

    def is_wake_word(self, text: str) -> bool:
        """检查消息是否命中任何唤醒词。"""
        lower = text.lower()
        return any(word in lower for word in self.wake_words)

    def build_system_message(self) -> dict[str, str]:
        """构建系统消息（OpenAI Chat 格式）。"""
        return {
            "role": "system",
            "content": self.system_prompt,
        }

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    @property
    def llm_base_url(self) -> str:
        return self._llm_cfg.get("base_url", "http://localhost:11434/v1")

    @property
    def llm_model(self) -> str:
        return self._llm_cfg.get("model", "llama2")

    @property
    def llm_api_key(self) -> str:
        return self._llm_cfg.get("api_key", "")

    @property
    def llm_max_tokens(self) -> int:
        return int(self._llm_cfg.get("max_tokens", 1000))

    @property
    def llm_timeout(self) -> int:
        return int(self._llm_cfg.get("timeout", 30))

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    def get_temperature(self, proactive: bool = False) -> float:
        """获取温度值。

        Args:
            proactive: 是否为主动回复场景。
        """
        if proactive:
            lo = float(self._temp_cfg.get("proactive_min", 0.5))
            hi = float(self._temp_cfg.get("proactive_max", 1.0))
            return max(lo, min(hi, (lo + hi) / 2))
        return float(self._temp_cfg.get("default", 0.7))

    @property
    def temperature_default(self) -> float:
        return float(self._temp_cfg.get("default", 0.7))

    @property
    def temperature_proactive_min(self) -> float:
        return float(self._temp_cfg.get("proactive_min", 0.5))

    @property
    def temperature_proactive_max(self) -> float:
        return float(self._temp_cfg.get("proactive_max", 1.0))

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    @property
    def memory_max_history(self) -> int:
        return int(self._memory_cfg.get("max_history", 50))

    @property
    def memory_distillation_threshold(self) -> int:
        return int(self._memory_cfg.get("distillation_threshold", 40))

    @property
    def memory_core_memory_max(self) -> int:
        return int(self._memory_cfg.get("core_memory_max", 10))

    # ------------------------------------------------------------------
    # Proactive
    # ------------------------------------------------------------------

    @property
    def proactive_enabled(self) -> bool:
        return bool(self._proactive_cfg.get("enabled", True))

    @property
    def proactive_probability(self) -> float:
        return float(self._proactive_cfg.get("probability", 0.1))

    @property
    def proactive_cooldown(self) -> int:
        return int(self._proactive_cfg.get("cooldown", 300))

    @property
    def proactive_check_interval(self) -> int:
        return int(self._proactive_cfg.get("check_interval", 60))
