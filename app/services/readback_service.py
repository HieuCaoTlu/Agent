"""`ReadbackService` — Mục I5 của Checklist, Mục 8.2/9.4 của Plan.

Điều phối bước B6 của quy trình: dựng nội dung đọc lại từ `readback_template`
của catalog (D) + giá trị đã xác nhận (I3), gọi TTS sinh audio với fallback
sang văn bản khi lỗi (NT-2 — luồng dự phòng không có AI vẫn phải hoàn tất
được), và ghi nhận xác nhận/từ chối của người dân (`citizen_confirmations`).

Không tạo bản ghi `CitizenConfirmation` ở `generate_readback()` — bảng
`citizen_confirmations` có `confirmed BOOLEAN NOT NULL` (không có trạng thái
"đang chờ"), nên bản ghi chỉ được tạo tại `record_citizen_confirmation()`, khi
đã biết kết quả. `generate_readback()` chỉ tính `readback_round` kế tiếp (dựa
trên số vòng đã ghi nhận trước đó) để hiển thị cho cán bộ, không lưu gì.

Audio TTS sinh thành công được lưu vào Redis qua `TTSCacheService` (H2, key
cố định theo `session_id` — `store_for_session()`), phục vụ
`GET /sessions/{id}/readback/audio` (J6) tải lại mà không cần gọi lại TTS.
"""

import uuid
from datetime import date

from app.domain.exceptions import DomainError
from app.domain.session_state import SessionEvent, SessionState, transition
from app.models.confirmation import CitizenConfirmation
from app.models.session import Session
from app.repositories.audit_repository import AuditRepository
from app.repositories.citizen_confirmation_repository import CitizenConfirmationRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.services.catalog_service import CatalogService
from app.services.tts_cache_service import TTSCacheService
from app.tts.base import SynthesisResult, TTSProvider
from app.tts.exceptions import TTSError
from app.tts.readback import build_fallback_text, build_readback_text


class SessionNotFoundForReadback(DomainError):
    """Ném ra khi `session_id` không tồn tại."""

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Không tìm thấy phiên có mã '{session_id}'.")


class NoProcedureSelected(DomainError):
    """Ném ra khi phiên chưa chọn thủ tục — không có `readback_template` để dựng nội dung."""

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Phiên '{session_id}' chưa chọn thủ tục, không thể đọc lại.")


class ReadbackOutcome:
    """Kết quả một lần đọc lại — audio (nếu TTS thành công) hoặc fallback văn bản."""

    def __init__(
        self,
        readback_round: int,
        text: str,
        audio_bytes: bytes | None,
        audio_format: str | None,
        used_fallback: bool,
    ) -> None:
        self.readback_round = readback_round
        self.text = text
        self.audio_bytes = audio_bytes
        self.audio_format = audio_format
        self.used_fallback = used_fallback


class ReadbackService:
    def __init__(
        self,
        session_repository: SessionRepository,
        field_state_repository: FieldStateRepository,
        citizen_confirmation_repository: CitizenConfirmationRepository,
        audit_repository: AuditRepository,
        catalog_service: CatalogService,
        tts_provider: TTSProvider,
        tts_cache_service: TTSCacheService,
    ) -> None:
        self._sessions = session_repository
        self._field_states = field_state_repository
        self._confirmations = citizen_confirmation_repository
        self._audit = audit_repository
        self._catalog = catalog_service
        self._tts = tts_provider
        self._tts_cache = tts_cache_service

    async def generate_readback(self, session_id: uuid.UUID) -> ReadbackOutcome:
        """Dựng nội dung đọc lại từ giá trị đã xác nhận, gọi TTS sinh audio.

        Chuyển phiên `FIELDS_CONFIRMED` → `READBACK` qua `transition()` (C1).
        Nếu TTS lỗi (`TTSError`), suy giảm mềm sang trả về văn bản để frontend
        hiển thị cỡ chữ lớn (NT-2) — không ném lỗi ra ngoài, không chặn luồng.
        """
        session = await self._get_session_or_raise(session_id)
        if session.procedure_code is None:
            raise NoProcedureSelected(session_id)

        today = date.today()
        template = self._catalog.get_readback_template(session.procedure_code, today)
        fields = self._catalog.get_field_schema(session.procedure_code, today)

        field_states = await self._field_states.list_by_session(session_id)
        confirmed_values = {
            fs.field_name: fs.confirmed_value for fs in field_states if fs.confirmed_value
        }
        text = build_readback_text(template, confirmed_values, fields)

        session.state = transition(
            SessionState(session.state), SessionEvent.TRIGGER_READBACK
        ).value
        await self._sessions.update(session)

        readback_round = await self._confirmations.next_readback_round(session_id)

        synthesis: SynthesisResult | None = None
        used_fallback = False
        try:
            synthesis = await self._tts.synthesize(text)
        except TTSError:
            used_fallback = True

        await self._audit.append(
            actor_type="system",
            action="readback_played",
            session_id=session_id,
            detail={"readback_round": readback_round, "used_fallback": used_fallback},
        )

        if synthesis is None:
            fallback_text = build_fallback_text(template, confirmed_values, fields)
            return ReadbackOutcome(
                readback_round=readback_round,
                text=fallback_text,
                audio_bytes=None,
                audio_format=None,
                used_fallback=True,
            )

        await self._tts_cache.store_for_session(session_id, synthesis.audio_bytes)

        return ReadbackOutcome(
            readback_round=readback_round,
            text=text,
            audio_bytes=synthesis.audio_bytes,
            audio_format=synthesis.audio_format,
            used_fallback=False,
        )

    async def record_citizen_confirmation(
        self,
        session_id: uuid.UUID,
        confirmed: bool,
        readback_text: str,
        staff_name: str,
        note: str | None = None,
        readback_method: str | None = None,
    ) -> CitizenConfirmation:
        """Lưu xác nhận hoặc từ chối của người dân sau khi nghe/đọc lại.

        Khi từ chối (`confirmed=False`): chuyển phiên về `REVIEWING` (UC4) để
        cán bộ sửa lại trường sai, ghi audit `citizen_rejected`. Khi xác nhận:
        chuyển `CITIZEN_CONFIRMED`, ghi audit `citizen_confirmed`.
        """
        session = await self._get_session_or_raise(session_id)
        readback_round = await self._confirmations.next_readback_round(session_id)

        confirmation = CitizenConfirmation(
            session_id=session_id,
            readback_round=readback_round,
            readback_text=readback_text,
            readback_method=readback_method,
            confirmed=confirmed,
            confirmation_note=note,
            recorded_by=staff_name,
        )
        await self._confirmations.add(confirmation)

        event = SessionEvent.CITIZEN_CONFIRMED if confirmed else SessionEvent.CITIZEN_REJECTED
        session.state = transition(SessionState(session.state), event).value
        await self._sessions.update(session)

        await self._audit.append(
            actor_type="staff",
            action="citizen_confirmed" if confirmed else "citizen_rejected",
            session_id=session_id,
            actor_id=staff_name,
            detail={"readback_round": readback_round, "note": note},
        )
        return confirmation

    async def _get_session_or_raise(self, session_id: uuid.UUID) -> Session:
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundForReadback(session_id)
        return session
