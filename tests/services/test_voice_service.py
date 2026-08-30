"""Test `VoiceService` — Mục I4 của Checklist."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from app.models.session import Session
from app.repositories.audit_repository import AuditRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.voice_turn_repository import VoiceTurnRepository
from app.services.voice_service import (
    SessionNotFoundForVoice,
    VoiceService,
    VoiceTurnNotFound,
)
from app.stt.base import STTProvider, TranscriptChunk


class _EchoSTTProvider(STTProvider):
    """Trả về một `TranscriptChunk` (partial) cho mỗi chunk audio nhận được,
    rồi một chunk `is_final=True` khi luồng kết thúc — dùng để kiểm tra
    `VoiceService` chuyển tiếp đúng qua cầu nối asyncio.Queue."""

    def __init__(self) -> None:
        self.received_chunks: list[bytes] = []

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        count = 0
        async for chunk in audio_stream:
            self.received_chunks.append(chunk)
            count += 1
            yield TranscriptChunk(text=f"phần {count}", is_final=False, provider="echo")
        yield TranscriptChunk(text="transcript cuối cùng", is_final=True, provider="echo")

    async def transcribe_file(self, audio_bytes: bytes) -> TranscriptChunk:
        return TranscriptChunk(text="file", is_final=True, provider="echo")

    async def health_check(self) -> bool:
        return True


def _make_redis_mock() -> AsyncMock:
    redis_client = AsyncMock()
    return redis_client


def _make_service(db_session, stt_provider: STTProvider, redis_client: AsyncMock) -> VoiceService:
    return VoiceService(
        session_repository=SessionRepository(db_session),
        voice_turn_repository=VoiceTurnRepository(db_session),
        audit_repository=AuditRepository(db_session),
        stt_provider=stt_provider,
        redis_client=redis_client,
        audio_buffer_ttl_seconds=120,
    )


async def _make_session(db_session) -> Session:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state="LISTENING")
    await session_repo.create(session)
    await db_session.commit()
    return session


async def test_start_recording_creates_turn_and_audit(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()

    assert voice_turn.turn_number == 1
    assert voice_turn.session_id == session.id

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "recording_started" for log in logs)


async def test_start_recording_session_not_found_raises(db_session) -> None:
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    with pytest.raises(SessionNotFoundForVoice):
        await service.start_recording(uuid.uuid4())


async def test_process_audio_chunk_pushes_to_stt_and_redis_buffer(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()

    await service.process_audio_chunk(voice_turn.id, b"chunk-1")
    await service.process_audio_chunk(voice_turn.id, b"chunk-2")
    # Nhường control cho task nền tiêu thụ queue trước khi kiểm tra kết quả.
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    redis_client.rpush.assert_any_await(f"audio_buffer:{voice_turn.id}", b"chunk-1")
    redis_client.rpush.assert_any_await(f"audio_buffer:{voice_turn.id}", b"chunk-2")
    redis_client.expire.assert_any_await(f"audio_buffer:{voice_turn.id}", 120)

    await service.finalize_turn(voice_turn.id, "transcript cuối cùng")
    await db_session.commit()

    assert stt.received_chunks == [b"chunk-1", b"chunk-2"]
    # finalize_turn dọn dẹp queue/task nền — lượt không còn "đang ghi âm" nữa.
    with pytest.raises(VoiceTurnNotFound):
        service.get_partial_results(voice_turn.id)


async def test_process_audio_chunk_unknown_turn_raises(db_session) -> None:
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    with pytest.raises(VoiceTurnNotFound):
        await service.process_audio_chunk(uuid.uuid4(), b"chunk")


async def test_get_partial_results_returns_accumulated_chunks(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()

    await service.process_audio_chunk(voice_turn.id, b"chunk-1")
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    results = service.get_partial_results(voice_turn.id)
    assert any(r.text == "phần 1" for r in results)

    await service.finalize_turn(voice_turn.id, "transcript cuối cùng")
    await db_session.commit()


async def test_finalize_turn_saves_transcript_and_audit(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()

    updated = await service.finalize_turn(voice_turn.id, "Nguyễn Văn A sinh năm 1990")
    await db_session.commit()

    assert updated.raw_transcript == "Nguyễn Văn A sinh năm 1990"

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "transcript_received" for log in logs)


async def test_finalize_turn_unknown_turn_raises(db_session) -> None:
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    with pytest.raises(VoiceTurnNotFound):
        await service.finalize_turn(uuid.uuid4(), "abc")


async def test_delete_audio_buffer_deletes_key_and_stamps_timestamp(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()
    await service.finalize_turn(voice_turn.id, "transcript")
    await db_session.commit()

    updated = await service.delete_audio_buffer(voice_turn.id)
    await db_session.commit()

    assert updated.audio_deleted_at is not None
    redis_client.delete.assert_awaited_once_with(f"audio_buffer:{voice_turn.id}")

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "audio_buffer_deleted" for log in logs)


async def test_delete_audio_buffer_unknown_turn_raises(db_session) -> None:
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    with pytest.raises(VoiceTurnNotFound):
        await service.delete_audio_buffer(uuid.uuid4())


async def test_edit_transcript_updates_edited_field_and_audit(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()
    await service.finalize_turn(voice_turn.id, "transcript gốc")
    await db_session.commit()

    updated = await service.edit_transcript(
        voice_turn.id, "transcript đã sửa", staff_name="Cán bộ A"
    )
    await db_session.commit()

    assert updated.edited_transcript == "transcript đã sửa"
    assert updated.raw_transcript == "transcript gốc"  # không xóa bản gốc

    logs = await AuditRepository(db_session).list_by_session(session.id)
    matching = [log for log in logs if log.action == "transcript_edited_by_staff"]
    assert len(matching) == 1
    assert matching[0].actor_id == "Cán bộ A"


async def test_edit_transcript_unknown_turn_raises(db_session) -> None:
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    with pytest.raises(VoiceTurnNotFound):
        await service.edit_transcript(uuid.uuid4(), "x", staff_name="A")


async def test_flag_transcript_sets_flag_and_writes_audit_action(db_session) -> None:
    session = await _make_session(db_session)
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    voice_turn = await service.start_recording(session.id)
    await db_session.commit()
    await service.finalize_turn(voice_turn.id, "giọng không rõ")
    await db_session.commit()

    updated = await service.flag_transcript(voice_turn.id, staff_name="Cán bộ A")
    await db_session.commit()

    assert updated.flagged_by_staff is True

    logs = await AuditRepository(db_session).list_by_session(session.id)
    matching = [log for log in logs if log.action == "transcript_flagged_by_staff"]
    assert len(matching) == 1
    assert matching[0].actor_id == "Cán bộ A"


async def test_flag_transcript_unknown_turn_raises(db_session) -> None:
    stt = _EchoSTTProvider()
    redis_client = _make_redis_mock()
    service = _make_service(db_session, stt, redis_client)

    with pytest.raises(VoiceTurnNotFound):
        await service.flag_transcript(uuid.uuid4(), staff_name="A")
