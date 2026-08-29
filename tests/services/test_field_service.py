"""Test `FieldService` — Mục I3 của Checklist."""

import uuid
from datetime import date
from pathlib import Path

import pytest

from app.models.session import Session
from app.repositories.audit_repository import AuditRepository
from app.repositories.field_history_repository import FieldHistoryRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.services.catalog_service import CatalogService
from app.services.field_service import FieldNotFound, FieldService, SessionNotFoundForField

_CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "static_data" / "procedures"
_FIXED_ACTIVE_DATE = date(2026, 9, 15)


class _FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return _FIXED_ACTIVE_DATE


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.field_service.date", _FixedDate)


def _make_service(db_session) -> FieldService:
    return FieldService(
        session_repository=SessionRepository(db_session),
        field_state_repository=FieldStateRepository(db_session),
        field_history_repository=FieldHistoryRepository(db_session),
        audit_repository=AuditRepository(db_session),
        catalog_service=CatalogService(_CATALOG_DIR),
    )


async def _make_session_with_all_fields(
    db_session, state: str = "REVIEWING", code: str = "dang_ky_khai_sinh"
) -> Session:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state=state, procedure_code=code)
    await session_repo.create(session)

    catalog = CatalogService(_CATALOG_DIR)
    procedure = catalog.get(code, _FIXED_ACTIVE_DATE)
    field_repo = FieldStateRepository(db_session)
    for field in procedure.fields:
        await field_repo.upsert(session.id, field.name)
    await db_session.commit()
    return session


async def test_confirm_field_not_edited_when_matches_suggestion(db_session) -> None:
    session = await _make_session_with_all_fields(db_session)
    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(
        session.id, "ho_ten_nguoi_duoc_khai_sinh", suggested_value="Nguyễn Văn A"
    )
    await db_session.commit()

    service = _make_service(db_session)
    updated = await service.confirm_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh", "Nguyễn Văn A", staff_name="Cán bộ A"
    )
    await db_session.commit()

    assert updated.confirmed_value == "Nguyễn Văn A"
    assert updated.is_confirmed is True
    assert updated.was_edited is False

    history = await FieldHistoryRepository(db_session).list_by_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh"
    )
    assert history[-1].change_source == "staff_confirm"


async def test_confirm_field_marks_edited_when_differs_from_suggestion(db_session) -> None:
    session = await _make_session_with_all_fields(db_session)
    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(
        session.id, "ho_ten_nguoi_duoc_khai_sinh", suggested_value="Nguyễn Văn A"
    )
    await db_session.commit()

    service = _make_service(db_session)
    updated = await service.confirm_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh", "Nguyễn Văn B", staff_name="Cán bộ A"
    )
    await db_session.commit()

    assert updated.was_edited is True

    history = await FieldHistoryRepository(db_session).list_by_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh"
    )
    assert history[-1].change_source == "staff_edit"


async def test_confirm_field_session_not_found_raises(db_session) -> None:
    service = _make_service(db_session)
    with pytest.raises(SessionNotFoundForField):
        await service.confirm_field(uuid.uuid4(), "x", "y", staff_name="A")


async def test_confirm_field_unknown_field_raises(db_session) -> None:
    session = await _make_session_with_all_fields(db_session)
    service = _make_service(db_session)
    with pytest.raises(FieldNotFound):
        await service.confirm_field(session.id, "khong_ton_tai", "abc", staff_name="A")


async def test_confirm_all_required_fields_advances_session_to_fields_confirmed(
    db_session,
) -> None:
    session = await _make_session_with_all_fields(db_session, state="REVIEWING")
    catalog = CatalogService(_CATALOG_DIR)
    procedure = catalog.get("dang_ky_khai_sinh", _FIXED_ACTIVE_DATE)
    required_fields = [f for f in procedure.fields if f.required]

    service = _make_service(db_session)
    for field in required_fields:
        await service.confirm_field(session.id, field.name, "giá trị test", staff_name="Cán bộ A")
        await db_session.commit()

    updated_session = await SessionRepository(db_session).get(session.id)
    assert updated_session.state == "FIELDS_CONFIRMED"


async def test_confirm_partial_required_fields_keeps_reviewing(db_session) -> None:
    session = await _make_session_with_all_fields(db_session, state="REVIEWING")
    service = _make_service(db_session)

    await service.confirm_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh", "Nguyễn Văn A", staff_name="Cán bộ A"
    )
    await db_session.commit()

    updated_session = await SessionRepository(db_session).get(session.id)
    assert updated_session.state == "REVIEWING"


async def test_confirm_field_outside_reviewing_state_does_not_transition(db_session) -> None:
    session = await _make_session_with_all_fields(db_session, state="SUGGESTED")
    catalog = CatalogService(_CATALOG_DIR)
    procedure = catalog.get("dang_ky_khai_sinh", _FIXED_ACTIVE_DATE)
    required_fields = [f for f in procedure.fields if f.required]

    service = _make_service(db_session)
    for field in required_fields:
        await service.confirm_field(session.id, field.name, "giá trị test", staff_name="Cán bộ A")
        await db_session.commit()

    # Không ở REVIEWING lúc xác nhận -> không tự động chuyển, dù đủ trường bắt buộc.
    updated_session = await SessionRepository(db_session).get(session.id)
    assert updated_session.state == "SUGGESTED"


async def test_unconfirm_field_keeps_value_but_clears_flag(db_session) -> None:
    session = await _make_session_with_all_fields(db_session)
    service = _make_service(db_session)
    await service.confirm_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh", "Nguyễn Văn A", staff_name="Cán bộ A"
    )
    await db_session.commit()

    updated = await service.unconfirm_field(session.id, "ho_ten_nguoi_duoc_khai_sinh")
    await db_session.commit()

    assert updated.is_confirmed is False
    assert updated.confirmed_value == "Nguyễn Văn A"  # giá trị không bị xóa


async def test_unconfirm_unknown_field_raises(db_session) -> None:
    session = await _make_session_with_all_fields(db_session)
    service = _make_service(db_session)
    with pytest.raises(FieldNotFound):
        await service.unconfirm_field(session.id, "khong_ton_tai")


async def test_get_fields_returns_validation_results(db_session) -> None:
    session = await _make_session_with_all_fields(db_session)
    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(session.id, "so_dien_thoai", suggested_value="912")  # sai định dạng
    await db_session.commit()

    service = _make_service(db_session)
    fields = await service.get_fields(session.id)

    phone_field = next(f for f in fields if f.field_state.field_name == "so_dien_thoai")
    assert any(not r.valid for r in phone_field.validation_results)


async def test_get_fields_no_procedure_returns_empty_validation(db_session) -> None:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state="LISTENING")
    await session_repo.create(session)
    await db_session.commit()

    service = _make_service(db_session)
    fields = await service.get_fields(session.id)
    assert fields == []
