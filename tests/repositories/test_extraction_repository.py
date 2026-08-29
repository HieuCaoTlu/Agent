"""Test `ExtractionRepository` — lưu kết quả trích xuất, lấy lịch sử."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import Extraction
from app.models.session import Session
from app.repositories.extraction_repository import ExtractionRepository


async def test_add_and_get(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = ExtractionRepository(db_session)
    extraction = await repo.add(Extraction(session_id=session.id, status="success"))
    await db_session.commit()

    fetched = await repo.get(extraction.id)
    assert fetched is not None
    assert fetched.status == "success"


async def test_list_by_session_ordered_by_time(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = ExtractionRepository(db_session)
    await repo.add(Extraction(session_id=session.id, status="success", attempt_number=1))
    await repo.add(Extraction(session_id=session.id, status="timeout", attempt_number=2))
    await db_session.commit()

    history = await repo.list_by_session(session.id)
    assert [e.attempt_number for e in history] == [1, 2]


async def test_count_by_session(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = ExtractionRepository(db_session)
    assert await repo.count_by_session(session.id) == 0

    await repo.add(Extraction(session_id=session.id, status="success"))
    await db_session.commit()

    assert await repo.count_by_session(session.id) == 1
