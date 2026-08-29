"""Test `AuditRepository` — append, truy vấn theo phiên/hành động/thời gian."""

import uuid
from datetime import UTC, datetime, timedelta

from app.repositories.audit_repository import AuditRepository


async def test_no_mutation_methods_exposed() -> None:
    """Khẳng định repository không lộ hàm update/delete — bảo vệ tính bất biến (NT-7)."""
    assert not hasattr(AuditRepository, "update")
    assert not hasattr(AuditRepository, "delete")


async def test_append_and_list_by_session(db_session) -> None:
    session_id = uuid.uuid4()
    repo = AuditRepository(db_session)
    await repo.append(
        actor_type="staff",
        action="session_created",
        session_id=session_id,
        actor_id="Nguyễn Văn A",
        detail={"mode": "ai_assisted"},
    )
    await db_session.commit()

    entries = await repo.list_by_session(session_id)
    assert len(entries) == 1
    assert entries[0].action == "session_created"
    assert entries[0].detail == {"mode": "ai_assisted"}


async def test_list_by_action(db_session) -> None:
    repo = AuditRepository(db_session)
    await repo.append(actor_type="staff", action="field_confirmed")
    await repo.append(actor_type="staff", action="field_confirmed")
    await repo.append(actor_type="staff", action="session_cancelled")
    await db_session.commit()

    confirmed = await repo.list_by_action("field_confirmed")
    assert len(confirmed) == 2


async def test_list_by_time_range(db_session) -> None:
    repo = AuditRepository(db_session)
    await repo.append(actor_type="system", action="extraction_requested")
    await db_session.commit()

    now = datetime.now(UTC)
    results = await repo.list_by_time_range(now - timedelta(minutes=5), now + timedelta(minutes=5))
    assert len(results) == 1
