import json

import pytest

from app.domain.extraction_schema import (
    ExtractedField,
    ExtractionParseError,
    ExtractionResult,
    extraction_result_json_schema,
    parse_extraction_result,
)


def test_parse_valid_json() -> None:
    raw = json.dumps(
        {
            "fields": [
                {
                    "name": "ho_ten",
                    "status": "extracted",
                    "value": "Nguyễn Văn A",
                    "confidence": "high",
                    "evidence": "tôi tên là Nguyễn Văn A",
                },
                {"name": "so_dien_thoai", "status": "missing"},
            ],
            "observations": ["Công dân nói nhanh, có thể cần đọc lại số điện thoại"],
        }
    )
    result = parse_extraction_result(raw)
    assert isinstance(result, ExtractionResult)
    assert len(result.fields) == 2
    assert result.fields[0].name == "ho_ten"
    assert result.fields[0].status == "extracted"
    assert result.fields[1].status == "missing"
    assert result.observations == ["Công dân nói nhanh, có thể cần đọc lại số điện thoại"]


def test_parse_minimal_json_without_optional_fields() -> None:
    raw = json.dumps({"fields": [{"name": "x", "status": "unclear"}]})
    result = parse_extraction_result(raw)
    assert result.fields[0].value is None
    assert result.fields[0].confidence is None
    assert result.observations == []


def test_parse_invalid_json_raises_parse_error_with_raw_text() -> None:
    raw = "khong phai json"
    with pytest.raises(ExtractionParseError) as exc_info:
        parse_extraction_result(raw)
    assert exc_info.value.raw_text == raw


def test_parse_json_not_matching_schema_raises_parse_error() -> None:
    raw = json.dumps({"fields": [{"name": "x", "status": "khong_hop_le"}]})
    with pytest.raises(ExtractionParseError) as exc_info:
        parse_extraction_result(raw)
    assert exc_info.value.raw_text == raw


def test_parse_missing_required_field_raises_parse_error() -> None:
    raw = json.dumps({"fields": [{"status": "missing"}]})  # thiếu "name"
    with pytest.raises(ExtractionParseError):
        parse_extraction_result(raw)


def test_extracted_field_direct_construction() -> None:
    field = ExtractedField(
        name="cccd", status="extracted", value="123456789012", confidence="medium"
    )
    assert field.reason is None


def test_json_schema_has_expected_shape() -> None:
    schema = extraction_result_json_schema()
    assert schema["type"] == "object"
    assert "fields" in schema["properties"]
    assert "observations" in schema["properties"]
