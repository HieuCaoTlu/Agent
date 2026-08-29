import pytest

from app.config import Settings
from app.tts.blaze_provider import BlazeBatchTTS
from app.tts.exceptions import UnapprovedHostError
from app.tts.factory import create_tts_provider
from app.tts.mock_provider import MockTTSProvider


def _make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "tts_provider": "mock",
        "llm_provider": "mock",
        "anthropic_api_key": None,
        "blaze_api_token": None,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type,call-arg]


def test_factory_returns_mock_provider() -> None:
    settings = _make_settings(tts_provider="mock")
    provider = create_tts_provider(settings)
    assert isinstance(provider, MockTTSProvider)


def test_factory_returns_blaze_provider() -> None:
    settings = _make_settings(tts_provider="blaze", blaze_api_token="token-test")
    provider = create_tts_provider(settings)
    assert isinstance(provider, BlazeBatchTTS)


def test_factory_rejects_unapproved_blaze_host() -> None:
    settings = _make_settings(
        tts_provider="blaze",
        blaze_api_token="token-test",
        blaze_base_url="https://evil.example.com",
        approved_ai_hosts=["api.anthropic.com", "api.blaze.vn"],
    )
    with pytest.raises(UnapprovedHostError):
        create_tts_provider(settings)
