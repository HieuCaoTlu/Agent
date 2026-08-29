"""State machine của phiên — Mục 5.2/5.3 của Plan (rút gọn — Mục C1 của Checklist).

Logic thuần, không import bất kỳ thứ gì liên quan I/O (không DB, không HTTP,
không Redis) — đúng yêu cầu của Checklist mục C.

Bản rút gọn: `transition()` chỉ tra bảng chuyển đổi (current, event) -> next,
KHÔNG kiểm tra điều kiện phụ (context) như procedure_code_in_catalog,
has_dossier_code... — các điều kiện đó, nếu cần, được service tầng trên
(ngoài phạm vi C) tự kiểm tra trước khi gọi transition().
"""

from enum import StrEnum

from app.domain.exceptions import InvalidTransitionError


class SessionState(StrEnum):
    CREATED = "CREATED"
    LISTENING = "LISTENING"
    PROCEDURE_SELECTED = "PROCEDURE_SELECTED"
    EXTRACTING = "EXTRACTING"
    SUGGESTED = "SUGGESTED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"
    REVIEWING = "REVIEWING"
    FIELDS_CONFIRMED = "FIELDS_CONFIRMED"
    READBACK = "READBACK"
    CITIZEN_CONFIRMED = "CITIZEN_CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SessionEvent(StrEnum):
    START_LISTENING = "start_listening"
    SELECT_PROCEDURE = "select_procedure"
    REQUEST_EXTRACTION = "request_extraction"
    EXTRACTION_SUCCESS = "extraction_success"
    EXTRACTION_FAILED = "extraction_failed"
    OPEN_REVIEW = "open_review"
    MANUAL_ENTRY = "manual_entry"
    ASK_AGAIN = "ask_again"
    ALL_REQUIRED_CONFIRMED = "all_required_confirmed"
    TRIGGER_READBACK = "trigger_readback"
    CITIZEN_REJECTED = "citizen_rejected"
    CITIZEN_CONFIRMED = "citizen_confirmed"
    COMPLETE = "complete"
    CANCEL = "cancel"


# Bảng chuyển đổi hợp lệ — Mục 5.3 của Plan. Khóa là (trạng thái hiện tại, sự kiện).
# CANCEL được xử lý riêng ở transition() vì áp dụng cho "bất kỳ" trạng thái.
_TRANSITIONS: dict[tuple[SessionState, SessionEvent], SessionState] = {
    (SessionState.CREATED, SessionEvent.START_LISTENING): SessionState.LISTENING,
    (SessionState.LISTENING, SessionEvent.SELECT_PROCEDURE): SessionState.PROCEDURE_SELECTED,
    (SessionState.PROCEDURE_SELECTED, SessionEvent.REQUEST_EXTRACTION): SessionState.EXTRACTING,
    (SessionState.EXTRACTING, SessionEvent.EXTRACTION_SUCCESS): SessionState.SUGGESTED,
    (SessionState.EXTRACTING, SessionEvent.EXTRACTION_FAILED): SessionState.AI_UNAVAILABLE,
    (SessionState.SUGGESTED, SessionEvent.OPEN_REVIEW): SessionState.REVIEWING,
    (SessionState.AI_UNAVAILABLE, SessionEvent.MANUAL_ENTRY): SessionState.REVIEWING,
    (SessionState.REVIEWING, SessionEvent.ASK_AGAIN): SessionState.LISTENING,
    (SessionState.REVIEWING, SessionEvent.ALL_REQUIRED_CONFIRMED): SessionState.FIELDS_CONFIRMED,
    (SessionState.FIELDS_CONFIRMED, SessionEvent.TRIGGER_READBACK): SessionState.READBACK,
    (SessionState.READBACK, SessionEvent.CITIZEN_REJECTED): SessionState.REVIEWING,
    (SessionState.READBACK, SessionEvent.CITIZEN_CONFIRMED): SessionState.CITIZEN_CONFIRMED,
    (SessionState.CITIZEN_CONFIRMED, SessionEvent.COMPLETE): SessionState.COMPLETED,
}


def transition(current: SessionState, event: SessionEvent) -> SessionState:
    """Tính trạng thái kế tiếp từ (current, event).

    Ném `InvalidTransitionError` (thông báo tiếng Việt) nếu không có cạnh nào
    từ `current` qua `event` trong bảng chuyển đổi (và đây không phải sự kiện
    `cancel`, vốn áp dụng cho mọi trạng thái chưa kết thúc).
    """
    if event == SessionEvent.CANCEL:
        if current in (SessionState.COMPLETED, SessionState.CANCELLED):
            raise InvalidTransitionError(
                current_state=current,
                event=event,
                message=f"Không thể hủy phiên đã ở trạng thái kết thúc ({current}).",
            )
        return SessionState.CANCELLED

    next_state = _TRANSITIONS.get((current, event))
    if next_state is None:
        raise InvalidTransitionError(current_state=current, event=event)
    return next_state


def is_terminal(state: SessionState) -> bool:
    """Trạng thái kết thúc — không còn chuyển đổi nào khác ngoài giữ nguyên."""
    return state in (SessionState.COMPLETED, SessionState.CANCELLED)
