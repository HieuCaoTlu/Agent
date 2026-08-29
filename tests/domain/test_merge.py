"""Test quy tắc gộp dữ liệu qua nhiều lượt — Mục 7.1 của Plan."""

from app.domain.extraction_schema import ExtractedField
from app.domain.merge import merge_field


def _extracted(value: str, confidence: str = "high", evidence: str = "ev") -> ExtractedField:
    return ExtractedField(
        name="x", status="extracted", value=value, confidence=confidence, evidence=evidence
    )


def _missing() -> ExtractedField:
    return ExtractedField(name="x", status="missing")


def test_empty_current_receives_new_value() -> None:
    result = merge_field(current_value=None, is_confirmed=False, new_field=_extracted("A"))
    assert result.value == "A"
    assert result.changed_from_previous is False
    assert result.conflict_with_confirmed is False


def test_missing_current_receives_new_value() -> None:
    result = merge_field(current_value="", is_confirmed=False, new_field=_extracted("A"))
    assert result.value == "A"


def test_unconfirmed_different_value_replaced_and_flagged_changed() -> None:
    result = merge_field(current_value="A", is_confirmed=False, new_field=_extracted("B"))
    assert result.value == "B"
    assert result.changed_from_previous is True
    assert result.conflict_with_confirmed is False


def test_confirmed_different_value_keeps_confirmed_and_flags_conflict() -> None:
    result = merge_field(current_value="A", is_confirmed=True, new_field=_extracted("B"))
    assert result.value == "A"
    assert result.conflict_with_confirmed is True
    assert result.changed_from_previous is False


def test_new_missing_keeps_old_value() -> None:
    result = merge_field(current_value="A", is_confirmed=False, new_field=_missing())
    assert result.value == "A"
    assert result.changed_from_previous is False
    assert result.conflict_with_confirmed is False


def test_new_missing_keeps_old_value_even_when_confirmed() -> None:
    result = merge_field(current_value="A", is_confirmed=True, new_field=_missing())
    assert result.value == "A"
    assert result.conflict_with_confirmed is False


def test_field_absent_from_llm_response_treated_as_missing() -> None:
    result = merge_field(current_value="A", is_confirmed=False, new_field=None)
    assert result.value == "A"


def test_same_value_again_not_flagged_as_changed() -> None:
    result = merge_field(current_value="A", is_confirmed=False, new_field=_extracted("A"))
    assert result.value == "A"
    assert result.changed_from_previous is False


def test_unclear_status_treated_as_no_new_value() -> None:
    unclear = ExtractedField(name="x", status="unclear", reason="mơ hồ")
    result = merge_field(current_value="A", is_confirmed=False, new_field=unclear)
    assert result.value == "A"
