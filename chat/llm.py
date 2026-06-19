"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : OpenAI-compatible LLM client (aiohttp, zero heavy deps)
"""

__author__ = "Xiaji-yu"

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# OpenAI Chat Completions 端点
CHAT_ENDPOINT = "/chat/completions"


class LLMClient:
    """OpenAI 兼容 API 客户端。

    使用 aiohttp 发送异步请求，支持 OpenAI / Ollama / 任何兼容端点。
    不依赖 openai SDK，保持零重型依赖。
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        max_tokens: int = 1000,
        timeout: int = 30,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._max_tokens = max_tokens
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def model(self) -> str:
        return self._model

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _payload(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self._max_tokens,
            "stream": False,
        }

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str | None:
        """发送聊天请求，返回助手回复文本。

        Args:
            messages: OpenAI Chat 格式的消息列表。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数，None 则使用默认值。

        Returns:
            助手回复的文本内容，失败返回 None。
        """
        url = self._base_url + CHAT_ENDPOINT
        payload = self._payload(messages, temperature, max_tokens)

        logger.debug(
            "LLM request: model=%s, msgs=%d, temp=%.2f",
            self._model,
            len(messages),
            temperature,
        )

        try:
            async with aiohttp.ClientSession(timeout=self._timeout) as session:
                async with session.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(
                            "LLM API error %d: %s", resp.status, text[:500]
                        )
                        return None
                    data = await resp.json()
        except aiohttp.ClientError as exc:
            logger.error("LLM request failed: %s", exc)
            return None
        except Exception:
            logger.exception("Unexpected error during LLM request")
            return None

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            logger.error("Unexpected LLM response format: %s", str(data)[:500])
            return None

    async def health_check(self) -> bool:
        """简单健康检查：发送一条最小请求验证连通性。"""
        try:
            result = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return result is not None
        except Exception:
            return False
