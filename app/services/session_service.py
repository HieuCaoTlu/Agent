"""`SessionService` — Mục I1 của Checklist.

Điều phối vòng đời một phiên (`Session`): tạo, đọc trạng thái đầy đủ, ghi nhận
đồng ý, chọn thủ tục, hủy, kết thúc. Mọi thay đổi trạng thái đi qua
`app.domain.session_state.transition()` (C1) — service này chỉ chịu trách
nhiệm I/O (DB, audit), không tự phát minh luật chuyển trạng thái.
"""

import uuid
from datetime import UTC, date, datetime

from app.domain.audit_action import AuditAction
from app.domain.exceptions import DomainError
from app.domain.extraction_schema import ExtractedField
from app.domain.session_state import SessionEvent, SessionState, transition
from app.domain.warnings import Warning as DomainWarning
from app.domain.warnings import generate_warnings
from app.models.extraction import FieldState
from app.models.session import Session
from app.repositories.audit_repository import AuditRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.services.catalog_service import CatalogService

# Danh sách trắng trường được phép kế thừa từ phiên cha sang phiên con — Mục
# UC3 của Plan. Cố định trong code, không cấu hình động (NT-4 tinh thần chung:
# phạm vi dữ liệu chia sẻ không được để AI hay cấu hình runtime tự mở rộng).
INHERITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "ho_ten_nguoi_yeu_cau",
        "ngay_sinh_nguoi_yeu_cau",
        "so_cccd_nguoi_yeu_cau",
        "so_dien_thoai",
        "dia_chi_thuong_tru",
    }
)


class SessionNotFound(DomainError):
    """Ném ra khi không tìm thấy phiên theo `session_id`."""

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Không tìm thấy phiên có mã '{session_id}'.")


