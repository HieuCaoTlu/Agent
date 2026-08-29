from app.catalog.models import FieldSpec
from app.domain.extraction_schema import ExtractedField, ExtractionResult
from app.llm.grounding import verify_grounding

_TRANSCRIPT = "Tôi muốn đăng ký khai sinh cho con tôi tên Nguyễn Văn An, sinh ngày 5 tháng 3."
_SCHEMA = [
    FieldSpec(name="ho_ten", label="Họ tên", type="person_name", required=True),
    FieldSpec(name="ngay_sinh", label="Ngày sinh", type="date", required=True),
]


def test_field_with_grounded_evidence_kept_unchanged() -> None:
    result = ExtractionResult(
        fields=[
            ExtractedField(
                name="ho_ten",
                status="extracted",
                value="Nguyễn Văn An",
                confidence="high",
                evidence="con tôi tên Nguyễn Văn An",
            )
        ]
    )
    verified, events = verify_grounding(result, _TRANSCRIPT, _SCHEMA)

    assert verified.fields[0].confidence == "high"
    assert events == []


def test_field_outside_schema_is_dropped_and_logged() -> None:
    result = ExtractionResult(
        fields=[
            ExtractedField(name="ho_ten", status="missing"),
            ExtractedField(name="truong_la_khong_ton_tai", status="extracted", value="x"),
        ]
    )
    verified, events = verify_grounding(result, _TRANSCRIPT, _SCHEMA)

    assert [f.name for f in verified.fields] == ["ho_ten"]
    assert len(events) == 1
    assert events[0].code == "schema_violation_detected"
    assert events[0].field_name == "truong_la_khong_ton_tai"


def test_extracted_field_without_evidence_flagged_unverifiable() -> None:
    result = ExtractionResult(
        fields=[ExtractedField(name="ho_ten", status="extracted", value="X", evidence=None)]
    )
    verified, events = verify_grounding(result, _TRANSCRIPT, _SCHEMA)

    assert verified.fields[0].confidence == "low"
    assert verified.fields[0].reason is not None
    assert "unverifiable" in verified.fields[0].reason
    assert events[0].code == "unverifiable_value_flagged"


def test_extracted_field_with_evidence_not_in_transcript_flagged() -> None:
    result = ExtractionResult(
        fields=[
            ExtractedField(
                name="ho_ten",
                status="extracted",
                value="X",
                evidence="một câu hoàn toàn không liên quan tới transcript gốc",
            )
        ]
    )
    verified, events = verify_grounding(result, _TRANSCRIPT, _SCHEMA)

    assert verified.fields[0].confidence == "low"
    assert events[0].code == "unverifiable_value_flagged"


def test_missing_and_unclear_fields_not_checked_for_grounding() -> None:
    result = ExtractionResult(
        fields=[
            ExtractedField(name="ho_ten", status="missing"),
            ExtractedField(name="ngay_sinh", status="unclear", reason="không rõ ngày"),
        ]
    )
    verified, events = verify_grounding(result, _TRANSCRIPT, _SCHEMA)

    assert verified.fields[0].status == "missing"
    assert verified.fields[1].status == "unclear"
    assert events == []


def test_observations_pass_through_unchanged() -> None:
    result = ExtractionResult(fields=[], observations=["ghi chú trung lập"])
    verified, _ = verify_grounding(result, _TRANSCRIPT, _SCHEMA)
    assert verified.observations == ["ghi chú trung lập"]
