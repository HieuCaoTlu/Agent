"""Enum `AuditAction` — Mục E của Checklist (rút gọn — chỉ action của luồng chính).

Logic thuần, không I/O — enum liệt kê hành động hợp lệ để ghi vào audit log.
Việc ghi log thật (I/O) nằm ở `app/services/audit_service.py`.

Bản rút gọn: chỉ 7 action của luồng chính (Mục 8.3 của Plan liệt kê đầy đủ hơn
nhiều, ví dụ đăng nhập/đăng xuất cán bộ, thay đổi catalog... — thêm lại khi
luồng chính đã chạy ổn định).
"""

from enum import StrEnum


class AuditAction(StrEnum):
    SESSION_CREATED = "session_created"
    EXTRACTION_REQUESTED = "extraction_requested"
    EXTRACTION_SUCCEEDED = "extraction_succeeded"
    EXTRACTION_FAILED = "extraction_failed"
    FIELD_CONFIRMED = "field_confirmed"
    SESSION_COMPLETED = "session_completed"
    SESSION_CANCELLED = "session_cancelled"
