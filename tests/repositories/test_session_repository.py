"""Test `SessionRepository` — CRUD, quan hệ tự tham chiếu (UC3), truy vấn."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.repositories.session_repository import SessionRepository

_VN_TZ = timezone(timedelta(hours=7))


async def test_create_and_get(db_session: AsyncSession) -> None:
    repo = SessionRepository(db_session)
    session = Session(staff_name="Nguyễn Văn A")
    created = await repo.create(session)
    await db_session.commit()

    fetched = await repo.get(created.id)
    assert fetched is not None
    assert fetched.staff_name == "Nguyễn Văn A"
    assert fetched.state == "CREATED"


async def test_get_missing_returns_none(db_session: AsyncSession) -> None:
    import uuid

    repo = SessionRepository(db_session)
    assert await repo.get(uuid.uuid4()) is None


async def test_parent_child_relationship(db_session: AsyncSession) -> None:
    repo = SessionRepository(db_session)
    parent = await repo.create(Session(staff_name="Cán bộ A"))
    await db_session.flush()
    child = await repo.create(Session(staff_name="Cán bộ A", parent_session_id=parent.id))
    await db_session.commit()

    fetched_child = await repo.get(child.id)
    assert fetched_child is not None
    assert fetched_child.parent_session_id == parent.id


async def test_list_recent_orders_newest_first(db_session: AsyncSession) -> None:
    repo = SessionRepository(db_session)
    for name in ("A", "B", "C"):
        await repo.create(Session(staff_name=name))
    await db_session.commit()

    results = await repo.list_recent(limit=10)
    assert len(results) == 3


async def test_list_by_state(db_session: AsyncSession) -> None:
    repo = SessionRepository(db_session)
    s1 = Session(staff_name="A", state="COMPLETED")
    s2 = Session(staff_name="B", state="CREATED")
    await repo.create(s1)
    await repo.create(s2)
    await db_session.commit()

    completed = await repo.list_by_state("COMPLETED")
    assert len(completed) == 1
    assert completed[0].staff_name == "A"


async def test_list_by_date(db_session: AsyncSession) -> None:
    """SQLite CURRENT_TIMESTAMP trả naive-UTC nên không dùng để test so khớp
    aware-datetime một cách đáng tin cậy — gán `started_at` tường minh (aware,
    giờ VN) thay vì dựa vào server_default, để test độc lập với hành vi
    timezone khác nhau giữa SQLite (dev) và Postgres (production)."""
    repo = SessionRepository(db_session)
    now_vn = datetime.now(_VN_TZ)
    session = Session(staff_name="A", started_at=now_vn)
    await repo.create(session)
    await db_session.commit()

    today_results = await repo.list_by_date(now_vn.date())
    assert len(today_results) == 1

    yesterday_results = await repo.list_by_date((now_vn - timedelta(days=1)).date())
    assert len(yesterday_results) == 0
