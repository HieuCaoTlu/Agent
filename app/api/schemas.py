"""Response/request model Pydantic dùng chung cho mọi router — Mục J7 của Checklist.

Tách khỏi model DB (SQLAlchemy) và dataclass domain thuần — tầng API luôn đi
qua một model Pydantic riêng trước khi trả ra ngoài, không serialize thẳng
ORM object (tránh rò field nội bộ, tránh phụ thuộc ngược DB → HTTP contract).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.catalog.models import Document, FieldSpec
from app.domain.warnings import Warning as DomainWarning
from app.models.confirmation import CitizenConfirmation
from app.models.extraction import Extraction, FieldState
from app.models.session import Session
from app.models.voice import VoiceTurn
from app.services.field_service import FieldWithValidation
from app.services.readback_service import ReadbackOutcome
from app.services.session_service import SessionStateSnapshot


class ProcedureSummaryResponse(BaseModel):
    code: str
    name: str
    catalog_version: str


class ProcedureDetailResponse(BaseModel):
    code: str
    name: str
    catalog_version: str
    legal_basis: str
    fields: list[FieldSpec]
    required_documents: list[Document]


class WarningResponse(BaseModel):
    severity: str
    field: str
    message: str
    code: str

    @classmethod
    def from_domain(cls, warning: DomainWarning) -> "WarningResponse":
        return cls(
            severity=warning.severity, field=warning.field, message=warning.message,
            code=warning.code,
        )


class FieldStateResponse(BaseModel):
    field_name: str
    suggested_value: str | None
    suggested_by: str | None
    ai_confidence: str | None
    evidence_span: str | None
    confirmed_value: str | None
    is_confirmed: bool
    confirmed_by: str | None
    was_edited: bool
    validation_status: str | None
    validation_message: str | None

    @classmethod
    def from_model(cls, field_state: FieldState) -> "FieldStateResponse":
        return cls(
            field_name=field_state.field_name,
            suggested_value=field_state.suggested_value,
            suggested_by=field_state.suggested_by,
            ai_confidence=field_state.ai_confidence,
            evidence_span=field_state.evidence_span,
            confirmed_value=field_state.confirmed_value,
            is_confirmed=field_state.is_confirmed,
            confirmed_by=field_state.confirmed_by,
            was_edited=field_state.was_edited,
            validation_status=field_state.validation_status,
            validation_message=field_state.validation_message,
        )


class ValidationResultResponse(BaseModel):
    valid: bool
    message: str | None


class FieldWithValidationResponse(BaseModel):
    field: FieldStateResponse
    validation_results: list[ValidationResultResponse]

    @classmethod
    def from_domain(cls, item: FieldWithValidation) -> "FieldWithValidationResponse":
        return cls(
            field=FieldStateResponse.from_model(item.field_state),
            validation_results=[
                ValidationResultResponse(valid=r.valid, message=r.message)
                for r in item.validation_results
            ],
        )


class SessionResponse(BaseModel):
    id: uuid.UUID
    parent_session_id: uuid.UUID | None
    staff_name: str
    procedure_code: str | None
    state: str
    mode: str
    citizen_consent: bool
    citizen_ref: str | None
    dossier_code: str | None
    started_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_model(cls, session: Session) -> "SessionResponse":
        return cls(
            id=session.id,
            parent_session_id=session.parent_session_id,
            staff_name=session.staff_name,
            procedure_code=session.procedure_code,
            state=session.state,
            mode=session.mode,
            citizen_consent=session.citizen_consent,
            citizen_ref=session.citizen_ref,
            dossier_code=session.dossier_code,
            started_at=session.started_at,
            completed_at=session.completed_at,
        )


class SessionStateResponse(BaseModel):
    session: SessionResponse
    field_states: list[FieldStateResponse]
    warnings: list[WarningResponse]

    @classmethod
    def from_domain(cls, snapshot: SessionStateSnapshot) -> "SessionStateResponse":
        return cls(
            session=SessionResponse.from_model(snapshot.session),
            field_states=[FieldStateResponse.from_model(fs) for fs in snapshot.field_states],
            warnings=[WarningResponse.from_domain(w) for w in snapshot.warnings],
        )


class CreateSessionRequest(BaseModel):
    staff_name: str
    parent_session_id: uuid.UUID | None = None
    mode: str = "ai_assisted"


class ConsentRequest(BaseModel):
    consented: bool


class SelectProcedureRequest(BaseModel):
    code: str


class CancelSessionRequest(BaseModel):
    reason: str | None = None


class CompleteSessionRequest(BaseModel):
    dossier_code: str


class VoiceTurnResponse(BaseModel):
    id: uuid.UUID
    turn_number: int
    raw_transcript: str | None
    edited_transcript: str | None
    flagged_by_staff: bool
    audio_deleted_at: datetime | None

    @classmethod
    def from_model(cls, voice_turn: VoiceTurn) -> "VoiceTurnResponse":
        return cls(
            id=voice_turn.id,
            turn_number=voice_turn.turn_number,
            raw_transcript=voice_turn.raw_transcript,
            edited_transcript=voice_turn.edited_transcript,
            flagged_by_staff=voice_turn.flagged_by_staff,
            audio_deleted_at=voice_turn.audio_deleted_at,
        )


class EditTranscriptRequest(BaseModel):
    new_text: str
    staff_name: str


class FlagTranscriptRequest(BaseModel):
    staff_name: str


class ExtractionResponse(BaseModel):
    id: uuid.UUID
    attempt_number: int
    status: str
    error_detail: str | None
    warnings: list[WarningResponse]
    created_at: datetime

    @classmethod
    def from_domain(
        cls, extraction: Extraction, warnings: list[DomainWarning]
    ) -> "ExtractionResponse":
        return cls(
            id=extraction.id,
            attempt_number=extraction.attempt_number,
            status=extraction.status,
            error_detail=extraction.error_detail,
            warnings=[WarningResponse.from_domain(w) for w in warnings],
            created_at=extraction.created_at,
        )

    @classmethod
    def from_model_only(cls, extraction: Extraction) -> "ExtractionResponse":
        """Dùng cho lịch sử (`GET /extractions`, J4) — không có `warnings` tính lại."""
        return cls(
            id=extraction.id,
            attempt_number=extraction.attempt_number,
            status=extraction.status,
            error_detail=extraction.error_detail,
            warnings=[],
            created_at=extraction.created_at,
        )


class ExtractRequest(BaseModel):
    include_turns: list[int]
    only_missing: bool = False


class AmendFieldRequest(BaseModel):
    transcript_turns: list[str]


class ConfirmFieldRequest(BaseModel):
    value: str
    staff_name: str


class ReadbackResponse(BaseModel):
    readback_round: int
    text: str
    audio_available: bool
    used_fallback: bool

    @classmethod
    def from_domain(cls, outcome: ReadbackOutcome) -> "ReadbackResponse":
        return cls(
            readback_round=outcome.readback_round,
            text=outcome.text,
            audio_available=outcome.audio_bytes is not None,
            used_fallback=outcome.used_fallback,
        )


class CitizenConfirmRequest(BaseModel):
    confirmed: bool
    readback_text: str
    staff_name: str
    note: str | None = None
    readback_method: str | None = None


class CitizenConfirmationResponse(BaseModel):
    id: uuid.UUID
    readback_round: int
    confirmed: bool
    confirmation_note: str | None
    recorded_by: str
    created_at: datetime

    @classmethod
    def from_model(cls, confirmation: CitizenConfirmation) -> "CitizenConfirmationResponse":
        return cls(
            id=confirmation.id,
            readback_round=confirmation.readback_round,
            confirmed=confirmation.confirmed,
            confirmation_note=confirmation.confirmation_note,
            recorded_by=confirmation.recorded_by,
            created_at=confirmation.created_at,
        )


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: str | None = None
    request_id: str
    fallback_available: bool = False


class ErrorResponse(BaseModel):
    error: ErrorDetail
