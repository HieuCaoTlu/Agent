from datetime import date, timedelta

import pytest

from app.domain.validators import (
    cccd_12_digits,
    date_not_future,
    date_reasonable_birth,
    in_options,
    required_present,
    validate_all,
    validate_field,
    vietnamese_name,
    vn_phone_10_digits,
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


@pytest.mark.parametrize(
    ("value", "expected_valid"),
    [
        ("0912345678", True),
        ("0123456789", True),
        ("912345678", False),  # thiếu số 0 đầu, chỉ 9 chữ số
        ("09123456789", False),  # thừa số
        ("091234567a", False),  # có chữ
        ("", False),
    ],
)
def test_vn_phone_10_digits(value: str, expected_valid: bool) -> None:
    result = vn_phone_10_digits(value)
    assert result.valid is expected_valid
    if not expected_valid:
        assert result.message


def test_date_not_future_accepts_today_and_past() -> None:
    assert date_not_future(date.today().isoformat()).valid is True
    assert date_not_future("2000-01-01").valid is True


def test_date_not_future_rejects_future() -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    result = date_not_future(tomorrow)
    assert result.valid is False
    assert result.message


def test_date_not_future_rejects_bad_format() -> None:
    result = date_not_future("khong-phai-ngay")
    assert result.valid is False


def test_date_reasonable_birth_accepts_recent_date() -> None:
    assert date_reasonable_birth("2020-05-10").valid is True


def test_date_reasonable_birth_rejects_future() -> None:
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert date_reasonable_birth(tomorrow).valid is False


def test_date_reasonable_birth_rejects_too_far_in_past() -> None:
    result = date_reasonable_birth("1850-01-01")
    assert result.valid is False
    assert result.message


def test_in_options_accepts_listed_value() -> None:
    result = in_options("Nam", options=["Nam", "Nữ"])
    assert result.valid is True


def test_in_options_rejects_unlisted_value() -> None:
    result = in_options("Khác", options=["Nam", "Nữ"])
    assert result.valid is False
    assert "Nam" in result.message


def test_in_options_rejects_when_no_options_configured() -> None:
    result = in_options("Nam", options=None)
    assert result.valid is False


def test_validate_field_passes_options_to_in_options() -> None:
    result = validate_field("in_options", "Nữ", options=["Nam", "Nữ"])
    assert result.valid is True


def test_validate_all_passes_field_options() -> None:
    results = validate_all(
        {"gioi_tinh": "Nam"},
        field_validators={"gioi_tinh": ["in_options"]},
        field_options={"gioi_tinh": ["Nam", "Nữ"]},
    )
    assert results["gioi_tinh"][0].valid is True
