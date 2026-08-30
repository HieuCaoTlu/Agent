"""Factory chọn `LLMProvider` theo cấu hình — Mục F1 của Checklist.

Nơi duy nhất quyết định dùng provider thật hay mock — service khác luôn nhận
một `LLMProvider` đã dựng sẵn (dependency injection), không tự gọi factory.
"""

from app.config import Settings
from app.domain.extraction_schema import extraction_result_json_schema
from app.llm.base import LLMProvider
from app.llm.claude_provider import ClaudeLLMProvider
from app.llm.gemini_provider import GeminiLLMProvider
from app.llm.mock_provider import MockLLMProvider


def create_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockLLMProvider()

    if settings.llm_provider == "gemini":
        assert settings.gemini_api_key is not None  # Settings validator đã bắt buộc khi 'gemini'
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            approved_hosts=settings.approved_ai_hosts,
        )

    assert settings.anthropic_api_key is not None  # Settings validator đã bắt buộc khi 'claude'
    return ClaudeLLMProvider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        result_json_schema=extraction_result_json_schema(),
        approved_hosts=settings.approved_ai_hosts,
    )
