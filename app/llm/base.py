"""Trừu tượng hóa tầng LLM — Mục F1 của Checklist.

`LLMProvider` là interface duy nhất mà tầng service (F/I) phụ thuộc vào —
không service nào được import thẳng SDK Anthropic hay bất kỳ SDK provider cụ
thể nào, để có thể đổi provider (hoặc dùng mock khi phát triển/test) mà không
sửa code gọi.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    """Kết quả thô từ một lần gọi LLM — chưa parse/validate thành `ExtractionResult`.

    Tách riêng khỏi `ExtractionResult` (schema nghiệp vụ, C5) vì đây là dữ liệu
    kỹ thuật về bản thân lệnh gọi (dùng để log, tính chi phí, đo hiệu năng).
    """

    raw_text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str


class LLMProvider(ABC):
    """Interface một provider LLM phải hiện thực."""

    @abstractmethod
    async def extract(self, system_prompt: str, user_message: str) -> LLMResponse:
        """Gọi LLM với system prompt và user message, trả về kết quả thô.

        Không parse/validate JSON ở đây — đó là việc của tầng gọi
        (`app/domain/extraction_schema.parse_extraction_result`, C5) để giữ
        provider chỉ chịu trách nhiệm về I/O mạng.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Kiểm tra provider có sẵn sàng phục vụ không (dùng cho GET /health)."""
        ...
