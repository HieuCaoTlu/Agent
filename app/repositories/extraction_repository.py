"""`ExtractionRepository` — lưu kết quả trích xuất, lấy lịch sử."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction import Extraction


class ExtractionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, extraction: Extraction) -> Extraction:
        self._db.add(extraction)
        await self._db.flush()
        return extraction

    async def get(self, extraction_id: uuid.UUID) -> Extraction | None:
        return await self._db.get(Extraction, extraction_id)

    async def list_by_session(self, session_id: uuid.UUID) -> list[Extraction]:
        """Lịch sử các lần trích xuất của phiên, cũ nhất trước (theo thứ tự thời gian gọi)."""
        stmt = (
            select(Extraction)
            .where(Extraction.session_id == session_id)
            .order_by(Extraction.created_at.asc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_session(self, session_id: uuid.UUID) -> int:
        """Số lần trích xuất đã thực hiện — dùng kiểm tra `max_extractions_per_session` (L2)."""
        stmt = (
            select(func.count())
            .select_from(Extraction)
            .where(Extraction.session_id == session_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()
