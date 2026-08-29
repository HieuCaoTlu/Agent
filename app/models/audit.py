"""Model `AuditLog` — nhật ký hành động, append-only (xem NT-7).

Không khai báo quan hệ (`relationship`) với `Session` vì `session_id` ở đây
cố ý không có ràng buộc khóa ngoại cứng (log phải giữ được ngay cả khi phiên
bị xóa hoặc trong trường hợp actor_type != session, ví dụ log bảo mật không
gắn với phiên nào). Việc REVOKE UPDATE/DELETE thực hiện ở migration (B3).
"""

import ipaddress
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, BigAutoIncrement


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigAutoIncrement, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True, index=True)
    # system | staff | citizen
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Lưu dạng chuỗi (thay vì kiểu INET riêng của Postgres) để tương thích SQLite khi
    # dev/test; giá trị vẫn phải là IPv4/IPv6 hợp lệ — validate ở AuditService (E).
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def validate_ip_address(value: str) -> str:
    """Kiểm tra `value` là địa chỉ IPv4/IPv6 hợp lệ trước khi ghi vào `AuditLog.ip_address`."""
    ipaddress.ip_address(value)
    return value
