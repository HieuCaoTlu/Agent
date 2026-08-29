import pytest

from app.domain.validators import (
    cccd_12_digits,
    required_present,
    validate_all,
    validate_field,
    vietnamese_name,
)


@pytest.mark.parametrize(
    ("value", "expected_valid"),
    [
        ("012345678901", True),
        ("123456789012", True),
        ("12345", False),  # thiếu số
        ("1234567890123", False),  # thừa số
        ("01234567890a", False),  # có chữ
        ("", False),
    ],
)
def test_cccd_12_digits(value: str, expected_valid: bool) -> None:
    result = cccd_12_digits(value)
    assert result.valid is expected_valid
    if not expected_valid:
        assert result.message


@pytest.mark.parametrize(
    ("value", "expected_valid"),
    [
        ("Nguyễn Văn A", True),
        ("Trần Thị Bích", True),
        ("Le Van B", True),
        ("Nguyen123", False),  # có số
        ("Nguyễn  Văn", False),  # hai khoảng trắng liền
        ("", False),
        ("   ", False),
    ],
)
def test_vietnamese_name(value: str, expected_valid: bool) -> None:
    result = vietnamese_name(value)
    assert result.valid is expected_valid
    if not expected_valid:
        assert result.message


@pytest.mark.parametrize(
    ("value", "expected_valid"),
    [
        ("có giá trị", True),
        ("", False),
        ("   ", False),
        (None, False),
    ],
)
def test_required_present(value: str | None, expected_valid: bool) -> None:
    result = required_present(value)
    assert result.valid is expected_valid
    if not expected_valid:
        assert result.message


def test_validate_field_by_name() -> None:
    result = validate_field("cccd_12_digits", "123456789012")
    assert result.valid is True


def test_validate_field_unknown_name_raises_key_error() -> None:
    with pytest.raises(KeyError):
        validate_field("khong_ton_tai", "abc")


def test_validate_all() -> None:
    values = {
        "cccd": "123456789012",
        "ho_ten": "Nguyễn Văn A",
        "ghi_chu": None,
    }
    field_validators = {
        "cccd": ["required_present", "cccd_12_digits"],
        "ho_ten": ["required_present", "vietnamese_name"],
        "ghi_chu": ["required_present"],
    }
    results = validate_all(values, field_validators)

    assert all(r.valid for r in results["cccd"])
    assert all(r.valid for r in results["ho_ten"])
    assert results["ghi_chu"][0].valid is False


def test_validate_all_ignores_fields_without_validators() -> None:
    values = {"khac": "gia tri bat ky"}
    results = validate_all(values, field_validators={})
    assert results == {}
