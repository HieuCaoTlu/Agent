"""Test `SessionService` — Mục I1 của Checklist.

Toàn bộ catalog thật (`app/static_data/procedures/`) có `effective_from`
2026-09-01 — sau ngày hệ thống hiện tại (2026-08-30) lúc viết test này. Các
test cần thủ tục đang hiệu lực dùng `_FIXED_ACTIVE_DATE` (patch `date` trong
module service) thay vì phụ thuộc ngày thật của máy chạy test.
"""

import uuid
from datetime import date
from pathlib import Path

import pytest

from app.domain.exceptions import InvalidTransitionError, ProcedureNotFound
from app.domain.session_state import SessionState
from app.repositories.audit_repository import AuditRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.services.catalog_service import CatalogService
from app.services.session_service import INHERITABLE_FIELDS, SessionNotFound, SessionService

_CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "static_data" / "procedures"
# Sau effective_from (2026-09-01) của mọi thủ tục trong catalog thật.
_FIXED_ACTIVE_DATE = date(2026, 9, 15)


class _FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return _FIXED_ACTIVE_DATE


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cố định `date.today()` trong `session_service` để catalog thật luôn active."""
    monkeypatch.setattr("app.services.session_service.date", _FixedDate)


def _make_service(db_session) -> SessionService:
    return SessionService(
        session_repository=SessionRepository(db_session),
        field_state_repository=FieldStateRepository(db_session),
        audit_repository=AuditRepository(db_session),
        catalog_service=CatalogService(_CATALOG_DIR),
    )


async def test_create_session_starts_in_created_state_and_logs_audit(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Nguyễn Văn A")
    await db_session.commit()

    assert session.state == SessionState.CREATED.value
    assert session.staff_name == "Nguyễn Văn A"
    assert session.mode == "ai_assisted"

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert len(logs) == 1
    assert logs[0].action == "session_created"


async def test_create_session_with_parent(db_session) -> None:
    service = _make_service(db_session)
    parent = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    child = await service.create_session(staff_name="Cán bộ A", parent_session_id=parent.id)
    await db_session.commit()

    assert child.parent_session_id == parent.id


async def test_get_session_state_not_found_raises(db_session) -> None:
    service = _make_service(db_session)
    with pytest.raises(SessionNotFound):
        await service.get_session_state(uuid.uuid4())


async def test_record_consent_sets_flag_and_timestamp(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    updated = await service.record_consent(session.id, True)
    await db_session.commit()

    assert updated.citizen_consent is True
    assert updated.consent_recorded_at is not None


async def test_select_procedure_before_listening_raises(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await service.record_consent(session.id, True)
    await db_session.commit()

    # select_procedure chỉ hợp lệ từ LISTENING theo state machine (C1);
    # phiên mới ở CREATED.
    with pytest.raises(InvalidTransitionError):
        await service.select_procedure(session.id, "dang_ky_khai_sinh")


async def test_start_listening_transitions_created_to_listening(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    updated = await service.start_listening(session.id)
    await db_session.commit()

    assert updated.state == SessionState.LISTENING.value


async def test_start_listening_from_wrong_state_raises(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await service.start_listening(session.id)
    await db_session.commit()

    with pytest.raises(InvalidTransitionError):
        await service.start_listening(session.id)


async def test_select_procedure_success_after_listening(db_session) -> None:
    from app.domain.session_state import SessionEvent, transition

    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    session.state = transition(SessionState(session.state), SessionEvent.START_LISTENING).value
    await SessionRepository(db_session).update(session)
    await db_session.commit()

    updated = await service.select_procedure(session.id, "dang_ky_khai_sinh")
    await db_session.commit()

    assert updated.state == SessionState.PROCEDURE_SELECTED.value
    assert updated.procedure_code == "dang_ky_khai_sinh"

    field_states = await FieldStateRepository(db_session).list_by_session(session.id)
    catalog = CatalogService(_CATALOG_DIR)
    schema = catalog.get_field_schema("dang_ky_khai_sinh", _FIXED_ACTIVE_DATE)
    expected_fields = {f.name for f in schema}
    assert {fs.field_name for fs in field_states} == expected_fields

    # E (hoàn thiện 30/8/2026): mọi lần chuyển trạng thái phiên phải có audit log.
    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "procedure_selected" for log in logs)


async def test_select_procedure_unknown_code_raises(db_session) -> None:
    from app.domain.session_state import SessionEvent, transition

    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    session.state = transition(SessionState(session.state), SessionEvent.START_LISTENING).value
    await SessionRepository(db_session).update(session)
    await db_session.commit()

    with pytest.raises(ProcedureNotFound):
        await service.select_procedure(session.id, "khong_ton_tai")


async def test_cancel_session_from_any_non_terminal_state(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    cancelled = await service.cancel_session(session.id, reason="Người dân đổi ý")
    await db_session.commit()

    assert cancelled.state == SessionState.CANCELLED.value
    assert cancelled.cancel_reason == "Người dân đổi ý"


async def test_cancel_session_already_terminal_raises(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await service.cancel_session(session.id)
    await db_session.commit()

    with pytest.raises(InvalidTransitionError):
        await service.cancel_session(session.id)


async def test_complete_session_requires_citizen_confirmed_state(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    with pytest.raises(InvalidTransitionError):
        await service.complete_session(session.id, dossier_code="HS-001")


async def test_complete_session_success(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")

    # Đẩy thủ công qua toàn bộ state machine tới CITIZEN_CONFIRMED để test complete().
    from app.domain.session_state import SessionEvent, transition

    for event in (
        SessionEvent.START_LISTENING,
        SessionEvent.SELECT_PROCEDURE,
        SessionEvent.REQUEST_EXTRACTION,
        SessionEvent.EXTRACTION_SUCCESS,
        SessionEvent.OPEN_REVIEW,
        SessionEvent.ALL_REQUIRED_CONFIRMED,
        SessionEvent.TRIGGER_READBACK,
        SessionEvent.CITIZEN_CONFIRMED,
    ):
        session.state = transition(SessionState(session.state), event).value
    await SessionRepository(db_session).update(session)
    await db_session.commit()

    completed = await service.complete_session(session.id, dossier_code="HS-2026-001")
    await db_session.commit()

    assert completed.state == SessionState.COMPLETED.value
    assert completed.dossier_code == "HS-2026-001"
    assert completed.completed_at is not None


async def test_inherit_from_parent_only_copies_whitelisted_confirmed_fields(db_session) -> None:
    service = _make_service(db_session)
    parent = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    parent_field_repo = FieldStateRepository(db_session)
    await parent_field_repo.upsert(
        parent.id,
        "ho_ten_nguoi_yeu_cau",
        confirmed_value="Nguyễn Văn A",
        is_confirmed=True,
    )
    # Trường không nằm trong whitelist — không được kế thừa dù đã xác nhận.
    await parent_field_repo.upsert(
        parent.id, "ghi_chu_noi_bo", confirmed_value="abc", is_confirmed=True
    )
    # Trường trong whitelist nhưng CHƯA xác nhận — không được kế thừa.
    await parent_field_repo.upsert(parent.id, "so_dien_thoai", suggested_value="0912345678")
    await db_session.commit()

    child = await service.create_session(staff_name="Cán bộ A", parent_session_id=parent.id)
    await db_session.commit()

    inherited = await service.inherit_from_parent(child.id)
    await db_session.commit()

    assert inherited == ["ho_ten_nguoi_yeu_cau"]

    child_field_repo = FieldStateRepository(db_session)
    ho_ten = await child_field_repo.get(child.id, "ho_ten_nguoi_yeu_cau")
    assert ho_ten is not None
    assert ho_ten.suggested_value == "Nguyễn Văn A"
    assert ho_ten.suggested_by == "parent_session"
    assert ho_ten.is_confirmed is False  # vẫn phải xác nhận lại (NT-3)


async def test_inherit_from_parent_no_parent_returns_empty(db_session) -> None:
    service = _make_service(db_session)
    session = await service.create_session(staff_name="Cán bộ A")
    await db_session.commit()

    assert await service.inherit_from_parent(session.id) == []


def test_inheritable_fields_matches_plan_whitelist() -> None:
    assert INHERITABLE_FIELDS == {
        "ho_ten_nguoi_yeu_cau",
        "ngay_sinh_nguoi_yeu_cau",
        "so_cccd_nguoi_yeu_cau",
        "so_dien_thoai",
        "dia_chi_thuong_tru",
    }
