"""`FieldHistoryRepository` — chỉ có hàm append, không có update/delete (xem NT-7)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import FieldHistory


class FieldHistoryRepository:
    """Cố ý KHÔNG cung cấp update()/delete() — lịch sử trường phải bất biến."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def append(
        self,
        session_id: uuid.UUID,
        field_name: str,
        old_value: str | None,
        new_value: str | None,
        change_source: str,
        changed_by: str | None = None,
    ) -> FieldHistory:
        entry = FieldHistory(
            session_id=session_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_source=change_source,
            changed_by=changed_by,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_by_session(self, session_id: uuid.UUID) -> list[FieldHistory]:
        stmt = (
            select(FieldHistory)
            .where(FieldHistory.session_id == session_id)
            .order_by(FieldHistory.changed_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_field(self, session_id: uuid.UUID, field_name: str) -> list[FieldHistory]:
        stmt = (
            select(FieldHistory)
            .where(FieldHistory.session_id == session_id, FieldHistory.field_name == field_name)
            .order_by(FieldHistory.changed_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
