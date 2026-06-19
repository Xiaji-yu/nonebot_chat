"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Personality system — loads and exposes persona config
"""

__author__ = "Xiaji-yu"

import logging
import os
from pathlib import Path

import yaml
from pydantic import ValidationError

from .config import ChatConfig, ChatYamlConfig, PersistenceConfig, PipelineConfig

logger = logging.getLogger(__name__)


class Personality:
    """人格配置管理器。

    从 chat_config.yaml 加载全部配置，通过 ChatYamlConfig 一次性
    Pydantic 验证，各属性直接委托给已验证的模型字段。
    """

    def __init__(self, config: ChatConfig) -> None:
        self._config = config
        self._yaml: ChatYamlConfig = ChatYamlConfig()
        self._load()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """加载并验证 YAML 配置文件。"""
        path = Path(self._config.config_path)
        if not path.is_file():
            logger.warning("Chat config file not found: %s, using defaults", path)
            return
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.error("Failed to load chat config from %s: %s", path, exc)
            return
        try:
            self._yaml = ChatYamlConfig(**raw)
        except ValidationError as exc:
            logger.warning("Invalid chat config, using defaults: %s", exc)

    # ------------------------------------------------------------------
    # Personality
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """人格名称。"""
        return self._yaml.personality.name

    @property
    def system_prompt(self) -> str:
        """系统提示词。"""
        return self._yaml.personality.system_prompt

    @property
    def wake_words(self) -> list[str]:
        """唤醒词列表（小写）。"""
        return [w.lower() for w in self._yaml.personality.wake_words]

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
        return self._yaml.llm.base_url

    @property
    def llm_model(self) -> str:
        return self._yaml.llm.model

    @property
    def llm_api_key(self) -> str:
        """API Key。优先从环境变量读取，回退到配置文件。"""
        return (
            os.environ.get("OPENAI_API_KEY", "")
            or os.environ.get("LLM_API_KEY", "")
            or self._yaml.llm.api_key
        )

    @property
    def llm_max_tokens(self) -> int:
        return self._yaml.llm.max_tokens

    @property
    def llm_timeout(self) -> int:
        return self._yaml.llm.timeout

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------

    def get_temperature(self, proactive: bool = False) -> float:
        """获取温度值。

        Args:
            proactive: 是否为主动回复场景。
        """
        if proactive:
            lo = self._yaml.temperature.proactive_min
            hi = self._yaml.temperature.proactive_max
            return max(lo, min(hi, (lo + hi) / 2))
        return self._yaml.temperature.default

    @property
    def temperature_default(self) -> float:
        return self._yaml.temperature.default

    @property
    def temperature_proactive_min(self) -> float:
        return self._yaml.temperature.proactive_min

    @property
    def temperature_proactive_max(self) -> float:
        return self._yaml.temperature.proactive_max

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    @property
    def memory_max_history(self) -> int:
        return self._yaml.memory.max_history

    @property
    def memory_distillation_threshold(self) -> int:
        return self._yaml.memory.distillation_threshold

    @property
    def memory_core_memory_max(self) -> int:
        return self._yaml.memory.core_memory_max

    # ------------------------------------------------------------------
    # Proactive
    # ------------------------------------------------------------------

    @property
    def proactive_enabled(self) -> bool:
        return self._yaml.proactive.enabled

    @property
    def proactive_probability(self) -> float:
        return self._yaml.proactive.probability

    @property
    def proactive_cooldown(self) -> int:
        return self._yaml.proactive.cooldown

    @property
    def proactive_check_interval(self) -> int:
        return self._yaml.proactive.check_interval

    # ------------------------------------------------------------------
    # Pipeline config
    # ------------------------------------------------------------------

    @property
    def pipeline_config(self) -> PipelineConfig:
        """Pipeline 配置（从 YAML 加载，一次性验证）。"""
        return self._yaml.pipeline

    @property
    def persistence_config(self) -> PersistenceConfig:
        """持久化配置（从 YAML 加载，一次性验证）。"""
        return self._yaml.persistence