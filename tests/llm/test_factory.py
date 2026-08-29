from app.config import Settings
from app.llm.claude_provider import ClaudeLLMProvider
from app.llm.factory import create_llm_provider
from app.llm.mock_provider import MockLLMProvider


def _make_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "llm_provider": "mock",
        "anthropic_api_key": None,
        "blaze_api_token": "token",
    }
    defaults.update(overrides)
    # _env_file=None: không đọc .env thật của máy dev (có thể chứa key thật) —
    # test phải hoàn toàn tất định chỉ dựa vào tham số truyền vào.
    return Settings(_env_file=None, **defaults)  # type: ignore[arg-type,call-arg]


def test_factory_returns_mock_provider() -> None:
    settings = _make_settings(llm_provider="mock")
    provider = create_llm_provider(settings)
    assert isinstance(provider, MockLLMProvider)


def test_factory_returns_claude_provider() -> None:
    settings = _make_settings(llm_provider="claude", anthropic_api_key="sk-test-key")
    provider = create_llm_provider(settings)
    assert isinstance(provider, ClaudeLLMProvider)
