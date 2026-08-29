"""Test `FieldStateRepository` — upsert theo (session_id, field_name)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.repositories.field_state_repository import FieldStateRepository


async def test_upsert_creates_new(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = FieldStateRepository(db_session)
    fs = await repo.upsert(session.id, "ho_ten", suggested_value="Nguyễn Văn A")
    await db_session.commit()

    assert fs.field_name == "ho_ten"
    assert fs.suggested_value == "Nguyễn Văn A"
    assert fs.is_confirmed is False


async def test_upsert_updates_existing(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = FieldStateRepository(db_session)
    await repo.upsert(session.id, "ho_ten", suggested_value="Nguyễn Văn A")
    await db_session.commit()

    updated = await repo.upsert(session.id, "ho_ten", suggested_value="Trần Thị B")
    await db_session.commit()

    assert updated.suggested_value == "Trần Thị B"

    all_states = await repo.list_by_session(session.id)
    # Phải vẫn chỉ có 1 dòng cho (session_id, field_name) — không tạo trùng
    assert len(all_states) == 1


async def test_list_by_session_returns_all_fields(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = FieldStateRepository(db_session)
    await repo.upsert(session.id, "ho_ten", suggested_value="A")
    await repo.upsert(session.id, "ngay_sinh", suggested_value="01/01/2000")
    await db_session.commit()

    states = await repo.list_by_session(session.id)
    assert {s.field_name for s in states} == {"ho_ten", "ngay_sinh"}
