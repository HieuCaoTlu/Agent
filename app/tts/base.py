"""Trừu tượng hóa tầng TTS — Mục H1 của Checklist.

`TTSProvider` là interface duy nhất mà tầng service phụ thuộc vào — không
service nào được import thẳng SDK/giao thức Blaze cụ thể.

**Lược bỏ khỏi MVP (H2):** TTS real-time (WebSocket) — chỉ dùng batch, vì
đọc lại tại quầy không yêu cầu độ trễ thấp như hội thoại.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SynthesisResult:
    audio_bytes: bytes
    audio_format: str
    provider: str


class TTSProvider(ABC):
    """Interface một provider TTS phải hiện thực."""

    @abstractmethod
    async def synthesize(self, text: str) -> SynthesisResult:
        """Chuyển văn bản thành audio (batch — không streaming, xem ghi chú module)."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Kiểm tra provider có sẵn sàng phục vụ không (dùng cho GET /health)."""
        ...
