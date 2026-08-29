"""Base declarative và mixin dùng chung cho mọi model SQLAlchemy."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Kiểu UUID tương thích đa dialect: native UUID trên Postgres, CHAR(32) trên SQLite.
# Dùng kiểu này (thay vì sqlalchemy.dialects.postgresql.UUID) cho mọi cột UUID trong
# models/ để cùng một mã nguồn chạy được cả Postgres (production) và SQLite (dev/test
# khi chưa có Docker sẵn — xem README.md phần môi trường dev).
GUID = Uuid(as_uuid=True, native_uuid=True)

# Kiểu khóa chính tự tăng cho các bảng append-only (audit_log, field_history).
# BIGSERIAL/BIGINT thật trên Postgres; trên SQLite, BigInteger PRIMARY KEY KHÔNG
# kích hoạt rowid-alias autoincrement (chỉ INTEGER PRIMARY KEY mới có), nên biến
# thể sqlite dùng Integer để autoincrement hoạt động đúng khi dev/test.
BigAutoIncrement = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    """Base class cho toàn bộ model của ứng dụng."""


class TimestampMixin:
    """Mixin thêm `created_at`/`updated_at` tự động quản lý bởi database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def new_uuid() -> uuid.UUID:
    """Sinh UUID4 mặc định phía Python cho cột id (tương thích SQLite lẫn Postgres)."""
    return uuid.uuid4()
