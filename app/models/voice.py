"""Model `VoiceTurn` — một lượt ghi âm/hỏi trong phiên."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, new_uuid

if TYPE_CHECKING:
    from app.models.session import Session


class VoiceTurn(Base):
    """Một lượt ghi âm — tương ứng một lần bấm nút "hỏi" tại quầy.

    `audio_deleted_at` là bằng chứng đã xóa buffer âm thanh khỏi Redis (NT-6:
    không lưu bản ghi âm sau khi có transcript).
    """

    __tablename__ = "voice_turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_number", name="uq_turn_session_number"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_by_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    audio_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    audio_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stt_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    stt_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["Session"] = relationship("Session", back_populates="voice_turns")
