"""`FieldStateRepository` — upsert trạng thái trường, lấy toàn bộ trường của phiên."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import FieldState


class FieldStateRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, session_id: uuid.UUID, field_name: str) -> FieldState | None:
        stmt = select(FieldState).where(
            FieldState.session_id == session_id, FieldState.field_name == field_name
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_session(self, session_id: uuid.UUID) -> list[FieldState]:
        stmt = select(FieldState).where(FieldState.session_id == session_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def upsert(self, session_id: uuid.UUID, field_name: str, **values: Any) -> FieldState:
        """Tạo mới hoặc cập nhật trạng thái một trường theo (session_id, field_name).

        `values` là các thuộc tính của `FieldState` cần set/ghi đè (ví dụ
        `suggested_value=..., ai_confidence=..., evidence_span=...`).
        """
        field_state = await self.get(session_id, field_name)
        if field_state is None:
            field_state = FieldState(session_id=session_id, field_name=field_name, **values)
            self._db.add(field_state)
        else:
            for key, value in values.items():
                setattr(field_state, key, value)
        await self._db.flush()
        return field_state
