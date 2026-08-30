/**
 * Type TypeScript tương ứng với schema Pydantic của backend
 * (`app/api/schemas.py`, `app/catalog/models.py`) — Mục M2 của Checklist.
 *
 * Viết tay đối chiếu trực tiếp với schema Pydantic thay vì chạy công cụ
 * sinh type từ OpenAPI runtime (`openapi-typescript`...) — môi trường build
 * không có backend đang chạy để introspect `/openapi.json` tại thời điểm
 * này. Nếu cần tự động hóa sau này: `npx openapi-typescript http://localhost:8000/openapi.json -o src/types/api.generated.ts`.
 */

export type FieldType =
  | 'person_name'
  | 'date'
  | 'national_id'
  | 'phone'
  | 'address'
  | 'enum'
  | 'text'

export interface FieldSpec {
  name: string
  label: string
  type: FieldType
  required: boolean
  sensitive: boolean
  redact_to_llm: boolean
  options: string[] | null
  spoken_hint: string | null
  validators: string[]
}

export interface DocumentSpec {
  name: string
  note: string | null
}

export interface ProcedureSummary {
  code: string
  name: string
  catalog_version: string
}

export interface ProcedureDetail extends ProcedureSummary {
  legal_basis: string
  fields: FieldSpec[]
  required_documents: DocumentSpec[]
}

export interface Warning {
  severity: string
  field: string
  message: string
  code: string
}

export interface FieldState {
  field_name: string
  suggested_value: string | null
  suggested_by: string | null
  ai_confidence: string | null
  evidence_span: string | null
  confirmed_value: string | null
  is_confirmed: boolean
  confirmed_by: string | null
  was_edited: boolean
  validation_status: string | null
  validation_message: string | null
}

export interface ValidationResult {
  valid: boolean
  message: string | null
}

export interface FieldWithValidation {
  field: FieldState
  validation_results: ValidationResult[]
}

/** Khớp `app/domain/session_state.py::SessionState` (C1). */
export type SessionState =
  | 'CREATED'
  | 'LISTENING'
  | 'PROCEDURE_SELECTED'
  | 'EXTRACTING'
  | 'SUGGESTED'
  | 'AI_UNAVAILABLE'
  | 'REVIEWING'
  | 'FIELDS_CONFIRMED'
  | 'READBACK'
  | 'CITIZEN_CONFIRMED'
  | 'COMPLETED'
  | 'CANCELLED'

export interface Session {
  id: string
  parent_session_id: string | null
  staff_name: string
  procedure_code: string | null
  state: SessionState
  mode: string
  citizen_consent: boolean
  citizen_ref: string | null
  dossier_code: string | null
  started_at: string
  completed_at: string | null
}

export interface SessionStateSnapshot {
  session: Session
  field_states: FieldState[]
  warnings: Warning[]
}

export interface CreateSessionRequest {
  staff_name: string
  parent_session_id?: string | null
  mode?: string
}

export interface VoiceTurn {
  id: string
  turn_number: number
  raw_transcript: string | null
  edited_transcript: string | null
  flagged_by_staff: boolean
  audio_deleted_at: string | null
}

export interface Extraction {
  id: string
  attempt_number: number
  status: string
  error_detail: string | null
  warnings: Warning[]
  created_at: string
}

export interface ReadbackOutcome {
  readback_round: number
  text: string
  audio_available: boolean
  used_fallback: boolean
}

export interface CitizenConfirmation {
  id: string
  readback_round: number
  confirmed: boolean
  confirmation_note: string | null
  recorded_by: string
  created_at: string
}

export interface ApiErrorDetail {
  code: string
  message: string
  detail: string | null
  request_id: string
  fallback_available: boolean
}

export interface ApiErrorBody {
  error: ApiErrorDetail
}
