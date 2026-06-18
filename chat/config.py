"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Chat plugin configuration (Pydantic Config for NoneBot)
"""

__author__ = "Xiaji-yu"

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ── 常量 ──────────────────────────────────────────────────────────
DEFAULT_PERSONA_NAME = "小助手"
DEFAULT_SYSTEM_PROMPT = (
    "你是一个友善、聪明的助手，名叫小助手。"
    "请用简洁、自然的语气回复，避免过于正式或机械的表达。"
    "适当使用 emoji，但不要过度。记住和用户的历史对话上下文。"
)
DEFAULT_LLM_BASE_URL = "http://localhost:11434/v1"
DEFAULT_LLM_MODEL = "llama2"
DEFAULT_LLM_MAX_TOKENS = 1000
DEFAULT_LLM_TIMEOUT = 30
DEFAULT_TEMP = 0.7
DEFAULT_TEMP_PROACTIVE_MIN = 0.5
DEFAULT_TEMP_PROACTIVE_MAX = 1.0
DEFAULT_MAX_HISTORY = 50
DEFAULT_DISTILL_THRESHOLD = 40
DEFAULT_CORE_MEMORY_MAX = 10
DEFAULT_PROACTIVE_PROBABILITY = 0.1
DEFAULT_PROACTIVE_COOLDOWN = 300
DEFAULT_PROACTIVE_INTERVAL = 60
DEFAULT_DEDUP_WINDOW = 5
DEFAULT_RL_PER_SESSION = 3
DEFAULT_RL_WINDOW = 10
DEFAULT_DEBOUNCE_WINDOW = 3
DEFAULT_FORMAT_MAX_LENGTH = 500
DEFAULT_SLEEP_START = "23:00"
DEFAULT_SLEEP_END = "08:00"

# HH:MM 格式校验
_TIME_PATTERN = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


class PersonalityConfig(BaseModel):
    """人格配置。"""

    name: str = Field(default=DEFAULT_PERSONA_NAME)
    """人格名称。"""

    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT)
    """系统提示词（System Prompt），定义 AI 的人格和行为准则。"""

    wake_words: list[str] = Field(default=["小助手", "bot"])
    """唤醒词列表。仅当消息命中唤醒词时才触发回复（主动回复除外）。"""


class LLMConfig(BaseModel):
    """LLM 客户端配置。"""

    base_url: str = Field(default=DEFAULT_LLM_BASE_URL)
    """OpenAI 兼容 API 的基础 URL。"""

    model: str = Field(default=DEFAULT_LLM_MODEL)
    """模型名称。"""

    api_key: str = Field(default="")
    """API Key。空字符串表示无需认证。"""

    max_tokens: int = Field(default=DEFAULT_LLM_MAX_TOKENS, ge=1, le=8192)
    """单次生成的最大 token 数。"""

    timeout: int = Field(default=DEFAULT_LLM_TIMEOUT, ge=5, le=120)
    """API 请求超时时间（秒）。"""


class TemperatureConfig(BaseModel):
    """温度配置，控制回复的创造性。"""

    default: float = Field(default=DEFAULT_TEMP, ge=0.0, le=2.0)
    """普通回复温度。"""

    proactive_min: float = Field(default=DEFAULT_TEMP_PROACTIVE_MIN, ge=0.0, le=2.0)
    """主动回复温度下限。"""

    proactive_max: float = Field(default=DEFAULT_TEMP_PROACTIVE_MAX, ge=0.0, le=2.0)
    """主动回复温度上限。"""

    @model_validator(mode="after")
    def _check_range(self) -> "TemperatureConfig":
        if self.proactive_min > self.proactive_max:
            raise ValueError(
                f"proactive_min ({self.proactive_min}) must be <= "
                f"proactive_max ({self.proactive_max})"
            )
        return self


class MemoryConfig(BaseModel):
    """记忆系统配置。"""

    max_history: int = Field(default=DEFAULT_MAX_HISTORY, ge=5, le=500)
    """单会话最大消息条数。超过后触发蒸馏。"""

    distillation_threshold: int = Field(default=DEFAULT_DISTILL_THRESHOLD, ge=10, le=200)
    """对话消息数达到此阈值时触发记忆蒸馏。"""

    core_memory_max: int = Field(default=DEFAULT_CORE_MEMORY_MAX, ge=1, le=50)
    """蒸馏后保留的核心记忆条数。"""

    @model_validator(mode="after")
    def _check_threshold(self) -> "MemoryConfig":
        if self.distillation_threshold >= self.max_history:
            raise ValueError(
                f"distillation_threshold ({self.distillation_threshold}) must be "
                f"< max_history ({self.max_history})"
            )
        if self.core_memory_max > self.max_history:
            raise ValueError(
                f"core_memory_max ({self.core_memory_max}) must be "
                f"<= max_history ({self.max_history})"
            )
        return self


class ProactiveConfig(BaseModel):
    """主动回复配置。"""

    enabled: bool = True
    """是否启用主动回复。"""

    probability: float = Field(default=DEFAULT_PROACTIVE_PROBABILITY, ge=0.0, le=1.0)
    """每条非唤醒词消息的主动回复概率。"""

    cooldown: int = Field(default=DEFAULT_PROACTIVE_COOLDOWN, ge=30, le=3600)
    """主动回复冷却时间（秒）。"""

    check_interval: int = Field(default=DEFAULT_PROACTIVE_INTERVAL, ge=10, le=600)
    """主动回复检查间隔（秒）。"""


# ── Pipeline 配置 ──────────────────────────────────────────────────

class DedupConfig(BaseModel):
    """去重配置。"""

    enabled: bool = True
    """是否启用去重。"""

    window: int = Field(default=DEFAULT_DEDUP_WINDOW, ge=1, le=60)
    """时间窗口（秒），相同内容在此窗口内忽略。"""


class AccessConfig(BaseModel):
    """黑白名单配置。"""

    mode: Literal["whitelist", "blacklist", "none"] = Field(default="none")
    """访问模式：whitelist（白名单）、blacklist（黑名单）、none（不过滤）。"""

    users: list[str] = Field(default=[])
    """用户 ID 列表（字符串形式）。"""

    groups: list[str] = Field(default=[])
    """群 ID 列表（字符串形式）。"""


class SilentConfig(BaseModel):
    """静默关键词配置。"""

    enabled: bool = True
    """是否启用静默关键词。"""

    keywords: list[str] = Field(default=["闭嘴", "别回", "silent"])
    """静默关键词列表，命中则不回复。"""


class RateLimitConfig(BaseModel):
    """频控配置。"""

    enabled: bool = True
    """是否启用频控。"""

    max_requests: int = Field(default=DEFAULT_RL_PER_SESSION, ge=1, le=100)
    """时间窗口内最大请求次数。"""

    window: int = Field(default=DEFAULT_RL_WINDOW, ge=1, le=300)
    """时间窗口（秒）。"""


class TriggerConfig(BaseModel):
    """触发检测配置。"""

    mode: Literal["mention", "keyword", "spectator"] = Field(default="keyword")
    """触发模式：mention（@提及）、keyword（关键词）、spectator（旁观模式）。"""

    keywords: list[str] = Field(default=["小助手", "bot"])
    """关键词列表（keyword 模式下生效）。"""


class SleepScheduleConfig(BaseModel):
    """休眠时间表配置。"""

    start: str = Field(default=DEFAULT_SLEEP_START, pattern=_TIME_PATTERN.pattern)
    """休眠开始时间（HH:MM）。"""

    end: str = Field(default=DEFAULT_SLEEP_END, pattern=_TIME_PATTERN.pattern)
    """休眠结束时间（HH:MM）。"""


class SleepConfig(BaseModel):
    """休眠模式配置。"""

    enabled: bool = False
    """是否启用休眠模式。"""

    mode: Literal["schedule", "manual"] = Field(default="schedule")
    """休眠模式：schedule（定时）、manual（手动开关）。"""

    schedule: SleepScheduleConfig = Field(default_factory=SleepScheduleConfig)
    """定时休眠配置（schedule 模式生效）。"""

    override_by_mention: bool = True
    """@mention 是否可临时唤醒（休眠期间）。"""


class AdminConfig(BaseModel):
    """管理命令配置。"""

    enabled: bool = True
    """是否启用管理命令。"""


class DebounceConfig(BaseModel):
    """回复防抖合并配置。"""

    enabled: bool = True
    """是否启用防抖。"""

    window: int = Field(default=DEFAULT_DEBOUNCE_WINDOW, ge=1, le=30)
    """防抖窗口（秒），窗口内消息合并为一条回复。"""


class FormatConfig(BaseModel):
    """消息格式化配置。"""

    max_length: int = Field(default=DEFAULT_FORMAT_MAX_LENGTH, ge=100, le=2000)
    """单条消息最大长度。"""

    mode: Literal["plain", "markdown"] = Field(default="plain")
    """格式化模式：plain（纯文本）、markdown（Markdown）。"""


class PipelineConfig(BaseModel):
    """Pipeline 各阶段配置聚合。"""

    sleep: SleepConfig = Field(default_factory=SleepConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    access: AccessConfig = Field(default_factory=AccessConfig)
    silent: SilentConfig = Field(default_factory=SilentConfig)
    ratelimit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    trigger: TriggerConfig = Field(default_factory=TriggerConfig)
    debounce: DebounceConfig = Field(default_factory=DebounceConfig)
    format: FormatConfig = Field(default_factory=FormatConfig)


class ChatConfig(BaseModel):
    """聊天插件总配置。

    通过 YAML 配置文件（chat_config.yaml）加载复杂配置项，
    同时支持 NoneBot 的 env 变量覆盖。
    """

    config_path: str = Field(
        default_factory=lambda: str(Path(__file__).resolve().parent.parent / "chat_config.yaml")
    )
    """YAML 配置文件路径。"""

    chat_enabled: bool = True
    """是否启用聊天功能。"""

    only_superusers: bool = True
    """是否仅允许超级用户使用聊天功能。"""

    # PipelineConfig 保留结构定义，但实际从 chat_config.yaml 加载
    pipeline: Any = None  # type: ignore[assignment]
    """Pipeline 各阶段配置。"""
