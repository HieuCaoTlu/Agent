"""Validator trường dữ liệu — Mục C2 của Checklist.

Logic thuần, không I/O. Ban đầu rút gọn chỉ giữ 3 validator đại diện
(`cccd_12_digits`, `vietnamese_name`, `required_present`); bổ sung thêm
(30/8/2026, theo yêu cầu của I2 — catalog thật D1 tham chiếu các tên này)
`date_not_future`, `date_reasonable_birth`, `in_options`, `vn_phone_10_digits`
theo cùng khuôn mẫu.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

_CCCD_PATTERN = re.compile(r"^\d{12}$")

# Chữ cái tiếng Việt (có dấu) + chữ cái Latin thường dùng trong tên người + khoảng trắng.
_VIETNAMESE_NAME_PATTERN = re.compile(
    r"^[A-Za-zÀ-ỹà-ỹĐđ]+(?: [A-Za-zÀ-ỹà-ỹĐđ]+)*$"
)

# Số điện thoại di động/cố định Việt Nam: 10 chữ số, bắt đầu bằng 0.
_VN_PHONE_PATTERN = re.compile(r"^0\d{9}$")

# Ngày sinh hợp lý: không quá 130 năm trước — loại các giá trị AI trích xuất
# sai (ví dụ nhầm thế kỷ) mà không dùng dữ liệu tuổi thọ chính xác của y tế.
_MAX_BIRTH_AGE_YEARS = 130


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    message: str | None = None


def cccd_12_digits(value: str) -> ValidationResult:
    """Số CCCD phải gồm đúng 12 chữ số."""
    if _CCCD_PATTERN.match(value):
        return ValidationResult(valid=True)
    return ValidationResult(valid=False, message="Số CCCD phải gồm đúng 12 chữ số.")


def vietnamese_name(value: str) -> ValidationResult:
    """Tên người phải chỉ gồm chữ cái tiếng Việt/Latin và khoảng trắng đơn."""
    stripped = value.strip()
    if stripped and _VIETNAMESE_NAME_PATTERN.match(stripped):
        return ValidationResult(valid=True)
    return ValidationResult(
        valid=False,
        message="Họ tên chỉ được chứa chữ cái và khoảng trắng, không chứa số hoặc ký tự đặc biệt.",
    )


def required_present(value: str | None) -> ValidationResult:
    """Trường bắt buộc phải có giá trị khác rỗng."""
    if value is not None and value.strip():
        return ValidationResult(valid=True)
    return ValidationResult(valid=False, message="Trường này là bắt buộc, không được để trống.")


def vn_phone_10_digits(value: str) -> ValidationResult:
    """Số điện thoại Việt Nam: đúng 10 chữ số, bắt đầu bằng 0."""
    if _VN_PHONE_PATTERN.match(value):
        return ValidationResult(valid=True)
    return ValidationResult(
        valid=False, message="Số điện thoại phải gồm đúng 10 chữ số và bắt đầu bằng 0."
    )


def date_not_future(value: str) -> ValidationResult:
    """Ngày (định dạng ISO `YYYY-MM-DD`) không được ở tương lai."""
    parsed = _parse_iso_date(value)
    if parsed is None:
        return ValidationResult(valid=False, message="Ngày không đúng định dạng (YYYY-MM-DD).")
    if parsed > date.today():
        return ValidationResult(valid=False, message="Ngày không được ở tương lai.")
    return ValidationResult(valid=True)


def date_reasonable_birth(value: str) -> ValidationResult:
    """Ngày sinh (ISO) phải trong khoảng hợp lý: không tương lai, không quá xa quá khứ."""
    parsed = _parse_iso_date(value)
    if parsed is None:
        return ValidationResult(valid=False, message="Ngày sinh không đúng định dạng (YYYY-MM-DD).")
    if parsed > date.today():
        return ValidationResult(valid=False, message="Ngày sinh không được ở tương lai.")
    earliest_reasonable = date(date.today().year - _MAX_BIRTH_AGE_YEARS, 1, 1)
    if parsed < earliest_reasonable:
        return ValidationResult(
            valid=False, message=f"Ngày sinh không hợp lý (quá {_MAX_BIRTH_AGE_YEARS} năm trước)."
        )
    return ValidationResult(valid=True)


def in_options(value: str, options: list[str] | None = None) -> ValidationResult:
    """Giá trị phải nằm trong danh sách `options` (từ `FieldSpec.options` của catalog).

    `options=None`/rỗng coi là lỗi cấu hình catalog (trường khai báo validator
    `in_options` nhưng không kèm `options`) — không có gì để so khớp nên
    luôn báo không hợp lệ, không âm thầm cho qua.
    """
    if not options:
        return ValidationResult(
            valid=False, message="Trường này chưa khai báo danh sách giá trị hợp lệ (options)."
        )
    if value in options:
        return ValidationResult(valid=True)
    return ValidationResult(
        valid=False, message=f"Giá trị phải là một trong: {', '.join(options)}."
    )


def _parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


_VALIDATORS: dict[str, Callable[..., ValidationResult]] = {
    "cccd_12_digits": cccd_12_digits,
    "vietnamese_name": vietnamese_name,
    "required_present": required_present,
    "vn_phone_10_digits": vn_phone_10_digits,
    "date_not_future": date_not_future,
    "date_reasonable_birth": date_reasonable_birth,
    "in_options": in_options,
}

# Tên validator cần tham số `options` bổ sung (ngoài `value`) — dùng để
# `validate_field`/`validate_all` biết khi nào phải truyền `options`.
_VALIDATORS_NEEDING_OPTIONS: frozenset[str] = frozenset({"in_options"})


def validate_field(
    validator_name: str, value: str | None, options: list[str] | None = None
) -> ValidationResult:
    """Chạy một validator theo tên (tra trong `_VALIDATORS`).

    `options`: chỉ dùng bởi validator cần danh sách giá trị hợp lệ
    (`in_options`) — validator khác bỏ qua tham số này.
    Ném `KeyError` nếu tên validator không tồn tại — lỗi lập trình (cấu hình
    catalog sai tên validator), không phải lỗi nghiệp vụ nên không bọc mềm.
    """
    validator = _VALIDATORS[validator_name]
    value_or_empty = value if value is not None else ""
    if validator_name in _VALIDATORS_NEEDING_OPTIONS:
        return validator(value_or_empty, options=options)
    return validator(value_or_empty)


def validate_all(
    values: dict[str, str | None],
    field_validators: dict[str, list[str]],
    field_options: dict[str, list[str]] | None = None,
) -> dict[str, list[ValidationResult]]:
    """Chạy toàn bộ validator cho từng trường.

    `field_validators`: ánh xạ tên trường -> danh sách tên validator áp dụng
    cho trường đó (thứ tự chạy giữ nguyên thứ tự khai báo).
    `field_options`: ánh xạ tên trường -> `FieldSpec.options` — chỉ cần khai
    báo cho trường có validator `in_options`.
    Chỉ trả về kết quả cho trường có validator được khai báo; trường không có
    trong `field_validators` được bỏ qua (không lỗi, không kết quả).
    """
    field_options = field_options or {}
    results: dict[str, list[ValidationResult]] = {}
    for field_name, validator_names in field_validators.items():
        value = values.get(field_name)
        options = field_options.get(field_name)
        results[field_name] = [
            validate_field(name, value, options=options) for name in validator_names
        ]
    return results
