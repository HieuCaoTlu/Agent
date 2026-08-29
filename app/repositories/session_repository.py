"""`SessionRepository` — CRUD phiên, truy vấn theo ngày/trạng thái."""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session

# Giờ Việt Nam (UTC+7) — hệ thống chỉ vận hành tại phường Yên Sở, không cần
# tra cứu timezone đầy đủ (zoneinfo) cho một múi giờ cố định không có DST.
_VN_TZ = timezone(timedelta(hours=7))


class SessionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, session: Session) -> Session:
        self._db.add(session)
        await self._db.flush()
        return session

    async def get(self, session_id: uuid.UUID) -> Session | None:
        return await self._db.get(Session, session_id)

    async def list_by_date(
        self, day: date, *, limit: int = 50, offset: int = 0
    ) -> list[Session]:
        """Danh sách phiên bắt đầu trong ngày `day` theo giờ Việt Nam, mới nhất trước."""
        start = datetime.combine(day, time.min, tzinfo=_VN_TZ)
        end = start + timedelta(days=1)
        stmt = (
            select(Session)
            .where(Session.started_at >= start, Session.started_at < end)
            .order_by(Session.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_state(
        self, state: str, *, limit: int = 50, offset: int = 0
    ) -> list[Session]:
        stmt = (
            select(Session)
            .where(Session.state == state)
            .order_by(Session.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(self, *, limit: int = 50, offset: int = 0) -> list[Session]:
        """Danh sách phiên gần đây, có phân trang — dùng cho bảng điều khiển (N)."""
        stmt = select(Session).order_by(Session.started_at.desc()).limit(limit).offset(offset)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, session: Session) -> Session:
        """Đăng ký thay đổi trên một instance đã được tracking bởi session hiện tại.

        Gọi `flush()` để đẩy thay đổi xuống DB trong cùng transaction, không tự
        commit — commit là trách nhiệm của tầng service/unit-of-work.
        """
        await self._db.flush()
        return session
