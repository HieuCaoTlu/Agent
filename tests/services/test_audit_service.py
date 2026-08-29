"""Test `AuditService` — nơi duy nhất được phép ghi audit log."""

import uuid

import pytest

from app.domain.audit_action import AuditAction
from app.repositories.audit_repository import AuditRepository
from app.services.audit_service import AuditService


async def test_log_appends_entry_with_action_as_string(db_session) -> None:
    service = AuditService(AuditRepository(db_session))
    session_id = uuid.uuid4()

    entry = await service.log(
        actor_type="staff",
        action=AuditAction.SESSION_CREATED,
        session_id=session_id,
        actor_id="Nguyễn Văn A",
        detail={"mode": "ai_assisted"},
    )
    await db_session.commit()

    assert entry.action == "session_created"
    assert entry.session_id == session_id
    assert entry.detail == {"mode": "ai_assisted"}


async def test_log_without_optional_fields(db_session) -> None:
    service = AuditService(AuditRepository(db_session))
    entry = await service.log(actor_type="system", action=AuditAction.EXTRACTION_REQUESTED)
    await db_session.commit()

    assert entry.action == "extraction_requested"
    assert entry.session_id is None
    assert entry.detail is None


async def test_log_validates_ip_address(db_session) -> None:
    service = AuditService(AuditRepository(db_session))
    entry = await service.log(
        actor_type="staff", action=AuditAction.FIELD_CONFIRMED, ip_address="192.168.1.10"
    )
    await db_session.commit()
    assert entry.ip_address == "192.168.1.10"


async def test_log_rejects_invalid_ip_address(db_session) -> None:
    service = AuditService(AuditRepository(db_session))
    with pytest.raises(ValueError):  # noqa: PT011 — vì ipaddress.ip_address ném ValueError thô
        await service.log(
            actor_type="staff", action=AuditAction.FIELD_CONFIRMED, ip_address="not-an-ip"
        )
