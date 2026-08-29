"""`MockTTSProvider` — Mục H1 của Checklist.

Trả một file audio mẫu (không gọi mạng) — dùng để phát triển/test khi chưa
có Blaze API token thật.
"""

from app.tts.base import SynthesisResult, TTSProvider

# WAV header hợp lệ tối thiểu, không có dữ liệu âm thanh thật — đủ để test
# luồng "trả về bytes" mà không cần file mẫu thật trong repo.
_SILENT_WAV_HEADER = (
    b"RIFF" + (36).to_bytes(4, "little") + b"WAVEfmt "
    + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
    + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
    + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
    + (16).to_bytes(2, "little") + b"data" + (0).to_bytes(4, "little")
)


class MockTTSProvider(TTSProvider):
    async def synthesize(self, text: str) -> SynthesisResult:
        return SynthesisResult(
            audio_bytes=_SILENT_WAV_HEADER, audio_format="wav", provider="mock"
        )

    async def health_check(self) -> bool:
        return True
