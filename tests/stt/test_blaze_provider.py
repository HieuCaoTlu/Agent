"""Test `BlazeSTTProvider` — không gọi mạng thật, mock WebSocket/HTTP."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import websockets

from app.stt.blaze_provider import BlazeSTTProvider
from app.stt.exceptions import STTAPIError, STTConnectionError


def _make_provider(**overrides: object) -> BlazeSTTProvider:
    defaults: dict[str, object] = {
        "api_token": "token-test",
        "base_url": "https://api.blaze.vn",
        "ws_base_url": "wss://api.blaze.vn",
        "stream_model": "stt-stream-1.5",
        "async_model": "stt-async-1.5",
    }
    defaults.update(overrides)
    return BlazeSTTProvider(**defaults)  # type: ignore[arg-type]


class _FakeWebSocket:
    """Giả lập `websockets.ClientConnection` đủ để test `transcribe_stream`."""

    def __init__(self, incoming_messages: list[str]) -> None:
        self.sent: list[str | bytes] = []
        self._incoming = list(incoming_messages)

    async def send(self, message: str | bytes) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if not self._incoming:
            raise websockets.exceptions.ConnectionClosedOK(None, None)
        return self._incoming.pop(0)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self._incoming:
            raise StopAsyncIteration
        return self._incoming.pop(0)


async def _audio_stream(chunks: list[bytes]):
    for chunk in chunks:
        yield chunk


def _patch_websockets_connect(monkeypatch, fake_ws: _FakeWebSocket) -> None:
    @asynccontextmanager
    async def _fake_connect(uri: str):
        yield fake_ws

    monkeypatch.setattr(websockets, "connect", _fake_connect)


async def test_transcribe_stream_sends_auth_and_yields_chunks(monkeypatch) -> None:
    ready = json.dumps({"type": "ready"})
    partial = json.dumps({"type": "partial", "text": "tôi muốn"})
    final = json.dumps({"type": "final", "text": "tôi muốn đăng ký khai sinh"})
    fake_ws = _FakeWebSocket([ready, partial, final])
    _patch_websockets_connect(monkeypatch, fake_ws)

    provider = _make_provider()
    chunks = [c async for c in provider.transcribe_stream(_audio_stream([b"\x00\x01"]))]

    auth_message = json.loads(fake_ws.sent[0])
    assert auth_message["token"] == "token-test"
    assert auth_message["language"] == "vi"
    assert auth_message["model"] == "stt-stream-1.5"

    assert [c.text for c in chunks] == ["tôi muốn", "tôi muốn đăng ký khai sinh"]
    assert chunks[0].is_final is False
    assert chunks[1].is_final is True


async def test_transcribe_stream_raises_if_no_ready_message(monkeypatch) -> None:
    fake_ws = _FakeWebSocket([json.dumps({"type": "error", "message": "bad token"})])
    _patch_websockets_connect(monkeypatch, fake_ws)

    provider = _make_provider()
    with pytest.raises(STTAPIError):
        async for _ in provider.transcribe_stream(_audio_stream([b"\x00"])):
            pass


async def test_transcribe_stream_wraps_websocket_exception(monkeypatch) -> None:
    @asynccontextmanager
    async def _raising_connect(uri: str):
        raise websockets.exceptions.InvalidURI(uri, "bad uri")
        yield  # pragma: no cover — unreachable, chỉ để hàm là async generator

    monkeypatch.setattr(websockets, "connect", _raising_connect)

    provider = _make_provider()
    with pytest.raises(STTConnectionError):
        async for _ in provider.transcribe_stream(_audio_stream([b"\x00"])):
            pass


async def test_transcribe_file_success(monkeypatch) -> None:
    provider = _make_provider()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"text": "kết quả từ file"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    chunk = await provider.transcribe_file(b"fake audio")
    assert chunk.text == "kết quả từ file"
    assert chunk.is_final is True
    assert chunk.provider == "blaze"

    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer token-test"
    assert call_kwargs["params"]["model"] == "stt-async-1.5"


async def test_transcribe_file_retries_on_transport_error_then_succeeds(monkeypatch) -> None:
    provider = _make_provider()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"text": "ok sau retry"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=[httpx.ConnectError("boom"), mock_response]
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    chunk = await provider.transcribe_file(b"fake audio")
    assert chunk.text == "ok sau retry"
    assert mock_client.post.call_count == 2


async def test_transcribe_file_gives_up_after_exhausting_retries(monkeypatch) -> None:
    provider = _make_provider()
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    with pytest.raises(STTConnectionError):
        await provider.transcribe_file(b"fake audio")
    assert mock_client.post.call_count == 3  # 1 lần đầu + 2 retry (_MAX_FILE_RETRIES)


async def test_transcribe_file_does_not_retry_http_status_error(monkeypatch) -> None:
    provider = _make_provider()
    request = httpx.Request("POST", "https://api.blaze.vn/v1/stt/execute")
    response = httpx.Response(400, request=request)

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("bad request", request=request, response=response)
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))

    with pytest.raises(STTAPIError):
        await provider.transcribe_file(b"fake audio")
    assert mock_client.post.call_count == 1  # không retry lỗi API cố định
