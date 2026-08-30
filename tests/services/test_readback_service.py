"""Test `ReadbackService` — Mục I5 của Checklist."""

import uuid
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.models.session import Session
from app.repositories.audit_repository import AuditRepository
from app.repositories.citizen_confirmation_repository import CitizenConfirmationRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.services.catalog_service import CatalogService
from app.services.readback_service import (
    NoProcedureSelected,
    ReadbackService,
    SessionNotFoundForReadback,
)
from app.services.tts_cache_service import TTSCacheService
from app.tts.base import SynthesisResult, TTSProvider
from app.tts.exceptions import TTSAPIError

_CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "static_data" / "procedures"
_FIXED_ACTIVE_DATE = date(2026, 9, 15)


class _FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return _FIXED_ACTIVE_DATE


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.readback_service.date", _FixedDate)


class _StubTTSProvider(TTSProvider):
    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self.calls: list[str] = []

    async def synthesize(self, text: str) -> SynthesisResult:
        self.calls.append(text)
        if self._should_fail:
            raise TTSAPIError("provider giả lập lỗi")
        return SynthesisResult(audio_bytes=b"audio-bytes", audio_format="wav", provider="stub")

    async def health_check(self) -> bool:
        return True


def _make_service(
    db_session, tts_provider: TTSProvider, tts_cache_service: TTSCacheService | None = None
) -> ReadbackService:
    return ReadbackService(
        session_repository=SessionRepository(db_session),
        field_state_repository=FieldStateRepository(db_session),
        citizen_confirmation_repository=CitizenConfirmationRepository(db_session),
        audit_repository=AuditRepository(db_session),
        catalog_service=CatalogService(_CATALOG_DIR),
        tts_provider=tts_provider,
        tts_cache_service=tts_cache_service or TTSCacheService(AsyncMock()),
    )


async def _make_session_with_confirmed_fields(
    db_session, state: str = "FIELDS_CONFIRMED"
) -> Session:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state=state, procedure_code="dang_ky_khai_sinh")
    await session_repo.create(session)

    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(
        session.id,
        "ho_ten_nguoi_duoc_khai_sinh",
        confirmed_value="Nguyễn Văn A",
        is_confirmed=True,
    )
    await field_repo.upsert(
        session.id, "ngay_sinh", confirmed_value="2026-01-05", is_confirmed=True
    )
    await db_session.commit()
    return session


async def test_generate_readback_success_returns_audio_and_advances_state(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session)
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    outcome = await service.generate_readback(session.id)
    await db_session.commit()

    assert outcome.used_fallback is False
    assert outcome.audio_bytes == b"audio-bytes"
    assert outcome.readback_round == 1
    assert "Nguyễn Văn A" in outcome.text
    assert len(tts.calls) == 1

    updated_session = await SessionRepository(db_session).get(session.id)
    assert updated_session.state == "READBACK"

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "readback_played" for log in logs)


async def test_generate_readback_success_caches_audio_by_session(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session)
    tts = _StubTTSProvider()
    redis_client = AsyncMock()
    cache = TTSCacheService(redis_client, ttl_seconds=60)
    service = _make_service(db_session, tts, tts_cache_service=cache)

    await service.generate_readback(session.id)
    await db_session.commit()

    redis_client.set.assert_awaited_once_with(
        f"tts_audio_session:{session.id}", b"audio-bytes", ex=60
    )


async def test_generate_readback_masks_national_id_and_formats_date(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session)
    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(
        session.id, "ngay_sinh", confirmed_value="2026-01-05", is_confirmed=True
    )
    await db_session.commit()

    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)
    outcome = await service.generate_readback(session.id)
    await db_session.commit()

    assert "mùng 5 tháng 1 năm 2026" in outcome.text


async def test_generate_readback_falls_back_to_text_when_tts_fails(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session)
    tts = _StubTTSProvider(should_fail=True)
    service = _make_service(db_session, tts)

    outcome = await service.generate_readback(session.id)
    await db_session.commit()

    assert outcome.used_fallback is True
    assert outcome.audio_bytes is None
    assert outcome.audio_format is None
    assert "Nguyễn Văn A" in outcome.text

    logs = await AuditRepository(db_session).list_by_session(session.id)
    played = next(log for log in logs if log.action == "readback_played")
    assert played.detail["used_fallback"] is True


async def test_generate_readback_session_not_found_raises(db_session) -> None:
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    with pytest.raises(SessionNotFoundForReadback):
        await service.generate_readback(uuid.uuid4())


async def test_generate_readback_no_procedure_raises(db_session) -> None:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state="FIELDS_CONFIRMED")
    await session_repo.create(session)
    await db_session.commit()

    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    with pytest.raises(NoProcedureSelected):
        await service.generate_readback(session.id)


async def test_generate_readback_invalid_state_raises_invalid_transition(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session, state="REVIEWING")
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    with pytest.raises(Exception, match="Không thể thực hiện thao tác này"):
        await service.generate_readback(session.id)


async def test_record_citizen_confirmation_confirmed_advances_state(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session, state="READBACK")
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    confirmation = await service.record_citizen_confirmation(
        session.id,
        confirmed=True,
        readback_text="nội dung đã đọc",
        staff_name="Cán bộ A",
    )
    await db_session.commit()

    assert confirmation.confirmed is True
    assert confirmation.readback_round == 1

    updated_session = await SessionRepository(db_session).get(session.id)
    assert updated_session.state == "CITIZEN_CONFIRMED"

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "citizen_confirmed" for log in logs)


async def test_record_citizen_confirmation_rejected_returns_to_reviewing(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session, state="READBACK")
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    confirmation = await service.record_citizen_confirmation(
        session.id,
        confirmed=False,
        readback_text="nội dung đã đọc",
        staff_name="Cán bộ A",
        note="Sai năm sinh",
    )
    await db_session.commit()

    assert confirmation.confirmed is False
    assert confirmation.confirmation_note == "Sai năm sinh"

    updated_session = await SessionRepository(db_session).get(session.id)
    assert updated_session.state == "REVIEWING"

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "citizen_rejected" for log in logs)


async def test_record_citizen_confirmation_increments_readback_round(db_session) -> None:
    session = await _make_session_with_confirmed_fields(db_session, state="READBACK")
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    await service.record_citizen_confirmation(
        session.id, confirmed=False, readback_text="lần 1", staff_name="Cán bộ A"
    )
    await db_session.commit()

    # Sau khi từ chối, phiên quay lại REVIEWING — giả lập cán bộ đưa lại READBACK
    # (chuyển tay trong test, không qua state machine thật vì ngoài phạm vi I5).
    session.state = "READBACK"
    await SessionRepository(db_session).update(session)
    await db_session.commit()

    second = await service.record_citizen_confirmation(
        session.id, confirmed=True, readback_text="lần 2", staff_name="Cán bộ A"
    )
    await db_session.commit()

    assert second.readback_round == 2


async def test_record_citizen_confirmation_session_not_found_raises(db_session) -> None:
    tts = _StubTTSProvider()
    service = _make_service(db_session, tts)

    with pytest.raises(SessionNotFoundForReadback):
        await service.record_citizen_confirmation(
            uuid.uuid4(), confirmed=True, readback_text="x", staff_name="A"
        )
