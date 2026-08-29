import pytest

from app.config import Settings
from app.stt.blaze_provider import BlazeSTTProvider
from app.stt.exceptions import UnapprovedHostError
from app.stt.factory import create_stt_provider
from app.stt.mock_provider import MockSTTProvider


def _make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "stt_provider": "mock",
        "llm_provider": "mock",
        "anthropic_api_key": None,
        "blaze_api_token": None,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type,call-arg]


def test_factory_returns_mock_provider() -> None:
    settings = _make_settings(stt_provider="mock")
    provider = create_stt_provider(settings)
    assert isinstance(provider, MockSTTProvider)


def test_factory_returns_blaze_provider() -> None:
    settings = _make_settings(stt_provider="blaze", blaze_api_token="token-test")
    provider = create_stt_provider(settings)
    assert isinstance(provider, BlazeSTTProvider)


def test_factory_rejects_unapproved_blaze_host() -> None:
    settings = _make_settings(
        stt_provider="blaze",
        blaze_api_token="token-test",
        blaze_base_url="https://evil.example.com",
        approved_ai_hosts=["api.anthropic.com", "api.blaze.vn"],
    )
    with pytest.raises(UnapprovedHostError):
        create_stt_provider(settings)
