"""Trừu tượng hóa tầng STT — Mục G1 của Checklist.

`STTProvider` là interface duy nhất mà tầng service phụ thuộc vào — không
service nào được import thẳng SDK/giao thức Blaze cụ thể.

**Quyết định (đã ghi trong Checklist, Mục G):** bỏ qua cơ chế ngưỡng
`confidence` cho STT. Tài liệu Blaze không cam kết trả field này, nên
`TranscriptChunk` KHÔNG có field `confidence` — việc đánh giá "câu nói có rõ
hay không" chuyển hoàn toàn cho cán bộ (xem UC5, GD-6).
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    is_final: bool
    provider: str
    latency_ms: int | None = None


class STTProvider(ABC):
    """Interface một provider STT phải hiện thực."""

    @abstractmethod
    def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        """Nhận luồng audio PCM 16kHz/mono/16-bit, trả về luồng transcript (partial + final).

        Trả về async iterator (không phải coroutine) — tầng gọi lặp bằng
        `async for chunk in provider.transcribe_stream(...)`.
        """
        ...

    @abstractmethod
    async def transcribe_file(self, audio_bytes: bytes) -> TranscriptChunk:
        """Nhận toàn bộ file audio, trả về một transcript hoàn chỉnh (dùng cho UC4)."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Kiểm tra provider có sẵn sàng phục vụ không (dùng cho GET /health)."""
        ...
