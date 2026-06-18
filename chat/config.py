"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Chat plugin configuration (Pydantic Config for NoneBot)
"""

__author__ = "Xiaji-yu"

from pathlib import Path

from pydantic import BaseModel, Field


class PersonalityConfig(BaseModel):
    """人格配置。"""

    name: str = "小助手"
    """人格名称。"""

    system_prompt: str = (
        "你是一个友善、聪明的助手，名叫小助手。"
        "请用简洁、自然的语气回复，避免过于正式或机械的表达。"
    )
    """系统提示词（System Prompt），定义 AI 的人格和行为准则。"""

    wake_words: list[str] = ["小助手", "bot"]
    """唤醒词列表。仅当消息命中唤醒词时才触发回复（主动回复除外）。"""


class LLMConfig(BaseModel):
    """LLM 客户端配置。"""

    base_url: str = "http://localhost:11434/v1"
    """OpenAI 兼容 API 的基础 URL。"""

    model: str = "llama2"
    """模型名称。"""

    api_key: str = ""
    """API Key。空字符串表示无需认证。"""

    max_tokens: int = Field(default=1000, ge=1, le=8192)
    """单次生成的最大 token 数。"""

    timeout: int = Field(default=30, ge=5, le=120)
    """API 请求超时时间（秒）。"""


class TemperatureConfig(BaseModel):
    """温度配置，控制回复的创造性。"""

    default: float = Field(default=0.7, ge=0.0, le=2.0)
    """普通回复温度。"""

    proactive_min: float = Field(default=0.5, ge=0.0, le=2.0)
    """主动回复温度下限。"""

    proactive_max: float = Field(default=1.0, ge=0.0, le=2.0)
    """主动回复温度上限。"""


class MemoryConfig(BaseModel):
    """记忆系统配置。"""

    max_history: int = Field(default=50, ge=5, le=500)
    """单会话最大消息条数。超过后触发蒸馏。"""

    distillation_threshold: int = Field(default=40, ge=10, le=200)
    """对话消息数达到此阈值时触发记忆蒸馏。"""

    core_memory_max: int = Field(default=10, ge=1, le=50)
    """蒸馏后保留的核心记忆条数。"""


class ProactiveConfig(BaseModel):
    """主动回复配置。"""

    enabled: bool = True
    """是否启用主动回复。"""

    probability: float = Field(default=0.1, ge=0.0, le=1.0)
    """每条非唤醒词消息的主动回复概率。"""

    cooldown: int = Field(default=300, ge=30, le=3600)
    """主动回复冷却时间（秒）。"""

    check_interval: int = Field(default=60, ge=10, le=600)
    """主动回复检查间隔（秒）。"""


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
