from app.domain.audit_action import AuditAction


def test_audit_action_has_ten_values() -> None:
    assert len(list(AuditAction)) == 10


def test_audit_action_values_match_names() -> None:
    assert AuditAction.SESSION_CREATED == "session_created"
    assert AuditAction.EXTRACTION_REQUESTED == "extraction_requested"
    assert AuditAction.EXTRACTION_SUCCEEDED == "extraction_succeeded"
    assert AuditAction.EXTRACTION_FAILED == "extraction_failed"
    assert AuditAction.FIELD_CONFIRMED == "field_confirmed"
    assert AuditAction.SESSION_COMPLETED == "session_completed"
    assert AuditAction.SESSION_CANCELLED == "session_cancelled"
    assert AuditAction.TRANSCRIPT_FLAGGED_BY_STAFF == "transcript_flagged_by_staff"
    assert AuditAction.PROCEDURE_SELECTED == "procedure_selected"
    assert AuditAction.FIELDS_CONFIRMED == "fields_confirmed"
