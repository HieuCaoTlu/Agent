"""Test `VoiceTurnRepository` — tự tăng turn_number, truy vấn theo phiên."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.models.voice import VoiceTurn
from app.repositories.voice_turn_repository import VoiceTurnRepository


async def test_add_auto_increments_turn_number(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = VoiceTurnRepository(db_session)
    turn1 = await repo.add(VoiceTurn(session_id=session.id, raw_transcript="lượt 1"))
    turn2 = await repo.add(VoiceTurn(session_id=session.id, raw_transcript="lượt 2"))
    await db_session.commit()

    assert turn1.turn_number == 1
    assert turn2.turn_number == 2


async def test_list_by_session_ordered(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = VoiceTurnRepository(db_session)
    await repo.add(VoiceTurn(session_id=session.id, raw_transcript="lượt 1"))
    await repo.add(VoiceTurn(session_id=session.id, raw_transcript="lượt 2"))
    await db_session.commit()

    turns = await repo.list_by_session(session.id)
    assert [t.turn_number for t in turns] == [1, 2]


async def test_next_turn_number_starts_at_one(db_session: AsyncSession) -> None:
    session = Session(staff_name="A")
    db_session.add(session)
    await db_session.flush()

    repo = VoiceTurnRepository(db_session)
    assert await repo.next_turn_number(session.id) == 1
