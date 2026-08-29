"""`ClaudeLLMProvider` — Mục F2 của Checklist, Mục 10.6 của Plan.

Dùng tool-use để ép Claude trả JSON đúng schema thay vì chỉ dựa vào chỉ dẫn
trong prompt (giảm đáng kể lỗi parse) — tool duy nhất `submit_extraction_result`
có `input_schema` chính là JSON Schema của `ExtractionResult` (C5), và
`tool_choice` ép model luôn gọi tool này.

**Ghi chú (đã trao đổi với người dùng):** Plan.MD yêu cầu `temperature=0`
nhưng SDK `anthropic` 1.2.0 (bản đang dùng) không còn tham số `temperature`
trong `messages.create()` — dòng model Claude 5 không expose sampling
temperature theo cách cũ nữa. Gọi API không truyền tham số này, chấp nhận
theo mặc định của model.
"""

import asyncio
import json
import time
from urllib.parse import urlparse

import anthropic

from app.llm.base import LLMProvider, LLMResponse
from app.llm.exceptions import (
    LLMAPIError,
    LLMConnectionError,
    LLMRateLimitError,
    LLMTimeoutError,
    UnapprovedHostError,
)

_TOOL_NAME = "submit_extraction_result"
_RETRY_BACKOFF_SECONDS = [1.0, 3.0]


class ClaudeLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        result_json_schema: dict,
        approved_hosts: list[str],
        base_url: str | None = None,
        max_tokens: int = 2000,
        timeout_seconds: float = 30.0,
    ) -> None:
        host = urlparse(base_url).hostname if base_url else "api.anthropic.com"
        if host not in approved_hosts:
            raise UnapprovedHostError(host or "")

        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, base_url=base_url, timeout=timeout_seconds
        )
        self._model = model
        self._result_json_schema = result_json_schema
        self._max_tokens = max_tokens

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
            message = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                tools=[
                    {
                        "name": _TOOL_NAME,
                        "description": "Nộp kết quả trích xuất trường dữ liệu theo schema.",
                        "input_schema": self._result_json_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
            )
        except anthropic.APITimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise LLMAPIError(str(exc)) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        raw_text = _extract_tool_input_as_json(message)
        return LLMResponse(
            raw_text=raw_text,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            latency_ms=latency_ms,
            model=message.model,
        )

    async def health_check(self) -> bool:
        try:
            await self._client.messages.create(
                model=self._model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        except anthropic.AnthropicError:
            return False
        return True


def _extract_tool_input_as_json(message: anthropic.types.Message) -> str:
    """Lấy `input` (dict) của tool-use block đầu tiên, trả về dưới dạng chuỗi JSON.

    Trả chuỗi (không phải dict) để giữ interface `LLMResponse.raw_text` thống
    nhất với `MockLLMProvider` — tầng gọi luôn parse bằng
    `parse_extraction_result` (C5) bất kể provider nào tạo ra nó.
    """
    for block in message.content:
        if block.type == "tool_use":
            return json.dumps(block.input, ensure_ascii=False)
    raise LLMAPIError("Claude không trả về tool_use block nào — không có kết quả để parse.")
