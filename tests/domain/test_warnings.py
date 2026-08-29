from app.catalog.models import FieldSpec
from app.domain.extraction_schema import ExtractedField
from app.domain.warnings import generate_warnings

_HO_TEN = FieldSpec(name="ho_ten", label="Họ và tên", type="person_name", required=True)
_CCCD = FieldSpec(name="cccd", label="Số CCCD", type="national_id", required=True)
_GHI_CHU = FieldSpec(name="ghi_chu", label="Ghi chú", type="text", required=False)


def test_required_missing_field_generates_error() -> None:
    extracted = {"cccd": ExtractedField(name="cccd", status="extracted", value="123456789012")}
    warnings = generate_warnings([_HO_TEN, _CCCD], extracted)

    assert len(warnings) == 1
    assert warnings[0].severity == "error"
    assert warnings[0].field == "ho_ten"
    assert warnings[0].code == "required_missing"


def test_required_field_absent_from_extracted_dict_counts_as_missing() -> None:
    warnings = generate_warnings([_HO_TEN], extracted={})
    assert len(warnings) == 1
    assert warnings[0].severity == "error"


def test_unclear_field_generates_warning() -> None:
    extracted = {
        "ho_ten": ExtractedField(name="ho_ten", status="extracted", value="Nguyễn Văn A"),
        "cccd": ExtractedField(
            name="cccd", status="unclear", reason="Công dân nói không rõ số cuối"
        ),
    }
    warnings = generate_warnings([_HO_TEN, _CCCD], extracted)

    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert warnings[0].field == "cccd"
    assert warnings[0].code == "extraction_unclear"


def test_optional_field_missing_generates_no_warning() -> None:
    warnings = generate_warnings([_GHI_CHU], extracted={})
    assert warnings == []


def test_extracted_field_generates_no_warning() -> None:
    extracted = {"ho_ten": ExtractedField(name="ho_ten", status="extracted", value="Nguyễn Văn A")}
    warnings = generate_warnings([_HO_TEN], extracted)
    assert warnings == []


def test_warnings_sorted_error_before_warning() -> None:
    extracted = {"cccd": ExtractedField(name="cccd", status="unclear")}
    # ho_ten thiếu (error), cccd unclear (warning) — khai báo theo thứ tự ngược lại
    warnings = generate_warnings([_CCCD, _HO_TEN], extracted)

    assert [w.severity for w in warnings] == ["error", "warning"]
    assert warnings[0].field == "ho_ten"
    assert warnings[1].field == "cccd"
