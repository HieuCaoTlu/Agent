"""`AuditService` — Mục E của Checklist (rút gọn), Mục 8 của Plan.

Bọc `AuditRepository` (I/O) bằng một hàm nghiệp vụ duy nhất `log(...)` — nơi
duy nhất trong ứng dụng được phép ghi vào audit log, để đảm bảo mọi lượt ghi
đều đi qua cùng một đường kiểm tra (validate `ip_address`, ép kiểu `AuditAction`
thành chuỗi khi lưu).

**Rút gọn cho MVP (30/8/2026):** không đảm bảo cùng transaction chặt với thao
tác nghiệp vụ đi kèm — service gọi `log()` ngay sau khi thao tác chính thành
công, chấp nhận rủi ro nhỏ ghi log trễ/thiếu nếu tiến trình crash giữa hai
bước. Không redact `detail` — tầng gọi tự chịu trách nhiệm không đưa giá trị
nhạy cảm (CCCD, số điện thoại...) vào `detail`.
"""

import uuid
from typing import Any

from app.domain.audit_action import AuditAction
from app.models.audit import AuditLog, validate_ip_address
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def log(
        self,
        actor_type: str,
        action: AuditAction,
        session_id: uuid.UUID | None = None,
        actor_id: str | None = None,
        detail: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        if ip_address is not None:
            validate_ip_address(ip_address)

        return await self._repository.append(
            actor_type=actor_type,
            action=action.value,
            session_id=session_id,
            actor_id=actor_id,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
