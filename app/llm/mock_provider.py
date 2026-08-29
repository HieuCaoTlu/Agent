"""`MockLLMProvider` — Mục F1 của Checklist.

Trả kết quả cố định (không gọi mạng) theo transcript đầu vào — dùng để phát
triển/test khi chưa có API key thật, hoặc để test luồng nghiệp vụ mà không
phụ thuộc vào việc Claude API có sẵn sàng hay không.
"""

import json
import time

from app.llm.base import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Provider giả lập — trả một `ExtractionResult` rỗng (mọi trường "missing").

    Không cố gắng "hiểu" transcript — mục đích là kiểm tra luồng gọi/parse
    hoạt động đúng đầu-cuối, không phải kiểm tra chất lượng trích xuất (việc
    đó thuộc về test tích hợp với Claude thật).
    """

    def __init__(self, model: str = "mock-llm") -> None:
        self._model = model

    async def extract(self, system_prompt: str, user_message: str) -> LLMResponse:
        start = time.monotonic()
        raw_text = json.dumps({"fields": [], "observations": []}, ensure_ascii=False)
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            raw_text=raw_text,
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
            model=self._model,
        )

    async def health_check(self) -> bool:
        return True
