"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Tests for LLMClient (aiohttp OpenAI-compatible client)
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.llm import LLMClient


class TestLLMClientInit:
    """Tests for LLMClient initialization and model property."""

    def test_model_property_returns_model(self) -> None:
        client = LLMClient(base_url="http://example.com", model="llama2")
        assert client.model == "llama2"

    def test_stores_base_url_trailing_slash_stripped(self) -> None:
        client = LLMClient(base_url="http://example.com/v1/", model="m")
        assert client._base_url == "http://example.com/v1"

    def test_stores_api_key(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", api_key="sk-123")
        assert client._api_key == "sk-123"

    def test_stores_max_tokens(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", max_tokens=500)
        assert client._max_tokens == 500

    def test_stores_timeout(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", timeout=60)
        assert client._timeout.total == 60
        assert client._timeout.connect == 10
        assert client._timeout.sock_read == 60


class TestLLMClientSession:
    """Tests for session reuse and close."""

    @pytest.mark.asyncio
    async def test_get_session_creates_and_reuses(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        session1 = await client._get_session()
        session2 = await client._get_session()
        assert session1 is session2

    @pytest.mark.asyncio
    async def test_close_clears_session(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        session = await client._get_session()
        await client.close()
        assert client._session is None
        assert session.closed


class TestLLMClientHeaders:
    """Tests for _headers()."""

    def test_headers_without_api_key(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        headers = client._headers()
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_headers_with_api_key(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", api_key="sk-abc")
        headers = client._headers()
        assert headers["Authorization"] == "Bearer sk-abc"


class TestLLMClientPayload:
    """Tests for _payload()."""

    def test_payload_defaults(self) -> None:
        client = LLMClient(base_url="http://example.com", model="llama2", max_tokens=200)
        payload = client._payload([{"role": "user", "content": "hi"}])
        assert payload["model"] == "llama2"
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 200
        assert payload["stream"] is False

    def test_payload_overrides_temperature_and_max_tokens(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        payload = client._payload([], temperature=0.5, max_tokens=100)
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 100

    def test_payload_falls_back_to_default_max_tokens_when_none(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", max_tokens=300)
        payload = client._payload([])
        assert payload["max_tokens"] == 300

    def test_payload_stream_true(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        payload = client._payload([], stream=True)
        assert payload["stream"] is True


class TestLLMClientChat:
    """Tests for chat() HTTP interactions."""

    @staticmethod
    def _mock_success_response(text: str = "hello"):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={
            "choices": [{"message": {"content": text}}],
        })
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        return mock_resp

    @staticmethod
    def _mock_session(response):
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    @pytest.mark.asyncio
    async def test_chat_returns_content_on_success(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_resp = self._mock_success_response("hi there")
        mock_session = self._mock_session(mock_resp)

        with patch("chat.llm.aiohttp.ClientSession", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result == "hi there"

    @pytest.mark.asyncio
    async def test_chat_returns_none_on_http_error(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="Server Error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = self._mock_session(mock_resp)

        with patch("chat.llm.aiohttp.ClientSession", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_chat_returns_none_on_unexpected_response_format(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"choices": []})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = self._mock_session(mock_resp)

        with patch("chat.llm.aiohttp.ClientSession", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_chat_returns_none_on_network_error(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")

        with patch("chat.llm.aiohttp.ClientSession") as mock_session_cls:
            mock_session_cls.return_value.__aenter__ = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None


class TestLLMClientChatStream:
    """Tests for chat_stream() SSE interactions."""

    @staticmethod
    def _make_async_iter(lines: list[str]) -> Any:
        class AsyncIterator:
            def __init__(self, items: list[str]) -> None:
                self._items = items
                self._index = 0

            def __aiter__(self) -> AsyncIterator:
                return self

            async def __anext__(self) -> str:
                if self._index >= len(self._items):
                    raise StopAsyncIteration
                value = self._items[self._index]
                self._index += 1
                return value

        return AsyncIterator(lines)

    @pytest.mark.asyncio
    async def test_chat_stream_yields_deltas(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        lines = [
            b'data: {"choices":[{"delta":{"content":"a"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"b"}}]}\n',
            b'data: [DONE]\n',
        ]
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content = self._make_async_iter(lines)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = []
            async for chunk in client.chat_stream([{"role": "user", "content": "hi"}]):
                result.append(chunk)

        assert result == ["a", "b"]

    @pytest.mark.asyncio
    async def test_chat_stream_returns_none_on_http_error(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="Server Error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = []
            async for chunk in client.chat_stream([{"role": "user", "content": "hi"}]):
                result.append(chunk)

        assert result == []

    @pytest.mark.asyncio
    async def test_chat_stream_handles_network_error(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = []
            async for chunk in client.chat_stream([{"role": "user", "content": "hi"}]):
                result.append(chunk)

        assert result == []


class TestLLMClientHealthCheck:
    """Tests for health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_true_when_chat_succeeds(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_resp = TestLLMClientChat._mock_success_response("ok")
        mock_session = TestLLMClientChat._mock_session(mock_resp)

        with patch("chat.llm.aiohttp.ClientSession", return_value=mock_session):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_false_when_chat_fails(self) -> None:
        client = LLMClient(base_url="http://localhost:11434/v1", model="llama2")
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.text = AsyncMock(return_value="error")
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session = TestLLMClientChat._mock_session(mock_resp)

        with patch("chat.llm.aiohttp.ClientSession", return_value=mock_session):
            result = await client.health_check()

        assert result is False
