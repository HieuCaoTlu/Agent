from app.domain.audit_action import AuditAction


def test_audit_action_has_seven_values() -> None:
    assert len(list(AuditAction)) == 7


def test_audit_action_values_match_names() -> None:
    assert AuditAction.SESSION_CREATED == "session_created"
    assert AuditAction.EXTRACTION_REQUESTED == "extraction_requested"
    assert AuditAction.EXTRACTION_SUCCEEDED == "extraction_succeeded"
    assert AuditAction.EXTRACTION_FAILED == "extraction_failed"
    assert AuditAction.FIELD_CONFIRMED == "field_confirmed"
    assert AuditAction.SESSION_COMPLETED == "session_completed"
    assert AuditAction.SESSION_CANCELLED == "session_cancelled"
