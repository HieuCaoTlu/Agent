"""`GeminiLLMProvider` — provider LLM thứ 3 (bên cạnh mock/claude, Mục F1-F2).

Dùng structured output (`response_mime_type="application/json"` +
`response_schema=ExtractionResult`) thay vì function-calling như
`ClaudeLLMProvider` — Gemini SDK (`google-genai`) nhận thẳng model Pydantic
làm schema, tự xử lý `$defs`/`anyOf` phát sinh từ `model_json_schema()`
(C5) mà không cần tự chuyển đổi sang dạng OpenAPI-subset của Gemini.
"""

import asyncio
import time
from urllib.parse import urlparse

from google import genai
from google.genai import errors, types

from app.domain.extraction_schema import ExtractionResult
from app.llm.base import LLMProvider, LLMResponse
from app.llm.exceptions import (
    LLMAPIError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
    UnapprovedHostError,
)

_RETRY_BACKOFF_SECONDS = [1.0, 3.0]
_RATE_LIMIT_STATUS = 429


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        approved_hosts: list[str],
        base_url: str | None = None,
        max_output_tokens: int = 2000,
        timeout_seconds: float = 30.0,
    ) -> None:
        host = urlparse(base_url).hostname if base_url else "generativelanguage.googleapis.com"
        if host not in approved_hosts:
            raise UnapprovedHostError(host or "")

        http_options = types.HttpOptions(
            base_url=base_url, timeout=int(timeout_seconds * 1000)
        )
        self._client = genai.Client(api_key=api_key, http_options=http_options)
        self._model = model
        self._max_output_tokens = max_output_tokens

    async def extract(self, system_prompt: str, user_message: str) -> LLMResponse:
        last_error: Exception | None = None
        for backoff in [0.0, *_RETRY_BACKOFF_SECONDS]:
            if backoff:
                await asyncio.sleep(backoff)
            try:
                return await self._call_once(system_prompt, user_message)
            except (LLMTimeoutError, LLMRateLimitError, LLMConnectionError) as exc:
                last_error = exc
                continue
            except LLMAPIError:
                raise  # lỗi API cố định (vd. bad request) — retry vô ích, ném ngay
        assert last_error is not None  # vòng lặp trên luôn set trước khi hết attempt
        raise last_error

    async def _call_once(self, system_prompt: str, user_message: str) -> LLMResponse:
        start = time.monotonic()
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=ExtractionResult,
                    max_output_tokens=self._max_output_tokens,
                    # Không dùng function-calling (chỉ structured output qua
                    # response_schema) — tắt tường minh để SDK không cảnh báo
                    # "Direct use of automatic function calling is not recommended".
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        except errors.ClientError as exc:
            if exc.code == _RATE_LIMIT_STATUS:
                raise LLMRateLimitError(str(exc)) from exc
            raise LLMAPIError(str(exc)) from exc
        except errors.ServerError as exc:
            raise LLMConnectionError(str(exc)) from exc
        except TimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except (ConnectionError, OSError) as exc:
            raise LLMConnectionError(str(exc)) from exc

        if response.text is None:
            raise LLMAPIError("Gemini không trả về nội dung nào — không có kết quả để parse.")

        latency_ms = int((time.monotonic() - start) * 1000)
        usage = response.usage_metadata
        return LLMResponse(
            raw_text=response.text,
            input_tokens=usage.prompt_token_count if usage else 0,
            output_tokens=usage.candidates_token_count if usage else 0,
            latency_ms=latency_ms,
            model=self._model,
        )

    async def health_check(self) -> bool:
        try:
            await self._client.aio.models.generate_content(
                model=self._model,
                contents="ping",
                config=types.GenerateContentConfig(
                    max_output_tokens=1,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        disable=True
                    ),
                ),
            )
        except errors.APIError:
            return False
        return True
