"""`CitizenConfirmationRepository` — ghi lượt đọc lại/xác nhận, tra cứu theo phiên."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.confirmation import CitizenConfirmation


class CitizenConfirmationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def next_readback_round(self, session_id: uuid.UUID) -> int:
        """Số vòng đọc lại kế tiếp cho phiên — bắt đầu từ 1 (KPI-3)."""
        stmt = select(func.max(CitizenConfirmation.readback_round)).where(
            CitizenConfirmation.session_id == session_id
        )
        result = await self._db.execute(stmt)
        current_max = result.scalar_one_or_none()
        return (current_max or 0) + 1

    async def add(self, confirmation: CitizenConfirmation) -> CitizenConfirmation:
        self._db.add(confirmation)
        await self._db.flush()
        return confirmation

    async def list_by_session(self, session_id: uuid.UUID) -> list[CitizenConfirmation]:
        stmt = (
            select(CitizenConfirmation)
            .where(CitizenConfirmation.session_id == session_id)
            .order_by(CitizenConfirmation.readback_round.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(self, session_id: uuid.UUID) -> CitizenConfirmation | None:
        """Lượt đọc lại/xác nhận mới nhất của phiên, `None` nếu chưa có lượt nào."""
        stmt = (
            select(CitizenConfirmation)
            .where(CitizenConfirmation.session_id == session_id)
            .order_by(CitizenConfirmation.readback_round.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
