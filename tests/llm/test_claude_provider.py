"""Test `ClaudeLLMProvider` — không gọi mạng thật, mock `messages.create`."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import anthropic
import pytest

from app.llm import claude_provider as claude_provider_module
from app.llm.claude_provider import ClaudeLLMProvider
from app.llm.exceptions import LLMAPIError, LLMConnectionError, UnapprovedHostError

_SCHEMA = {"type": "object", "properties": {"fields": {"type": "array"}}}


def _make_provider(**overrides: object) -> ClaudeLLMProvider:
    defaults: dict[str, object] = {
        "api_key": "sk-test",
        "model": "claude-sonnet-5",
        "result_json_schema": _SCHEMA,
        "approved_hosts": ["api.anthropic.com"],
    }
    defaults.update(overrides)
    return ClaudeLLMProvider(**defaults)  # type: ignore[arg-type]


def _make_message(tool_input: dict) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=tool_input)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        model="claude-sonnet-5",
    )


def test_rejects_unapproved_host() -> None:
    with pytest.raises(UnapprovedHostError):
        _make_provider(
            approved_hosts=["api.anthropic.com"], base_url="https://evil.example.com"
        )


def test_accepts_approved_custom_base_url() -> None:
    provider = _make_provider(
        approved_hosts=["api.anthropic.com", "proxy.internal"], base_url="https://proxy.internal"
    )
    assert isinstance(provider, ClaudeLLMProvider)


async def test_extract_success_returns_llm_response() -> None:
    provider = _make_provider()
    tool_result = {"fields": [], "observations": []}
    provider._client.messages.create = AsyncMock(return_value=_make_message(tool_result))  # type: ignore[method-assign]

    response = await provider.extract("system", "user")

    assert json.loads(response.raw_text) == tool_result
    assert response.input_tokens == 10
    assert response.output_tokens == 5
    assert response.model == "claude-sonnet-5"


async def test_extract_no_tool_use_block_raises_api_error() -> None:
    provider = _make_provider()
    message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="oops")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        model="claude-sonnet-5",
    )
    provider._client.messages.create = AsyncMock(return_value=message)  # type: ignore[method-assign]

    with pytest.raises(LLMAPIError):
        await provider.extract("system", "user")


async def test_extract_retries_on_connection_error_then_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(claude_provider_module.asyncio, "sleep", AsyncMock())
    provider = _make_provider()
    tool_result = {"fields": [], "observations": []}
    mock_request = SimpleNamespace()
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            anthropic.APIConnectionError(request=mock_request),
            _make_message(tool_result),
        ]
    )

    response = await provider.extract("system", "user")
    assert json.loads(response.raw_text) == tool_result
    assert provider._client.messages.create.call_count == 2


async def test_extract_gives_up_after_exhausting_retries(monkeypatch) -> None:
    monkeypatch.setattr(claude_provider_module.asyncio, "sleep", AsyncMock())
    provider = _make_provider()
    mock_request = SimpleNamespace()
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.APIConnectionError(request=mock_request)
    )

    with pytest.raises(LLMConnectionError):
        await provider.extract("system", "user")
    assert provider._client.messages.create.call_count == 3  # 1 lần đầu + 2 retry


async def test_health_check_true_on_success() -> None:
    provider = _make_provider()
    provider._client.messages.create = AsyncMock(return_value=_make_message({}))  # type: ignore[method-assign]
    assert await provider.health_check() is True


async def test_health_check_false_on_error() -> None:
    provider = _make_provider()
    mock_request = SimpleNamespace()
    provider._client.messages.create = AsyncMock(  # type: ignore[method-assign]
        side_effect=anthropic.APIConnectionError(request=mock_request)
    )
    assert await provider.health_check() is False
