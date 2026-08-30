"""`VoiceService` — Mục I4 của Checklist.

Điều phối vòng đời một lượt ghi âm: tạo lượt (`start_recording`), nhận audio
theo từng chunk và chuyển tiếp cho STT (`process_audio_chunk`), lưu transcript
cuối cùng (`finalize_turn`), xóa buffer audio khỏi Redis với bằng chứng
`audio_deleted_at` (NT-6), và cho cán bộ sửa/gắn cờ transcript (UC5).

**Cầu nối `asyncio.Queue` (quyết định đã hỏi người dùng):**
`STTProvider.transcribe_stream()` (G1) nhận một `AsyncIterator[bytes]` — một
luồng audio hoàn chỉnh — trong khi API thực tế của tầng gọi (WebSocket, K) đẩy
audio tới theo từng chunk rời rạc qua nhiều lần gọi `process_audio_chunk()`.
Hai giao diện không khớp trực tiếp, nên `VoiceService` giữ một
`asyncio.Queue[bytes | None]` cho mỗi lượt đang ghi âm: `process_audio_chunk()`
bỏ chunk vào queue (đồng thời lưu vào buffer Redis); một task nền đọc từ
queue — bọc thành `AsyncIterator[bytes]` — để đưa vào `transcribe_stream()`.

**Đẩy kết quả real-time (quyết định đã hỏi người dùng, bổ sung cho K):**
`_consume_stream()` vừa append từng `TranscriptChunk` vào `_ActiveTurn.results`
(dùng cho `get_partial_results()` — đọc kết quả gom được tới hiện tại, không
cần real-time) vừa `put()` ngay vào `_ActiveTurn.results_queue` — một
`asyncio.Queue[TranscriptChunk | None]` riêng. `stream_results(turn_id)` bọc
queue đó thành `AsyncIterator[TranscriptChunk]` để WebSocket handler (K)
`async for` trực tiếp, nhận kết quả ngay khi STT trả về — không cần polling.
`None` trong `results_queue` là tín hiệu kết thúc luồng, đẩy bởi
`_consume_stream()` khi `transcribe_stream()` kết thúc tự nhiên (STT đã xử lý
xong toàn bộ audio đã nhận, không phải do `finalize_turn()` gọi tới).
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import redis.asyncio as redis

from app.domain.audit_action import AuditAction
from app.domain.exceptions import DomainError
from app.models.voice import VoiceTurn
from app.repositories.audit_repository import AuditRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.voice_turn_repository import VoiceTurnRepository
from app.stt.base import STTProvider, TranscriptChunk

_AUDIO_BUFFER_KEY_PREFIX = "audio_buffer:"


class SessionNotFoundForVoice(DomainError):
    """Ném ra khi `session_id` không tồn tại."""

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Không tìm thấy phiên có mã '{session_id}'.")


class VoiceTurnNotFound(DomainError):
    """Ném ra khi `turn_id` không tồn tại (hoặc không thuộc phiên đang thao tác)."""

    def __init__(self, turn_id: uuid.UUID) -> None:
        self.turn_id = turn_id
        super().__init__(f"Không tìm thấy lượt thoại có mã '{turn_id}'.")


class _ActiveTurn:
    """Trạng thái nội bộ của một lượt đang ghi âm — queue audio vào + task nền
    + kết quả gom được (polling) + queue kết quả ra (real-time, dùng cho K)."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.results: list[TranscriptChunk] = []
        self.results_queue: asyncio.Queue[TranscriptChunk | None] = asyncio.Queue()
        self.task: asyncio.Task[None] | None = None


async def _queue_to_async_iterator(queue: asyncio.Queue[bytes | None]) -> AsyncIterator[bytes]:
    """Bọc `asyncio.Queue` thành `AsyncIterator[bytes]` — dừng khi gặp `None`."""
    while True:
        chunk = await queue.get()
        if chunk is None:
            return
        yield chunk


async def _results_queue_to_async_iterator(
    queue: asyncio.Queue[TranscriptChunk | None],
) -> AsyncIterator[TranscriptChunk]:
    """Bọc `asyncio.Queue` kết quả thành `AsyncIterator[TranscriptChunk]` — dừng khi gặp `None`."""
    while True:
        result = await queue.get()
        if result is None:
            return
        yield result