class SessionStateSnapshot:
    """Trạng thái đầy đủ của một phiên — dùng cho `GET /sessions/{id}` (J2).

    Không phải model DB, không phải Pydantic response model (đó là việc của
    tầng API, J) — chỉ là cấu trúc dữ liệu thuần tập hợp mọi thứ tầng API cần
    để dựng response, tránh tầng API phải tự gọi nhiều repository.
    """

    def __init__(
        self,
        session: Session,
        field_states: list[FieldState],
        warnings: list[DomainWarning],
    ) -> None:
        self.session = session
        self.field_states = field_states
        self.warnings = warnings


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        field_state_repository: FieldStateRepository,
        audit_repository: AuditRepository,
        catalog_service: CatalogService,
    ) -> None:
        self._sessions = session_repository
        self._field_states = field_state_repository
        self._audit = audit_repository
        self._catalog = catalog_service

    async def create_session(
        self,
        staff_name: str,
        parent_session_id: uuid.UUID | None = None,
        mode: str = "ai_assisted",
    ) -> Session:
        """Tạo phiên mới (`CREATED`), ghi audit `session_created`.

        Không kiểm tra `parent_session_id` có tồn tại hay không ở đây bằng
        ràng buộc nghiệp vụ bổ sung — FK của DB (`ForeignKey("sessions.id")`)
        đã đảm nhiệm việc đó, ném lỗi tầng DB nếu phiên cha không tồn tại.
        """
        session = Session(
            staff_name=staff_name,
            parent_session_id=parent_session_id,
            mode=mode,
            state=SessionState.CREATED.value,
        )
        await self._sessions.create(session)
        parent_id_str = str(parent_session_id) if parent_session_id else None
        await self._audit.append(
            actor_type="staff",
            action=AuditAction.SESSION_CREATED.value,
            session_id=session.id,
            actor_id=staff_name,
            detail={"mode": mode, "parent_session_id": parent_id_str},
        )
        return session

    async def get_session_state(self, session_id: uuid.UUID) -> SessionStateSnapshot:
        """Trạng thái đầy đủ: phiên, mọi `FieldState`, và cảnh báo hiện tại.

        Cảnh báo được tính lại từ field schema (catalog) + trạng thái trường
        hiện có — không lưu cảnh báo trong DB, luôn tính mới để phản ánh đúng
        `field_states` mới nhất (tránh cảnh báo "cũ" không khớp dữ liệu).
        """
        session = await self._get_or_raise(session_id)
        field_states = await self._field_states.list_by_session(session_id)

        warnings: list[DomainWarning] = []
        if session.procedure_code is not None:
            fields = self._catalog.get_field_schema(session.procedure_code, date.today())
            extracted = _field_states_to_extracted_map(field_states)
            warnings = generate_warnings(fields, extracted)

        return SessionStateSnapshot(session=session, field_states=field_states, warnings=warnings)

    async def record_consent(self, session_id: uuid.UUID, consented: bool) -> Session:
        """Ghi nhận đồng ý (hoặc từ chối) của người dân trước khi bắt đầu ghi âm."""
        session = await self._get_or_raise(session_id)
        session.citizen_consent = consented
        session.consent_recorded_at = datetime.now(UTC)
        await self._sessions.update(session)
        return session

    async def select_procedure(self, session_id: uuid.UUID, code: str) -> Session:
        """Chọn thủ tục cho phiên: kiểm tra catalog, chuyển trạng thái, khởi tạo
        `field_states` rỗng cho mọi trường của thủ tục.

        Ném `ProcedureNotFound` (từ `CatalogService`) nếu mã không hợp lệ/hết
        hiệu lực — phiên giữ nguyên trạng thái cũ, không có thay đổi một phần.
        """
        session = await self._get_or_raise(session_id)
        procedure = self._catalog.get(code, date.today())

        next_state = transition(SessionState(session.state), SessionEvent.SELECT_PROCEDURE)

        session.procedure_code = procedure.code
        session.catalog_version = procedure.catalog_version
        session.state = next_state.value
        await self._sessions.update(session)

        for field in procedure.fields:
            await self._field_states.upsert(session_id, field.name)

        return session

    async def inherit_from_parent(self, session_id: uuid.UUID) -> list[str]:
        """Kế thừa các trường trong `INHERITABLE_FIELDS` từ phiên cha (UC3).

        Chỉ áp dụng khi phiên có `parent_session_id` và phiên cha có
        `FieldState` đã xác nhận (`is_confirmed=True`) cho trường đó. Giá trị
        kế thừa được ghi vào `suggested_value`/`suggested_by="parent_session"`
        — KHÔNG tự động `is_confirmed=True` (NT-3: cán bộ vẫn phải xác nhận
        lại ở phiên con). Trả về danh sách tên trường đã kế thừa được.
        """
        session = await self._get_or_raise(session_id)
        if session.parent_session_id is None:
            return []

        parent_field_states = await self._field_states.list_by_session(session.parent_session_id)
        inherited: list[str] = []
        for parent_field in parent_field_states:
            if parent_field.field_name not in INHERITABLE_FIELDS:
                continue
            if not parent_field.is_confirmed or not parent_field.confirmed_value:
                continue
            await self._field_states.upsert(
                session_id,
                parent_field.field_name,
                suggested_value=parent_field.confirmed_value,
                suggested_by="parent_session",
            )
            inherited.append(parent_field.field_name)
        return inherited

    async def cancel_session(self, session_id: uuid.UUID, reason: str | None = None) -> Session:
        """Hủy phiên — hợp lệ ở mọi trạng thái chưa kết thúc (xem C1: CANCEL đặc biệt)."""
        session = await self._get_or_raise(session_id)
        next_state = transition(SessionState(session.state), SessionEvent.CANCEL)

        session.state = next_state.value
        session.cancel_reason = reason
        await self._sessions.update(session)

        await self._audit.append(
            actor_type="staff",
            action=AuditAction.SESSION_CANCELLED.value,
            session_id=session.id,
            detail={"reason": reason},
        )
        return session

    async def complete_session(self, session_id: uuid.UUID, dossier_code: str) -> Session:
        """Kết thúc phiên với mã hồ sơ — chỉ hợp lệ khi đã có xác nhận của người dân.

        Việc "đã có xác nhận của người dân" được biểu diễn qua state machine:
        chỉ trạng thái `CITIZEN_CONFIRMED` mới có cạnh `COMPLETE` hợp lệ (C1) —
        `transition()` tự ném `InvalidTransitionError` nếu gọi sớm, không cần
        service này tự kiểm tra điều kiện phụ.
        """
        session = await self._get_or_raise(session_id)
        next_state = transition(SessionState(session.state), SessionEvent.COMPLETE)

        session.state = next_state.value
        session.dossier_code = dossier_code
        session.completed_at = datetime.now(UTC)
        await self._sessions.update(session)

        await self._audit.append(
            actor_type="staff",
            action=AuditAction.SESSION_COMPLETED.value,
            session_id=session.id,
            detail={"dossier_code": dossier_code},
        )
        return session

    async def _get_or_raise(self, session_id: uuid.UUID) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session


def _field_states_to_extracted_map(field_states: list[FieldState]) -> dict[str, ExtractedField]:
    """Chuyển `list[FieldState]` (ORM) thành ánh xạ tên->`ExtractedField` tối
    giản để tái dùng `generate_warnings()` (C6) — vốn nhận `ExtractedField`
    (Pydantic, C5), không phải `FieldState` (ORM, B2).

    Chỉ suy ra `status` từ dữ liệu đã có trong `FieldState`, không có field
    nào khác được `generate_warnings()` dùng tới ngoài `status`.
    """
    result: dict[str, ExtractedField] = {}
    for fs in field_states:
        if fs.confirmed_value or fs.suggested_value:
            status = "extracted"
        elif fs.validation_status == "unclear":
            status = "unclear"
        else:
            status = "missing"
        result[fs.field_name] = ExtractedField(name=fs.field_name, status=status)
    return result
