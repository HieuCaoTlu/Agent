"""`FieldService` — Mục I3 của Checklist.

Điều phối việc cán bộ xác nhận/bỏ xác nhận từng trường dữ liệu. Tự động
chuyển phiên sang `FIELDS_CONFIRMED` khi đủ trường bắt buộc đã xác nhận (qua
`transition()`, C1) — không tự phát minh điều kiện, chỉ kiểm tra "đủ trường
bắt buộc" rồi gọi state machine.
"""

import uuid
from datetime import UTC, date, datetime

from app.catalog.models import FieldSpec
from app.domain.audit_action import AuditAction
from app.domain.exceptions import DomainError
from app.domain.session_state import SessionEvent, SessionState, transition
from app.domain.validators import ValidationResult, validate_all
from app.models.extraction import FieldState
from app.models.session import Session
from app.repositories.audit_repository import AuditRepository
from app.repositories.field_history_repository import FieldHistoryRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.services.catalog_service import CatalogService


class SessionNotFoundForField(DomainError):
    """Ném ra khi `session_id` không tồn tại."""

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Không tìm thấy phiên có mã '{session_id}'.")


class FieldNotFound(DomainError):
    """Ném ra khi tên trường không thuộc thủ tục hiện tại của phiên."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(f"Trường '{field_name}' không tồn tại trong thủ tục hiện tại.")


class FieldWithValidation:
    """Một `FieldState` kèm kết quả validate hiện tại — dùng cho `get_fields()` (J5)."""

    def __init__(self, field_state: FieldState, validation_results: list[ValidationResult]) -> None:
        self.field_state = field_state
        self.validation_results = validation_results


class FieldService:
    def __init__(
        self,
        session_repository: SessionRepository,
        field_state_repository: FieldStateRepository,
        field_history_repository: FieldHistoryRepository,
        audit_repository: AuditRepository,
        catalog_service: CatalogService,
    ) -> None:
        self._sessions = session_repository
        self._field_states = field_state_repository
        self._field_history = field_history_repository
        self._audit = audit_repository
        self._catalog = catalog_service

    async def confirm_field(
        self, session_id: uuid.UUID, field_name: str, value: str, staff_name: str
    ) -> FieldState:
        """Cán bộ chốt giá trị một trường sau khi đối chiếu giấy tờ gốc.

        `was_edited=True` khi giá trị khác gợi ý AI (`suggested_value`) —
        không so sánh với `confirmed_value` cũ, vì mục đích của cờ này là báo
        hiệu "cán bộ có tin AI không", không phải "có sửa so với lần xác nhận
        trước". Tự động chuyển `FIELDS_CONFIRMED` nếu sau khi xác nhận, mọi
        trường bắt buộc đã có `confirmed_value`.
        """
        session = await self._get_session_or_raise(session_id)
        self._get_field_spec_or_raise(session.procedure_code, field_name)

        current = await self._field_states.get(session_id, field_name)
        old_value = current.confirmed_value if current else None
        suggested = current.suggested_value if current else None
        was_edited = suggested is not None and suggested != value

        updated = await self._field_states.upsert(
            session_id,
            field_name,
            confirmed_value=value,
            is_confirmed=True,
            confirmed_by=staff_name,
            confirmed_at=datetime.now(UTC),
            was_edited=was_edited,
        )

        await self._field_history.append(
            session_id=session_id,
            field_name=field_name,
            old_value=old_value,
            new_value=value,
            change_source="staff_edit" if was_edited else "staff_confirm",
            changed_by=staff_name,
        )
        await self._audit.append(
            actor_type="staff",
            action=AuditAction.FIELD_CONFIRMED.value,
            session_id=session_id,
            actor_id=staff_name,
            detail={"field_name": field_name, "was_edited": was_edited},
        )

        await self._maybe_advance_to_fields_confirmed(session)
        return updated

    async def unconfirm_field(self, session_id: uuid.UUID, field_name: str) -> FieldState:
        """Bỏ xác nhận một trường — dùng khi người dân yêu cầu sửa (UC4/UC5).

        Giữ nguyên `confirmed_value` cũ (không xóa dữ liệu, giống quy tắc
        merge C7.1) — chỉ đặt `is_confirmed=False` để buộc cán bộ xác nhận
        lại trước khi phiên có thể tiến tiếp.
        """
        await self._get_session_or_raise(session_id)
        current = await self._field_states.get(session_id, field_name)
        if current is None:
            raise FieldNotFound(field_name)

        return await self._field_states.upsert(session_id, field_name, is_confirmed=False)

    async def get_fields(self, session_id: uuid.UUID) -> list[FieldWithValidation]:
        """Trạng thái mọi trường của phiên kèm kết quả validate hiện tại (J5)."""
        session = await self._get_session_or_raise(session_id)
        field_states = await self._field_states.list_by_session(session_id)

        if session.procedure_code is None:
            return [FieldWithValidation(fs, []) for fs in field_states]

        fields = self._catalog.get_field_schema(session.procedure_code, date.today())
        field_spec_by_name = {f.name: f for f in fields}

        values = {
            fs.field_name: fs.confirmed_value or fs.suggested_value for fs in field_states
        }
        field_validators = {
            fs.field_name: field_spec_by_name[fs.field_name].validators
            for fs in field_states
            if fs.field_name in field_spec_by_name and field_spec_by_name[fs.field_name].validators
        }
        field_options = {
            name: field_spec_by_name[name].options
            for name in field_validators
            if field_spec_by_name[name].options
        }
        all_results = validate_all(values, field_validators, field_options)

        return [
            FieldWithValidation(fs, all_results.get(fs.field_name, [])) for fs in field_states
        ]

    async def _maybe_advance_to_fields_confirmed(self, session: Session) -> None:
        if SessionState(session.state) != SessionState.REVIEWING:
            return  # chỉ tự động chuyển khi đang ở REVIEWING — tránh nhảy trạng thái bất ngờ.

        fields = self._catalog.get_field_schema(session.procedure_code, date.today())
        required_names = {f.name for f in fields if f.required}
        field_states = await self._field_states.list_by_session(session.id)
        confirmed_names = {
            fs.field_name for fs in field_states if fs.is_confirmed and fs.confirmed_value
        }

        if required_names.issubset(confirmed_names):
            session.state = transition(
                SessionState.REVIEWING, SessionEvent.ALL_REQUIRED_CONFIRMED
            ).value
            await self._sessions.update(session)
            await self._audit.append(
                actor_type="system",
                action=AuditAction.FIELDS_CONFIRMED.value,
                session_id=session.id,
                detail={"required_field_count": len(required_names)},
            )

    async def _get_session_or_raise(self, session_id: uuid.UUID) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundForField(session_id)
        return session

    def _get_field_spec_or_raise(self, procedure_code: str | None, field_name: str) -> FieldSpec:
        if procedure_code is None:
            raise FieldNotFound(field_name)
        fields = self._catalog.get_field_schema(procedure_code, date.today())
        field_spec = next((f for f in fields if f.name == field_name), None)
        if field_spec is None:
            raise FieldNotFound(field_name)
        return field_spec
