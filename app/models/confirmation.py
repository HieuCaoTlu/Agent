"""Model `CitizenConfirmation` — xác nhận của người dân sau khi nghe đọc lại."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, new_uuid

if TYPE_CHECKING:
    from app.models.session import Session


class CitizenConfirmation(Base):
    """Một lượt đọc lại nội dung cho người dân và ghi nhận xác nhận/từ chối.

    Lược bỏ khỏi MVP: `recorded_by` là chuỗi tên cán bộ, không FK tới
    `staff_users` (bảng này không tồn tại ở MVP — xem Checklist.MD mục B2).
    """

    __tablename__ = "citizen_confirmations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    readback_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    readback_text: Mapped[str] = mapped_column(Text, nullable=False)
    # tts_audio | screen_text
    readback_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confirmation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["Session"] = relationship("Session", back_populates="citizen_confirmations")
