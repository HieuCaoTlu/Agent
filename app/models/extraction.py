"""Models `Extraction`, `FieldState`, `FieldHistory`."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, BigAutoIncrement, new_uuid

if TYPE_CHECKING:
    from app.models.session import Session


class Extraction(Base):
    """Một lần gọi LLM để trích xuất trường dữ liệu từ transcript.

    `parsed_json`/`warnings` dùng kiểu `JSON` chung (không phải `JSONB` riêng
    của Postgres) để tương thích SQLite khi dev/test; Postgres tự dùng JSONB
    tương đương qua kiểu JSON chuẩn của SQLAlchemy trên dialect đó.
    """

    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("voice_turns.id"), nullable=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_redacted: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # success | parse_failed | schema_violation | api_error | timeout
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped["Session"] = relationship("Session", back_populates="extractions")


class FieldState(Base):
    """Trạng thái hiện tại của một trường dữ liệu trong phiên — "sổ cái" trạng thái.

    Một dòng cho mỗi (session_id, field_name). Lịch sử thay đổi nằm ở
    `FieldHistory` (append-only), bảng này chỉ giữ giá trị mới nhất.
    """

    __tablename__ = "field_states"
    __table_args__ = (
        UniqueConstraint("session_id", "field_name", name="uq_field_state_session_field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    suggested_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # llm | parent_session | manual
    suggested_by: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # high | medium | low | null
    ai_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evidence_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Lược bỏ khỏi MVP: không có staff_users, dùng chuỗi tên cán bộ thay vì FK UUID.
    confirmed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    was_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # ok | missing | unclear | format_error | conflict
    validation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    session: Mapped["Session"] = relationship("Session", back_populates="field_states")


class FieldHistory(Base):
    """Lịch sử thay đổi trường — append-only, không có update/delete (xem NT-7).

    Không dùng UUID cho khóa chính vì đây là log tuần tự thuần túy, dùng
    BIGSERIAL/`BigInteger` autoincrement như thiết kế gốc ở Mục 8.2 của Plan.
    """

    __tablename__ = "field_history"

    id: Mapped[int] = mapped_column(BigAutoIncrement, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # llm_extraction | staff_edit | staff_confirm | parent_session | amend
    change_source: Mapped[str] = mapped_column(String(30), nullable=False)
    # Lược bỏ khỏi MVP: chuỗi tên cán bộ thay vì FK UUID tới staff_users.
    changed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
