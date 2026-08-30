"""Model `Session` — phiên làm việc tại quầy hỗ trợ."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    FetchedValue,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from app.models.confirmation import CitizenConfirmation
    from app.models.extraction import Extraction, FieldState
    from app.models.voice import VoiceTurn

# 12 trạng thái của state machine — khớp SessionState ở app/domain/session_state.py (C1)
SESSION_STATES = (
    "CREATED",
    "LISTENING",
    "PROCEDURE_SELECTED",
    "EXTRACTING",
    "SUGGESTED",
    "AI_UNAVAILABLE",
    "REVIEWING",
    "FIELDS_CONFIRMED",
    "READBACK",
    "CITIZEN_CONFIRMED",
    "COMPLETED",
    "CANCELLED",
)


class Session(Base, TimestampMixin):
    """Một phiên hỗ trợ kê khai — đơn vị công việc chính của hệ thống.

    Lược bỏ khỏi MVP: không có FK tới bảng người dùng (không có `staff_users`
    ở MVP này — xem Checklist.MD mục B2). `staff_name` là chuỗi định danh cán
    bộ nhập tay lúc tạo phiên, không phải tài khoản đăng nhập.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "state IN (" + ", ".join(f"'{s}'" for s in SESSION_STATES) + ")",
            name="chk_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    parent_session_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("sessions.id"), nullable=True, index=True
    )
    staff_name: Mapped[str] = mapped_column(String(200), nullable=False)
    procedure_code: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    catalog_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="CREATED", index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="ai_assisted")
    citizen_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_recorded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    citizen_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dossier_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # duration_ms: cột tính toán phía Postgres (GENERATED ALWAYS AS ... STORED) — xem migration B3.
    # `server_default=FetchedValue()` báo cho SQLAlchemy đây là giá trị do server sinh ra —
    # KHÔNG gửi giá trị (kể cả NULL) trong câu INSERT/UPDATE (Postgres từ chối insert vào
    # generated column dù là NULL), và tự đọc lại giá trị thật qua RETURNING sau khi ghi.
    # Không khai báo công thức ở đây để tránh trùng logic giữa ORM và DB; đọc lại qua refresh().
    duration_ms: Mapped[int | None] = mapped_column(
        Integer, server_default=FetchedValue(), nullable=True
    )

    # Quan hệ tự tham chiếu (UC3): một phiên cha có thể có nhiều phiên con kế thừa dữ liệu
    parent: Mapped["Session | None"] = relationship(
        "Session", remote_side="Session.id", back_populates="children"
    )
    children: Mapped[list["Session"]] = relationship("Session", back_populates="parent")

    voice_turns: Mapped[list["VoiceTurn"]] = relationship(
        "VoiceTurn", back_populates="session", cascade="all, delete-orphan"
    )
    extractions: Mapped[list["Extraction"]] = relationship(
        "Extraction", back_populates="session", cascade="all, delete-orphan"
    )
    field_states: Mapped[list["FieldState"]] = relationship(
        "FieldState", back_populates="session", cascade="all, delete-orphan"
    )
    citizen_confirmations: Mapped[list["CitizenConfirmation"]] = relationship(
        "CitizenConfirmation", back_populates="session", cascade="all, delete-orphan"
    )
