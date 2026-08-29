"""`VoiceTurnRepository` — thêm lượt thoại, lấy danh sách theo phiên, tự tăng `turn_number`."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice import VoiceTurn


class VoiceTurnRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def next_turn_number(self, session_id: uuid.UUID) -> int:
        """Số thứ tự lượt thoại kế tiếp cho phiên — bắt đầu từ 1."""
        stmt = select(func.max(VoiceTurn.turn_number)).where(VoiceTurn.session_id == session_id)
        result = await self._db.execute(stmt)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def add(self, voice_turn: VoiceTurn) -> VoiceTurn:
        """Thêm lượt thoại mới. Nếu `turn_number` chưa được gán, tự tăng trước khi thêm."""
        if voice_turn.turn_number is None:  # type: ignore[comparison-overlap]
            voice_turn.turn_number = await self.next_turn_number(voice_turn.session_id)
        self._db.add(voice_turn)
        await self._db.flush()
        return voice_turn

    async def get(self, turn_id: uuid.UUID) -> VoiceTurn | None:
        return await self._db.get(VoiceTurn, turn_id)

    async def list_by_session(self, session_id: uuid.UUID) -> list[VoiceTurn]:
        stmt = (
            select(VoiceTurn)
            .where(VoiceTurn.session_id == session_id)
            .order_by(VoiceTurn.turn_number.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
