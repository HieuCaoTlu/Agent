"""`MockSTTProvider` — Mục G1 của Checklist.

Phát lại transcript có sẵn theo kịch bản — dùng để phát triển/test khi chưa
có Blaze API token thật, không mở kết nối mạng nào.
"""

from collections.abc import AsyncIterator

from app.stt.base import STTProvider, TranscriptChunk


class MockSTTProvider(STTProvider):
    """Phát lại một kịch bản transcript cố định, bất kể nội dung audio nhận được.

    `script`: danh sách chuỗi, mỗi phần tử là một "final chunk" sẽ được phát ra
    tuần tự mỗi khi `transcribe_stream()` được gọi (không tiêu thụ audio thật).
    """

    def __init__(self, script: list[str] | None = None) -> None:
        self._script = script or ["Đây là transcript giả lập cho môi trường phát triển."]

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        async for _ in audio_stream:
            pass  # tiêu thụ hết audio đầu vào, không xử lý gì (mock không cần audio thật)
        for text in self._script:
            yield TranscriptChunk(text=text, is_final=True, provider="mock")

    async def transcribe_file(self, audio_bytes: bytes) -> TranscriptChunk:
        text = self._script[0] if self._script else ""
        return TranscriptChunk(text=text, is_final=True, provider="mock")

    async def health_check(self) -> bool:
        return True
