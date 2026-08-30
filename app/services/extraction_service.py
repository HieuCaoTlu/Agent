"""`ExtractionService` — Mục I2 của Checklist, Mục 7/10 của Plan.

Điều phối toàn bộ luồng trích xuất — 12 bước theo Checklist:
gom transcript → field schema → che PII → gọi LLM → parse/validate → kiểm
chứng nguồn gốc → khôi phục PII → validator từng trường → merge → cảnh báo
→ lưu → audit. Mỗi bước có thể lỗi theo cách nghiệp vụ bình thường (LLM lỗi
mạng, JSON sai định dạng...) — service này bắt lỗi ở từng bước và luôn lưu
một `Extraction` phản ánh đúng những gì xảy ra, không để dữ liệu rác/exception
thô lọt lên UI.
"""

import hashlib
import time
import uuid
from dataclasses import dataclass
from datetime import date

from app.catalog.models import FieldSpec
from app.domain.audit_action import AuditAction
from app.domain.exceptions import DomainError, InvalidTransitionError
from app.domain.extraction_schema import (
    ExtractedField,
    ExtractionParseError,
    ExtractionResult,
    parse_extraction_result,
)
from app.domain.merge import MergeResult, merge_field
from app.domain.session_state import SessionEvent, SessionState, transition
from app.domain.validators import validate_all
from app.domain.warnings import Warning as DomainWarning
from app.domain.warnings import generate_warnings
from app.llm.base import LLMProvider
from app.llm.exceptions import LLMError
from app.llm.grounding import verify_grounding
from app.llm.prompt import (
    SYSTEM_PROMPT_V1,
    build_single_field_correction_message,
    build_user_message,
)
from app.llm.redactor import PIIRedactor
from app.models.extraction import Extraction, FieldState
from app.models.session import Session
from app.models.voice import VoiceTurn
from app.repositories.audit_repository import AuditRepository
from app.repositories.extraction_repository import ExtractionRepository
from app.repositories.field_history_repository import FieldHistoryRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.voice_turn_repository import VoiceTurnRepository
from app.services.catalog_service import CatalogService


