import json

from app.domain.extraction_schema import parse_extraction_result
from app.llm.mock_provider import MockLLMProvider


async def test_extract_returns_parseable_empty_result() -> None:
    provider = MockLLMProvider()
    response = provider.extract("system", "user")
    response = await response

    result = parse_extraction_result(response.raw_text)
    assert result.fields == []
    assert response.input_tokens == 0
    assert response.output_tokens == 0
    assert response.model == "mock-llm"


async def test_health_check_always_true() -> None:
    provider = MockLLMProvider()
    assert await provider.health_check() is True


async def test_raw_text_is_valid_json() -> None:
    provider = MockLLMProvider()
    response = await provider.extract("system", "user")
    json.loads(response.raw_text)  # không ném exception
