"""Test `BlazeBatchTTS` — không gọi mạng thật, mock `httpx.AsyncClient`."""

import base64
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.tts.blaze_provider import BlazeBatchTTS
from app.tts.exceptions import TTSAPIError, TTSConnectionError


def _make_provider(**overrides: object) -> BlazeBatchTTS:
    defaults: dict[str, object] = {
        "api_token": "token-test",
        "base_url": "https://api.blaze.vn",
        "model": "v2.0_pro",
        "speaker_id": "HN-Nam-1-BL",
    }
    defaults.update(overrides)
    return BlazeBatchTTS(**defaults)  # type: ignore[arg-type]


def _patch_client(monkeypatch, mock_response: MagicMock, *, post_side_effect=None) -> AsyncMock:
    mock_client = AsyncMock()
    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=mock_client))
    return mock_client


async def test_synthesize_binary_response(monkeypatch) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-type": "audio/mpeg"}
    mock_response.content = b"\xff\xfb\x90fake-mp3-bytes"
    mock_client = _patch_client(monkeypatch, mock_response)

    provider = _make_provider()
    result = await provider.synthesize("Xin chào ông bà")

    assert result.audio_bytes == b"\xff\xfb\x90fake-mp3-bytes"
    assert result.provider == "blaze"

    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer token-test"
    assert call_kwargs["json"]["query"] == "Xin chào ông bà"
    assert call_kwargs["json"]["speaker_id"] == "HN-Nam-1-BL"


async def test_synthesize_json_base64_response(monkeypatch) -> None:
    audio_bytes = b"raw-audio-data"
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"audio": base64.b64encode(audio_bytes).decode()}
    _patch_client(monkeypatch, mock_response)

    provider = _make_provider()
    result = await provider.synthesize("Xin chào")
    assert result.audio_bytes == audio_bytes


async def test_synthesize_json_missing_audio_field_raises_api_error(monkeypatch) -> None:
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json.return_value = {"error": "something else"}
    _patch_client(monkeypatch, mock_response)

    provider = _make_provider()
    with pytest.raises(TTSAPIError):
        await provider.synthesize("Xin chào")


async def test_synthesize_transport_error_raises_connection_error(monkeypatch) -> None:
    _patch_client(monkeypatch, MagicMock(), post_side_effect=httpx.ConnectError("boom"))
    provider = _make_provider()
    with pytest.raises(TTSConnectionError):
        await provider.synthesize("Xin chào")


async def test_synthesize_http_status_error_raises_api_error(monkeypatch) -> None:
    request = httpx.Request("POST", "https://api.blaze.vn/v1/tts")
    response = httpx.Response(400, request=request)
    _patch_client(
        monkeypatch,
        MagicMock(),
        post_side_effect=httpx.HTTPStatusError("bad", request=request, response=response),
    )
    provider = _make_provider()
    with pytest.raises(TTSAPIError):
        await provider.synthesize("Xin chào")
