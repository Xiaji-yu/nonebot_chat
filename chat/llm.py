"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : OpenAI-compatible LLM client (aiohttp, zero heavy deps)
"""

__author__ = "Xiaji-yu"

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import aiohttp

try:  # NoneBot 运行时使用 loguru（INFO 级别可见）
    from nonebot.log import logger
except ImportError:  # 独立运行/测试环境回退标准 logging
    logger = logging.getLogger(__name__)

# OpenAI Chat Completions 端点
CHAT_ENDPOINT = "/chat/completions"


@dataclass(frozen=True)
class Endpoint:
    """单个 LLM 端点（主端点或备用端点）。"""

    base_url: str
    model: str
    api_key: str = ""

    @property
    def url(self) -> str:
        return self.base_url.rstrip("/") + CHAT_ENDPOINT


class LLMClient:
    """OpenAI 兼容 API 客户端（带 fallback 备用端点）。

    使用 aiohttp 发送异步请求，支持 OpenAI / Ollama / 任何兼容端点。
    主端点失败时（网络错误、超时、HTTP 4xx/5xx、响应格式错误）
    自动按顺序尝试备用端点，全部失败才返回失败结果。
    不依赖 openai SDK，保持零重型依赖。
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        max_tokens: int = 1000,
        timeout: int = 30,
        fallbacks: list[tuple[str, str, str]] | None = None,
    ) -> None:
        """初始化客户端。

        Args:
            base_url: 主端点 OpenAI 兼容 API 基础 URL。
            model: 主端点模型名称。
            api_key: 主端点 API Key。
            max_tokens: 单次生成的最大 token 数。
            timeout: API 请求超时时间（秒）。
            fallbacks: 备用端点列表 [(base_url, model, api_key), ...]，可为空。
        """
        primary = Endpoint(base_url=base_url.rstrip("/"), model=model, api_key=api_key)
        backup = [
            Endpoint(base_url=url.rstrip("/"), model=m, api_key=k)
            for url, m, k in (fallbacks or [])
        ]
        self._endpoints: list[Endpoint] = [primary, *backup]
        self._max_tokens = max_tokens
        self._timeout = aiohttp.ClientTimeout(
            total=timeout,
            connect=min(10, timeout),
            sock_read=min(60, timeout),
        )
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    @property
    def model(self) -> str:
        """主端点模型名称。"""
        return self._endpoints[0].model

    @property
    def endpoints(self) -> list[Endpoint]:
        """全部端点（主 + 备用）。"""
        return list(self._endpoints)

    def _endpoint_tag(self, idx: int, ep: Endpoint) -> str:
        """生成端点标签：主端点 / 备用端点 N。"""
        if idx == 0:
            return f"主端点 {ep.model}"
        return f"备用端点{idx} {ep.model}"

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建共享的 aiohttp session。"""
        async with self._session_lock:
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession(timeout=self._timeout)
            return self._session

    async def close(self) -> None:
        """关闭底层连接池。"""
        async with self._session_lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
            self._session = None

    def _headers(self, api_key: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _payload(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self._max_tokens,
            "stream": stream,
        }

    # ------------------------------------------------------------------
    # 非流式聊天（带 fallback）
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str | None:
        """发送聊天请求，返回助手回复文本。

        主端点失败时自动尝试备用端点。

        Args:
            messages: OpenAI Chat 格式的消息列表。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数，None 则使用默认值。

        Returns:
            助手回复的文本内容，全部端点失败返回 None。
        """
        for idx, ep in enumerate(self._endpoints):
            logger.debug(
                f"LLM request: model={ep.model}, msgs={len(messages)}, "
                f"temp={temperature:.2f} (endpoint {idx + 1}/{len(self._endpoints)})"
            )
            result = await self._chat_once(ep, messages, temperature, max_tokens)
            if result is not None:
                logger.info(f"LLM 回复来自 {self._endpoint_tag(idx, ep)}")
                return result
            if idx < len(self._endpoints) - 1:
                logger.warning(
                    f"LLM endpoint {ep.base_url}/{ep.model} failed, falling back to next endpoint"
                )
        return None

    async def _chat_once(
        self,
        ep: Endpoint,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> str | None:
        """对单个端点发送一次非流式请求。"""
        payload = self._payload(ep.model, messages, temperature, max_tokens, stream=False)
        session = await self._get_session()
        try:
            async with session.post(
                ep.url,
                headers=self._headers(ep.api_key),
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"LLM API error {resp.status}: {text[:500]}")
                    return None
                data = await resp.json()
        except aiohttp.ClientError as exc:
            logger.error(f"LLM request failed: {exc}")
            return None
        except Exception:
            logger.exception("Unexpected error during LLM request")
            return None

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            logger.error(f"Unexpected LLM response format: {str(data)[:500]}")
            return None

    # ------------------------------------------------------------------
    # 流式聊天（带 fallback，仅在建立请求阶段失败时切换）
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        """流式聊天请求，逐块返回助手回复文本。

        主端点建立请求失败（网络错误 / 非 200）时自动尝试备用端点；
        一旦开始接收内容则不再切换（避免输出错位）。

        Args:
            messages: OpenAI Chat 格式的消息列表。
            temperature: 采样温度。
            max_tokens: 最大生成 token 数，None 则使用默认值。

        Yields:
            回复文本片段，全部端点失败时提前终止并返回。
        """
        for idx, ep in enumerate(self._endpoints):
            logger.debug(
                f"LLM stream request: model={ep.model}, msgs={len(messages)} "
                f"(endpoint {idx + 1}/{len(self._endpoints)})"
            )
            stream = self._stream_once(ep, messages, temperature, max_tokens)
            try:
                first = await anext(stream)
            except StopAsyncIteration:
                # 该端点未能建立请求（无内容产出）→ 尝试下一个端点
                if idx < len(self._endpoints) - 1:
                    logger.warning(
                        f"LLM stream endpoint {ep.base_url}/{ep.model} failed to start, trying next"
                    )
                continue
            # 端点已成功建立并产出首块 → 消费完本端点（不再切换）
            logger.info(f"LLM 回复来自 {self._endpoint_tag(idx, ep)}")
            yield first
            async for chunk in stream:
                yield chunk
            return
        return

    async def _stream_once(
        self,
        ep: Endpoint,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
    ) -> AsyncIterator[str]:
        """对单个端点发起流式请求，仅在成功建立后产出内容。

        建立请求失败（非 200 / 网络错误）时不产出任何内容（调用方可切换端点）；
        已建立后中途断流则按正常结束处理。
        """
        payload = self._payload(ep.model, messages, temperature, max_tokens, stream=True)
        session = await self._get_session()
        try:
            async with session.post(
                ep.url,
                headers=self._headers(ep.api_key),
                json=payload,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"LLM stream API error {resp.status}: {text[:500]}")
                    return
                async for line in resp.content:
                    if not line:
                        continue
                    text_line = line.decode("utf-8", errors="ignore").strip()
                    if not text_line.startswith("data:"):
                        continue
                    data = text_line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                        delta = event["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (KeyError, IndexError, TypeError, ValueError):
                        continue
        except aiohttp.ClientError as exc:
            logger.error(f"LLM stream request failed: {exc}")
        except Exception:
            logger.exception("Unexpected error during LLM stream request")

    # ------------------------------------------------------------------
    # 健康检查（主端点失败时自动尝试备用端点）
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """健康检查：任一端点连通即视为可用。"""
        try:
            result = await self.chat(
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return result is not None
        except Exception:
            return False
