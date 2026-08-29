"""`AuditRepository` — append log, truy vấn theo phiên/hành động/thời gian.

Cố ý KHÔNG cung cấp update()/delete() — audit log phải bất biến (NT-7). Ràng
buộc cứng ở tầng database do migration `REVOKE UPDATE, DELETE` đảm nhiệm
(xem B3); repository này chỉ đảm bảo tầng ứng dụng không có lối gọi sai.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class AuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(
        self,
        actor_type: str,
        action: str,
        session_id: uuid.UUID | None = None,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            session_id=session_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_by_session(self, session_id: uuid.UUID) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.session_id == session_id)
            .order_by(AuditLog.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_action(
        self, action: str, *, limit: int = 100, offset: int = 0
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_time_range(
        self, start: datetime, end: datetime, *, limit: int = 100, offset: int = 0
    ) -> list[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.created_at >= start, AuditLog.created_at <= end)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
