"""
@Author         : Xiaji-yu
@Date           : 2026-06-18
@Description    : Tests for LLMClient (aiohttp OpenAI-compatible client with fallback)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from chat.llm import LLMClient


class TestLLMClientInit:
    """Tests for LLMClient initialization and model property."""

    def test_model_property_returns_primary_model(self) -> None:
        client = LLMClient(base_url="http://example.com", model="llama2")
        assert client.model == "llama2"

    def test_endpoints_contains_primary_only_by_default(self) -> None:
        client = LLMClient(base_url="http://example.com/v1", model="m")
        assert len(client.endpoints) == 1
        assert client.endpoints[0].url == "http://example.com/v1/chat/completions"

    def test_endpoints_contains_primary_and_fallbacks(self) -> None:
        client = LLMClient(
            base_url="http://primary.com", model="m1",
            fallbacks=[("http://backup.com", "m2", "k2")],
        )
        assert len(client.endpoints) == 2
        assert client.endpoints[0].model == "m1"
        assert client.endpoints[1].model == "m2"
        assert client.endpoints[1].api_key == "k2"

    def test_stores_api_key_on_primary(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", api_key="sk-123")
        assert client.endpoints[0].api_key == "sk-123"

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
        headers = LLMClient(base_url="http://example.com", model="m")._headers("")
        assert headers["Content-Type"] == "application/json"
        assert "Authorization" not in headers

    def test_headers_with_api_key(self) -> None:
        headers = LLMClient(base_url="http://example.com", model="m")._headers("sk-abc")
        assert headers["Authorization"] == "Bearer sk-abc"


class TestLLMClientPayload:
    """Tests for _payload()."""

    def test_payload_defaults(self) -> None:
        client = LLMClient(base_url="http://example.com", model="llama2", max_tokens=200)
        payload = client._payload("llama2", [{"role": "user", "content": "hi"}])
        assert payload["model"] == "llama2"
        assert payload["messages"] == [{"role": "user", "content": "hi"}]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 200
        assert payload["stream"] is False

    def test_payload_overrides_temperature_and_max_tokens(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        payload = client._payload("m", [], temperature=0.5, max_tokens=100)
        assert payload["temperature"] == 0.5
        assert payload["max_tokens"] == 100

    def test_payload_falls_back_to_default_max_tokens_when_none(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m", max_tokens=300)
        payload = client._payload("m", [])
        assert payload["max_tokens"] == 300

    def test_payload_stream_true(self) -> None:
        client = LLMClient(base_url="http://example.com", model="m")
        payload = client._payload("m", [], stream=True)
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
    def _mock_error_response(status: int = 500, text: str = "Server Error"):
        mock_resp = MagicMock()
        mock_resp.status = status
        mock_resp.text = AsyncMock(return_value=text)
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
    async def test_chat_returns_content_on_success(self, caplog: Any) -> None:
        client = LLMClient(base_url="http://primary.com", model="m")
        mock_session = self._mock_session(self._mock_success_response("hi there"))

        with caplog.at_level(logging.INFO, logger="chat.llm"):
            with patch.object(client, "_get_session", return_value=mock_session):
                result = await client.chat([{"role": "user", "content": "hi"}])

        assert result == "hi there"
        # 成功时应记录回复来源（主端点）
        assert any("回复来自" in r.message for r in caplog.records)
        assert any("主端点 m" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_chat_returns_none_on_http_error(self) -> None:
        client = LLMClient(base_url="http://primary.com", model="m")
        mock_session = self._mock_session(self._mock_error_response())

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_chat_returns_none_on_unexpected_response_format(self) -> None:
        client = LLMClient(base_url="http://primary.com", model="m")
        resp = self._mock_success_response()
        resp.json = AsyncMock(return_value={"choices": []})
        mock_session = self._mock_session(resp)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None

    @pytest.mark.asyncio
    async def test_chat_returns_none_on_network_error(self) -> None:
        client = LLMClient(base_url="http://primary.com", model="m")
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=asyncio.TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None


class TestLLMClientFallback:
    """Tests for fallback to backup endpoints."""

    @staticmethod
    def _client_with_fallback() -> LLMClient:
        return LLMClient(
            base_url="http://primary.com", model="m1",
            fallbacks=[("http://backup.com", "m2", "k2")],
        )

    @staticmethod
    def _sequential_session(*responses: Any) -> MagicMock:
        """mock session，post 依序返回每个 response。"""
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=list(responses))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        return mock_session

    @pytest.mark.asyncio
    async def test_falls_back_when_primary_http_error(self, caplog: Any) -> None:
        client = self._client_with_fallback()
        primary_err = TestLLMClientChat._mock_error_response()
        backup_ok = TestLLMClientChat._mock_success_response("backup reply")
        mock_session = self._sequential_session(primary_err, backup_ok)

        with caplog.at_level(logging.INFO, logger="chat.llm"):
            with patch.object(client, "_get_session", return_value=mock_session):
                result = await client.chat([{"role": "user", "content": "hi"}])

        assert result == "backup reply"
        # 主 + 备用各请求一次
        assert mock_session.post.call_count == 2
        # 成功回复来自备用端点
        assert any("备用端点1 m2" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_falls_back_when_primary_network_error(self) -> None:
        client = self._client_with_fallback()
        mock_session = MagicMock()
        # 第一次抛网络错误，第二次成功
        mock_session.post = MagicMock(
            side_effect=[asyncio.TimeoutError(), TestLLMClientChat._mock_success_response("ok")]
        )
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result == "ok"
        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_all_endpoints_fail(self) -> None:
        client = self._client_with_fallback()
        primary_err = TestLLMClientChat._mock_error_response(500)
        backup_err = TestLLMClientChat._mock_error_response(503)
        mock_session = self._sequential_session(primary_err, backup_err)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result is None
        assert mock_session.post.call_count == 2

    @pytest.mark.asyncio
    async def test_uses_primary_when_it_succeeds(self) -> None:
        """主端点成功时不应调用备用端点。"""
        client = self._client_with_fallback()
        primary_ok = TestLLMClientChat._mock_success_response("primary")
        mock_session = self._sequential_session(primary_ok)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.chat([{"role": "user", "content": "hi"}])

        assert result == "primary"
        assert mock_session.post.call_count == 1

    @pytest.mark.asyncio
    async def test_health_check_true_when_primary_succeeds(self) -> None:
        client = LLMClient(base_url="http://primary.com", model="m")
        mock_session = TestLLMClientChat._mock_session(
            TestLLMClientChat._mock_success_response("ok")
        )

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_true_via_fallback(self) -> None:
        """主端点失败但备用端点成功 → 健康检查通过。"""
        client = self._client_with_fallback()
        primary_err = TestLLMClientChat._mock_error_response(500)
        backup_ok = TestLLMClientChat._mock_success_response("ok")
        mock_session = self._sequential_session(primary_err, backup_ok)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_false_when_all_fail(self) -> None:
        client = self._client_with_fallback()
        primary_err = TestLLMClientChat._mock_error_response(500)
        backup_err = TestLLMClientChat._mock_error_response(503)
        mock_session = self._sequential_session(primary_err, backup_err)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = await client.health_check()

        assert result is False


class TestLLMClientChatStream:
    """Tests for chat_stream() SSE interactions with fallback."""

    @staticmethod
    def _make_async_iter(lines: list[bytes]) -> Any:
        class AsyncBytesIter:
            def __init__(self, items: list[bytes]) -> None:
                self._items = items
                self._index = 0

            def __aiter__(self) -> AsyncBytesIter:
                return self

            async def __anext__(self) -> bytes:
                if self._index >= len(self._items):
                    raise StopAsyncIteration
                value = self._items[self._index]
                self._index += 1
                return value

        return AsyncBytesIter(lines)

    @pytest.mark.asyncio
    async def test_chat_stream_yields_deltas(self) -> None:
        client = LLMClient(base_url="http://primary.com", model="m")
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
    async def test_chat_stream_falls_back_on_primary_error(self) -> None:
        """主端点建立失败 → 切备用端点并产出内容。"""
        client = LLMClient(
            base_url="http://primary.com", model="m1",
            fallbacks=[("http://backup.com", "m2", "k2")],
        )
        primary_err = MagicMock()
        primary_err.status = 500
        primary_err.text = AsyncMock(return_value="Server Error")
        primary_err.__aenter__ = AsyncMock(return_value=primary_err)
        primary_err.__aexit__ = AsyncMock(return_value=False)

        backup_ok = MagicMock()
        backup_ok.status = 200
        backup_ok.content = self._make_async_iter(
            [b'data: {"choices":[{"delta":{"content":"z"}}]}\n', b"data: [DONE]\n"]
        )
        backup_ok.__aenter__ = AsyncMock(return_value=backup_ok)
        backup_ok.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=[primary_err, backup_ok])
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch.object(client, "_get_session", return_value=mock_session):
            result = []
            async for chunk in client.chat_stream([{"role": "user", "content": "hi"}]):
                result.append(chunk)

        assert result == ["z"]
        assert mock_session.post.call_count == 2
