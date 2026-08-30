"""Test `GeminiLLMProvider` — không gọi mạng thật, mock `models.generate_content`."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import errors

from app.llm import gemini_provider as gemini_provider_module
from app.llm.exceptions import (
    LLMAPIError,
    LLMConnectionError,
    LLMRateLimitError,
    UnapprovedHostError,
)
from app.llm.gemini_provider import GeminiLLMProvider


def _make_provider(**overrides: object) -> GeminiLLMProvider:
    defaults: dict[str, object] = {
        "api_key": "test-key",
        "model": "gemini-2.5-flash",
        "approved_hosts": ["generativelanguage.googleapis.com"],
    }
    defaults.update(overrides)
    return GeminiLLMProvider(**defaults)  # type: ignore[arg-type]


def _make_response(result: dict) -> SimpleNamespace:
    return SimpleNamespace(
        text=json.dumps(result, ensure_ascii=False),
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5),
    )


def _client_error(status: int) -> errors.ClientError:
    return errors.ClientError(code=status, response_json={"error": {"message": "lỗi"}})


def _server_error() -> errors.ServerError:
    return errors.ServerError(code=503, response_json={"error": {"message": "lỗi máy chủ"}})


def test_rejects_unapproved_host() -> None:
    with pytest.raises(UnapprovedHostError):
        _make_provider(
            approved_hosts=["generativelanguage.googleapis.com"],
            base_url="https://evil.example.com",
        )


def test_accepts_approved_custom_base_url() -> None:
    provider = _make_provider(
        approved_hosts=["generativelanguage.googleapis.com", "proxy.internal"],
        base_url="https://proxy.internal",
    )
    assert isinstance(provider, GeminiLLMProvider)


async def test_extract_success_returns_llm_response() -> None:
    provider = _make_provider()
    result = {"fields": [], "observations": []}
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        return_value=_make_response(result)
    )

    response = await provider.extract("system", "user")

    assert json.loads(response.raw_text) == result
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.model == "gemini-2.5-flash"


async def test_extract_no_text_raises_api_error() -> None:
    provider = _make_provider()
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(text=None, usage_metadata=None)
    )

    with pytest.raises(LLMAPIError):
        await provider.extract("system", "user")


async def test_extract_rate_limit_maps_to_rate_limit_error(monkeypatch) -> None:
    monkeypatch.setattr(gemini_provider_module.asyncio, "sleep", AsyncMock())
    provider = _make_provider()
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        side_effect=_client_error(429)
    )

    with pytest.raises(LLMRateLimitError):
        await provider.extract("system", "user")


async def test_extract_retries_on_server_error_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(gemini_provider_module.asyncio, "sleep", AsyncMock())
    provider = _make_provider()
    result = {"fields": [], "observations": []}
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        side_effect=[_server_error(), _make_response(result)]
    )

    response = await provider.extract("system", "user")
    assert json.loads(response.raw_text) == result
    assert provider._client.aio.models.generate_content.call_count == 2


async def test_extract_gives_up_after_exhausting_retries(monkeypatch) -> None:
    monkeypatch.setattr(gemini_provider_module.asyncio, "sleep", AsyncMock())
    provider = _make_provider()
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        side_effect=_server_error()
    )

    with pytest.raises(LLMConnectionError):
        await provider.extract("system", "user")
    assert provider._client.aio.models.generate_content.call_count == 3  # 1 lần đầu + 2 retry


async def test_extract_client_error_not_rate_limit_raises_api_error_without_retry() -> None:
    provider = _make_provider()
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        side_effect=_client_error(400)
    )

    with pytest.raises(LLMAPIError):
        await provider.extract("system", "user")
    assert provider._client.aio.models.generate_content.call_count == 1


async def test_health_check_true_on_success() -> None:
    provider = _make_provider()
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        return_value=_make_response({})
    )
    assert await provider.health_check() is True


async def test_health_check_false_on_error() -> None:
    provider = _make_provider()
    provider._client.aio.models.generate_content = AsyncMock(  # type: ignore[method-assign]
        side_effect=_server_error()
    )
    assert await provider.health_check() is False