class VoiceService:
    def __init__(
        self,
        session_repository: SessionRepository,
        voice_turn_repository: VoiceTurnRepository,
        audit_repository: AuditRepository,
        stt_provider: STTProvider,
        redis_client: redis.Redis,
        audio_buffer_ttl_seconds: int = 120,
    ) -> None:
        self._sessions = session_repository
        self._voice_turns = voice_turn_repository
        self._audit = audit_repository
        self._stt = stt_provider
        self._redis = redis_client
        self._audio_buffer_ttl_seconds = audio_buffer_ttl_seconds
        self._active_turns: dict[uuid.UUID, _ActiveTurn] = {}

    async def start_recording(self, session_id: uuid.UUID) -> VoiceTurn:
        """Bấm nút hỏi: tạo lượt thoại mới, cấp `turn_number`, mở queue nhận audio."""
        await self._get_session_or_raise(session_id)

        voice_turn = VoiceTurn(session_id=session_id)
        await self._voice_turns.add(voice_turn)

        active = _ActiveTurn()
        active.task = asyncio.create_task(self._consume_stream(voice_turn.id, active))
        self._active_turns[voice_turn.id] = active

        await self._audit.append(
            actor_type="staff",
            action="recording_started",
            session_id=session_id,
            detail={"turn_id": str(voice_turn.id), "turn_number": voice_turn.turn_number},
        )
        return voice_turn

    async def process_audio_chunk(self, turn_id: uuid.UUID, chunk: bytes) -> None:
        """Đẩy một chunk audio vào queue của lượt đang ghi âm, đồng thời lưu buffer Redis.

        Không trả kết quả partial/final trực tiếp — tầng gọi (K, WebSocket) đọc
        kết quả gom được qua `get_partial_results(turn_id)`, vì `transcribe_stream()`
        chạy trong task nền độc lập với lời gọi này.
        """
        active = self._active_turns.get(turn_id)
        if active is None:
            raise VoiceTurnNotFound(turn_id)

        await active.queue.put(chunk)
        await self._redis.rpush(_buffer_key(turn_id), chunk)
        await self._redis.expire(_buffer_key(turn_id), self._audio_buffer_ttl_seconds)

    def get_partial_results(self, turn_id: uuid.UUID) -> list[TranscriptChunk]:
        """Kết quả partial/final đã gom được cho đến hiện tại (snapshot, không real-time)."""
        active = self._active_turns.get(turn_id)
        if active is None:
            raise VoiceTurnNotFound(turn_id)
        return active.results

    def stream_results(self, turn_id: uuid.UUID) -> AsyncIterator[TranscriptChunk]:
        """`TranscriptChunk` (partial/final) ngay khi STT trả về — dùng cho K.

        WebSocket handler `async for result in service.stream_results(turn_id)`
        để đẩy `partial`/`final` về client thời gian thực, không cần polling
        `get_partial_results()`. Dừng tự nhiên khi `_consume_stream()` kết
        thúc (STT xử lý xong toàn bộ audio đã nhận tính tới lúc đó).
        """
        active = self._active_turns.get(turn_id)
        if active is None:
            raise VoiceTurnNotFound(turn_id)
        return _results_queue_to_async_iterator(active.results_queue)

    async def close_recording_stream(self, turn_id: uuid.UUID) -> list[TranscriptChunk]:
        """Đóng luồng audio (đẩy `None` vào queue), đợi task nền xử lý xong
        toàn bộ audio đã nhận, trả về kết quả gom được đầy đủ (kể cả chunk
        `is_final` cuối cùng — chỉ phát sinh SAU khi luồng đóng, xem docstring
        module).

        Tách khỏi `finalize_turn()` vì thứ tự đúng là: đóng luồng trước (để
        STT kịp trả chunk cuối) → tầng gọi (K) tự ghép text cuối cùng → mới
        gọi `finalize_turn()` để lưu. Gọi `get_partial_results()`/text trước
        khi đóng luồng có nguy cơ thiếu chunk cuối (race condition).
        An toàn khi gọi nhiều lần hoặc khi turn không còn active (trả `[]`).
        """
        active = self._active_turns.pop(turn_id, None)
        if active is None:
            return []
        await active.queue.put(None)
        if active.task is not None:
            await active.task
        return active.results

    async def finalize_turn(self, turn_id: uuid.UUID, transcript: str) -> VoiceTurn:
        """Kết thúc lượt ghi âm: lưu transcript cuối cùng.

        Đóng luồng audio còn dang dở nếu tầng gọi chưa tự gọi
        `close_recording_stream()` trước (tương thích ngược — polling đơn
        giản không cần quan tâm race condition ở trên vẫn gọi được thẳng
        method này). Không tự xóa buffer Redis ở đây — `delete_audio_buffer()`
        (gọi riêng ngay sau khi tầng trên xác nhận đã nhận transcript) mới là
        nơi ghi bằng chứng `audio_deleted_at` (NT-6).
        """
        voice_turn = await self._voice_turns.get(turn_id)
        if voice_turn is None:
            raise VoiceTurnNotFound(turn_id)

        await self.close_recording_stream(turn_id)

        voice_turn.raw_transcript = transcript
        await self._voice_turns.update(voice_turn)

        await self._audit.append(
            actor_type="system",
            action="transcript_received",
            session_id=voice_turn.session_id,
            detail={"turn_id": str(turn_id)},
        )
        return voice_turn

    async def delete_audio_buffer(self, turn_id: uuid.UUID) -> VoiceTurn:
        """Xóa buffer audio khỏi Redis, ghi `audio_deleted_at` làm bằng chứng (NT-6)."""
        voice_turn = await self._voice_turns.get(turn_id)
        if voice_turn is None:
            raise VoiceTurnNotFound(turn_id)

        await self._redis.delete(_buffer_key(turn_id))
        voice_turn.audio_deleted_at = datetime.now(UTC)
        await self._voice_turns.update(voice_turn)

        await self._audit.append(
            actor_type="system",
            action="audio_buffer_deleted",
            session_id=voice_turn.session_id,
            detail={"turn_id": str(turn_id)},
        )
        return voice_turn

    async def edit_transcript(
        self, turn_id: uuid.UUID, new_text: str, staff_name: str
    ) -> VoiceTurn:
        """Cán bộ sửa lại transcript đã nhận diện (UC5) — ghi vào `edited_transcript`."""
        voice_turn = await self._voice_turns.get(turn_id)
        if voice_turn is None:
            raise VoiceTurnNotFound(turn_id)

        voice_turn.edited_transcript = new_text
        await self._voice_turns.update(voice_turn)

        await self._audit.append(
            actor_type="staff",
            action="transcript_edited_by_staff",
            session_id=voice_turn.session_id,
            actor_id=staff_name,
            detail={"turn_id": str(turn_id)},
        )
        return voice_turn

    async def flag_transcript(self, turn_id: uuid.UUID, staff_name: str) -> VoiceTurn:
        """Cán bộ chủ động gắn cờ transcript "chưa rõ" (UC5), ghi audit tương ứng."""
        voice_turn = await self._voice_turns.get(turn_id)
        if voice_turn is None:
            raise VoiceTurnNotFound(turn_id)

        voice_turn.flagged_by_staff = True
        await self._voice_turns.update(voice_turn)

        await self._audit.append(
            actor_type="staff",
            action=AuditAction.TRANSCRIPT_FLAGGED_BY_STAFF.value,
            session_id=voice_turn.session_id,
            actor_id=staff_name,
            detail={"turn_id": str(turn_id)},
        )
        return voice_turn

    async def _consume_stream(self, turn_id: uuid.UUID, active: _ActiveTurn) -> None:
        """Task nền: đọc queue như `AsyncIterator[bytes]`, gom `TranscriptChunk` từ STT.

        Mỗi kết quả vừa append vào `results` (polling) vừa `put()` ngay vào
        `results_queue` (real-time, K) — hai đường tiêu thụ độc lập, không
        loại trừ nhau. Đẩy `None` vào `results_queue` khi `transcribe_stream()`
        kết thúc để `stream_results()` dừng đúng lúc.
        """
        audio_stream = _queue_to_async_iterator(active.queue)
        async for result in self._stt.transcribe_stream(audio_stream):
            active.results.append(result)
            await active.results_queue.put(result)
        await active.results_queue.put(None)

    async def _get_session_or_raise(self, session_id: uuid.UUID) -> None:
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundForVoice(session_id)


def _buffer_key(turn_id: uuid.UUID) -> str:
    return f"{_AUDIO_BUFFER_KEY_PREFIX}{turn_id}"