class SessionNotFoundForExtraction(DomainError):
    """Ném ra khi `session_id` không tồn tại — tách khỏi `SessionNotFound` (I1)
    để `ExtractionService` không phải phụ thuộc ngược vào `session_service`.
    """

    def __init__(self, session_id: uuid.UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Không tìm thấy phiên có mã '{session_id}'.")


class ExtractionLimitExceeded(DomainError):
    """Ném ra khi phiên đã đạt `max_extractions_per_session`."""

    def __init__(self, session_id: uuid.UUID, limit: int) -> None:
        self.session_id = session_id
        self.limit = limit
        super().__init__(
            f"Phiên '{session_id}' đã đạt giới hạn {limit} lần trích xuất. "
            "Hãy chuyển sang nhập tay phần còn lại."
        )


def _advance_state(session: Session, event: SessionEvent) -> None:
    """Cố gắng chuyển `session.state` theo `event` qua `transition()` (C1, L1).

    Khoan dung có chủ đích: nếu `event` không hợp lệ từ trạng thái hiện tại
    (ví dụ trích xuất lại khi phiên đã ở SUGGESTED/REVIEWING — luồng chưa
    được mô hình hóa trong bảng chuyển đổi C1), bỏ qua và giữ nguyên state,
    KHÔNG ném lỗi làm hỏng luồng nghiệp vụ hợp lệ khác. Chỉ áp dụng khi
    `event` thực sự khớp một cạnh trong bảng.
    """
    try:
        next_state = transition(SessionState(session.state), event)
    except InvalidTransitionError:
        return
    session.state = next_state.value


@dataclass(frozen=True)
class ExtractionOutcome:
    """Kết quả một lần gọi `extract()`/`amend_field()` — dùng cho tầng API (J4)."""

    extraction: Extraction
    warnings: list[DomainWarning]


class ExtractionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        voice_turn_repository: VoiceTurnRepository,
        extraction_repository: ExtractionRepository,
        field_state_repository: FieldStateRepository,
        field_history_repository: FieldHistoryRepository,
        audit_repository: AuditRepository,
        catalog_service: CatalogService,
        llm_provider: LLMProvider,
        max_extractions_per_session: int = 5,
    ) -> None:
        self._sessions = session_repository
        self._voice_turns = voice_turn_repository
        self._extractions = extraction_repository
        self._field_states = field_state_repository
        self._field_history = field_history_repository
        self._audit = audit_repository
        self._catalog = catalog_service
        self._llm = llm_provider
        self._max_extractions = max_extractions_per_session

    async def extract(
        self,
        session_id: uuid.UUID,
        include_turns: list[int],
        only_missing: bool = False,
    ) -> ExtractionOutcome:
        """Điều phối toàn bộ luồng trích xuất cho một phiên.

        `include_turns`: danh sách `turn_number` cán bộ chọn đưa vào transcript
        — lựa chọn thủ công, không có bước lọc tự động theo chất lượng (I2).
        """
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundForExtraction(session_id)
        if session.procedure_code is None:
            raise DomainError(f"Phiên '{session_id}' chưa chọn thủ tục, không thể trích xuất.")

        already_done = await self._extractions.count_by_session(session_id)
        if already_done >= self._max_extractions:
            raise ExtractionLimitExceeded(session_id, self._max_extractions)

        # Bước 1: gom transcript từ các lượt đã chọn (theo lựa chọn thủ công của cán bộ).
        all_turns = await self._voice_turns.list_by_session(session_id)
        turns_by_number = {t.turn_number: t for t in all_turns}
        transcript_turns = [
            _turn_text(turns_by_number[n]) for n in include_turns if n in turns_by_number
        ]
        transcript = "\n".join(transcript_turns)

        # Bước 2: field schema từ catalog.
        fields = self._catalog.get_field_schema(session.procedure_code, date.today())

        current_field_states = await self._field_states.list_by_session(session_id)
        confirmed_values = {
            fs.field_name: fs.confirmed_value
            for fs in current_field_states
            if fs.is_confirmed and fs.confirmed_value
        }

        await self._audit.append(
            actor_type="staff",
            action=AuditAction.EXTRACTION_REQUESTED.value,
            session_id=session_id,
            detail={"include_turns": include_turns, "only_missing": only_missing},
        )

        user_message = build_user_message(
            procedure_name=session.procedure_code,
            procedure_code=session.procedure_code,
            fields=fields,
            confirmed_values=confirmed_values,
            transcript_turns=transcript_turns,
            only_missing_fields=only_missing,
        )

        # L1: vào EXTRACTING trước khi gọi LLM — chỉ có hiệu lực từ
        # PROCEDURE_SELECTED (lần trích xuất đầu); các lần gọi lại từ trạng
        # thái khác (SUGGESTED/REVIEWING...) giữ nguyên state (xem _advance_state).
        _advance_state(session, SessionEvent.REQUEST_EXTRACTION)
        await self._sessions.update(session)

        extraction = await self._run_llm_and_save(
            session=session,
            fields=fields,
            transcript=transcript,
            user_message=user_message,
            current_field_states=current_field_states,
            attempt_number=already_done + 1,
        )

        warnings = await self._recompute_warnings(session_id, session.procedure_code)
        return ExtractionOutcome(extraction=extraction, warnings=warnings)

    async def amend_field(
        self, session_id: uuid.UUID, field_name: str, transcript_turns: list[str]
    ) -> ExtractionOutcome:
        """Trích xuất lại MỘT trường (UC4) — không chạy lại toàn bộ pipeline."""
        session = await self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundForExtraction(session_id)
        if session.procedure_code is None:
            raise DomainError(f"Phiên '{session_id}' chưa chọn thủ tục, không thể trích xuất.")

        all_fields = self._catalog.get_field_schema(session.procedure_code, date.today())
        field = next((f for f in all_fields if f.name == field_name), None)
        if field is None:
            raise DomainError(f"Trường '{field_name}' không tồn tại trong thủ tục hiện tại.")

        already_done = await self._extractions.count_by_session(session_id)
        if already_done >= self._max_extractions:
            raise ExtractionLimitExceeded(session_id, self._max_extractions)

        current_field_states = await self._field_states.list_by_session(session_id)
        transcript = "\n".join(transcript_turns)
        user_message = build_single_field_correction_message(field, transcript_turns)

        extraction = await self._run_llm_and_save(
            session=session,
            fields=[field],
            transcript=transcript,
            user_message=user_message,
            current_field_states=current_field_states,
            attempt_number=already_done + 1,
            advance_state=False,
        )

        warnings = await self._recompute_warnings(session_id, session.procedure_code)
        return ExtractionOutcome(extraction=extraction, warnings=warnings)

    async def _run_llm_and_save(
        self,
        session: Session,
        fields: list[FieldSpec],
        transcript: str,
        user_message: str,
        current_field_states: list[FieldState],
        attempt_number: int,
        advance_state: bool = True,
    ) -> Extraction:
        # Bước 3: che dữ liệu nhạy cảm. Redactor sống trong phạm vi một lần
        # gọi (không giữ giữa các request) — bảng ánh xạ CCCD chỉ cần tồn tại
        # đủ lâu để redact prompt rồi restore kết quả ngay sau đó.
        redactor = PIIRedactor()
        redacted_message = redactor.redact(user_message)
        prompt_hash = hashlib.sha256(redacted_message.encode("utf-8")).hexdigest()

        session_id = session.id
        start = time.monotonic()
        try:
            # Bước 4: gọi LLM provider.
            response = await self._llm.extract(SYSTEM_PROMPT_V1, redacted_message)
        except LLMError as exc:
            # L1 (bắt buộc, NT-8): LLM lỗi mạng/API → chuyển phiên sang
            # AI_UNAVAILABLE, cho phép cán bộ nhập tay. Không áp dụng cho
            # parse_failed (JSON sai định dạng không phải lỗi hạ tầng AI —
            # quyết định của người dùng) và không áp dụng khi advance_state=False
            # (amend_field, UC4 — sửa một trường không lùi trạng thái cả phiên).
            if advance_state:
                _advance_state(session, SessionEvent.EXTRACTION_FAILED)
                await self._sessions.update(session)
            return await self._save_failed_extraction(
                session_id=session_id,
                attempt_number=attempt_number,
                prompt_hash=prompt_hash,
                prompt_redacted=redacted_message,
                status="api_error",
                error_detail=str(exc),
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        try:
            # Bước 5: parse và validate schema.
            result = parse_extraction_result(response.raw_text)
        except ExtractionParseError as exc:
            return await self._save_failed_extraction(
                session_id=session_id,
                attempt_number=attempt_number,
                prompt_hash=prompt_hash,
                prompt_redacted=redacted_message,
                status="parse_failed",
                error_detail=str(exc),
                latency_ms=response.latency_ms,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                model_name=response.model,
            )

        # Bước 6: kiểm chứng nguồn gốc (grounding check) — trên transcript ĐÃ che,
        # vì evidence do LLM trả về cũng trích dẫn từ bản đã che.
        grounded_result, grounding_events = verify_grounding(result, redacted_message, fields)

        # Bước 7: khôi phục giá trị đã che (đưa placeholder [CCCD_n] về giá trị thật).
        restored_result = _restore_result(grounded_result, redactor)

        # Bước 8: chạy validator từng trường + Bước 9: gộp với trạng thái hiện có.
        extracted_by_name = {f.name: f for f in restored_result.fields}
        current_by_name = {fs.field_name: fs for fs in current_field_states}

        for field in fields:
            current = current_by_name.get(field.name)
            current_value = current.confirmed_value if current and current.is_confirmed else (
                current.suggested_value if current else None
            )
            is_confirmed = bool(current and current.is_confirmed)
            new_field = extracted_by_name.get(field.name)

            merge_result = merge_field(current_value, is_confirmed, new_field)
            await self._apply_merge_result(session_id, field, current, merge_result, new_field)

        # Bước 11 (phần còn lại): lưu extraction.
        extraction = Extraction(
            session_id=session_id,
            attempt_number=attempt_number,
            model_name=response.model,
            prompt_hash=prompt_hash,
            prompt_redacted=redacted_message,
            raw_response=response.raw_text,
            parsed_json=restored_result.model_dump(),
            warnings=[e.code for e in grounding_events],
            status="success",
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            latency_ms=response.latency_ms,
        )
        await self._extractions.add(extraction)

        # Bước 12: ghi audit (thành công + sự kiện grounding nếu có).
        await self._audit.append(
            actor_type="system",
            action=AuditAction.EXTRACTION_SUCCEEDED.value,
            session_id=session_id,
            detail={"extraction_id": str(extraction.id), "grounding_events": len(grounding_events)},
        )
        for event in grounding_events:
            await self._audit.append(
                actor_type="system",
                action=event.code,
                session_id=session_id,
                detail={"field_name": event.field_name},
            )

        if advance_state:
            _advance_state(session, SessionEvent.EXTRACTION_SUCCESS)
            await self._sessions.update(session)

        return extraction

    async def _apply_merge_result(
        self,
        session_id: uuid.UUID,
        field: FieldSpec,
        current: FieldState | None,
        merge_result: MergeResult,
        new_field: ExtractedField | None,
    ) -> None:
        old_value = current.suggested_value if current else None
        validation_status = None
        validation_message = None
        if field.validators:
            field_validators = {field.name: field.validators}
            field_options = {field.name: field.options} if field.options else None
            results = validate_all(
                {field.name: merge_result.value}, field_validators, field_options
            )
            field_results = results.get(field.name, [])
            if any(not r.valid for r in field_results):
                validation_status = "format_error"
                validation_message = next((r.message for r in field_results if not r.valid), None)
            else:
                validation_status = "ok"

        if merge_result.conflict_with_confirmed:
            return  # giá trị đã xác nhận không bị đổi — không cần upsert lại suggested_value.

        await self._field_states.upsert(
            session_id,
            field.name,
            suggested_value=merge_result.value,
            suggested_by="llm" if new_field is not None else (
                current.suggested_by if current else None
            ),
            ai_confidence=merge_result.confidence,
            evidence_span=merge_result.evidence,
            validation_status=validation_status,
            validation_message=validation_message,
        )

        if merge_result.value != old_value:
            await self._field_history.append(
                session_id=session_id,
                field_name=field.name,
                old_value=old_value,
                new_value=merge_result.value,
                change_source="llm_extraction",
            )

    async def _save_failed_extraction(
        self,
        session_id: uuid.UUID,
        attempt_number: int,
        prompt_hash: str,
        prompt_redacted: str,
        status: str,
        error_detail: str,
        latency_ms: int | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model_name: str | None = None,
    ) -> Extraction:
        extraction = Extraction(
            session_id=session_id,
            attempt_number=attempt_number,
            model_name=model_name,
            prompt_hash=prompt_hash,
            prompt_redacted=prompt_redacted,
            status=status,
            error_detail=error_detail,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        await self._extractions.add(extraction)
        await self._audit.append(
            actor_type="system",
            action=AuditAction.EXTRACTION_FAILED.value,
            session_id=session_id,
            detail={"status": status, "error": error_detail},
        )
        return extraction

    async def _recompute_warnings(
        self, session_id: uuid.UUID, procedure_code: str
    ) -> list[DomainWarning]:
        fields = self._catalog.get_field_schema(procedure_code, date.today())
        field_states = await self._field_states.list_by_session(session_id)
        extracted = {
            fs.field_name: ExtractedField(
                name=fs.field_name,
                status=_status_from_field_state(fs),
            )
            for fs in field_states
        }
        return generate_warnings(fields, extracted)


def _turn_text(voice_turn: VoiceTurn) -> str:
    return voice_turn.edited_transcript or voice_turn.raw_transcript or ""


def _restore_result(result: ExtractionResult, redactor: PIIRedactor) -> ExtractionResult:
    restored_fields = []
    for field in result.fields:
        update = {}
        if field.value:
            update["value"] = redactor.restore(field.value)
        if field.evidence:
            update["evidence"] = redactor.restore(field.evidence)
        restored_fields.append(field.model_copy(update=update) if update else field)
    return ExtractionResult(fields=restored_fields, observations=result.observations)


def _status_from_field_state(fs: FieldState) -> str:
    if fs.confirmed_value or fs.suggested_value:
        return "extracted"
    if fs.validation_status == "unclear":
        return "unclear"
    return "missing"
