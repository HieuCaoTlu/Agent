import pytest

from app.domain.exceptions import InvalidTransitionError
from app.domain.session_state import SessionEvent, SessionState, is_terminal, transition


def test_transition_happy_path_full_flow() -> None:
    state = SessionState.CREATED
    state = transition(state, SessionEvent.START_LISTENING)
    assert state == SessionState.LISTENING
    state = transition(state, SessionEvent.SELECT_PROCEDURE)
    assert state == SessionState.PROCEDURE_SELECTED
    state = transition(state, SessionEvent.REQUEST_EXTRACTION)
    assert state == SessionState.EXTRACTING
    state = transition(state, SessionEvent.EXTRACTION_SUCCESS)
    assert state == SessionState.SUGGESTED
    state = transition(state, SessionEvent.OPEN_REVIEW)
    assert state == SessionState.REVIEWING
    state = transition(state, SessionEvent.ALL_REQUIRED_CONFIRMED)
    assert state == SessionState.FIELDS_CONFIRMED
    state = transition(state, SessionEvent.TRIGGER_READBACK)
    assert state == SessionState.READBACK
    state = transition(state, SessionEvent.CITIZEN_CONFIRMED)
    assert state == SessionState.CITIZEN_CONFIRMED
    state = transition(state, SessionEvent.COMPLETE)
    assert state == SessionState.COMPLETED


def test_extraction_failed_leads_to_manual_entry() -> None:
    state = transition(SessionState.EXTRACTING, SessionEvent.EXTRACTION_FAILED)
    assert state == SessionState.AI_UNAVAILABLE
    state = transition(state, SessionEvent.MANUAL_ENTRY)
    assert state == SessionState.REVIEWING


def test_citizen_rejected_returns_to_reviewing() -> None:
    state = transition(SessionState.READBACK, SessionEvent.CITIZEN_REJECTED)
    assert state == SessionState.REVIEWING


def test_ask_again_returns_to_listening() -> None:
    state = transition(SessionState.REVIEWING, SessionEvent.ASK_AGAIN)
    assert state == SessionState.LISTENING


def test_cancel_valid_from_non_terminal_state() -> None:
    for state in (
        SessionState.CREATED,
        SessionState.LISTENING,
        SessionState.PROCEDURE_SELECTED,
        SessionState.EXTRACTING,
        SessionState.SUGGESTED,
        SessionState.AI_UNAVAILABLE,
        SessionState.REVIEWING,
        SessionState.FIELDS_CONFIRMED,
        SessionState.READBACK,
        SessionState.CITIZEN_CONFIRMED,
    ):
        assert transition(state, SessionEvent.CANCEL) == SessionState.CANCELLED


def test_cancel_rejected_from_completed() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(SessionState.COMPLETED, SessionEvent.CANCEL)


def test_cancel_rejected_from_cancelled() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(SessionState.CANCELLED, SessionEvent.CANCEL)


def test_invalid_edge_raises() -> None:
    with pytest.raises(InvalidTransitionError) as exc_info:
        transition(SessionState.CREATED, SessionEvent.COMPLETE)
    assert exc_info.value.current_state == SessionState.CREATED
    assert exc_info.value.event == SessionEvent.COMPLETE
    assert exc_info.value.message  # thông báo tiếng Việt không rỗng


def test_no_edge_out_of_terminal_states() -> None:
    for event in SessionEvent:
        if event == SessionEvent.CANCEL:
            continue
        with pytest.raises(InvalidTransitionError):
            transition(SessionState.COMPLETED, event)
        with pytest.raises(InvalidTransitionError):
            transition(SessionState.CANCELLED, event)


def test_is_terminal() -> None:
    assert is_terminal(SessionState.COMPLETED) is True
    assert is_terminal(SessionState.CANCELLED) is True
    assert is_terminal(SessionState.CREATED) is False
    assert is_terminal(SessionState.REVIEWING) is False
