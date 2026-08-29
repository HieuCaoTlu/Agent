"""Validator trường dữ liệu — Mục C2 của Checklist (rút gọn — 3 validator đại diện).

Logic thuần, không I/O. Bản rút gọn chỉ giữ 3 validator đại diện cho 3 nhóm
kiểm tra khác nhau (định dạng số, định dạng chữ có dấu tiếng Việt, và
bắt buộc-phải-có) — đủ để chứng minh cơ chế `validate_field`/`validate_all`
hoạt động đúng. Các validator khác (ngày tháng, số điện thoại, địa chỉ...)
bổ sung sau khi cần, theo cùng khuôn mẫu.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

_CCCD_PATTERN = re.compile(r"^\d{12}$")

# Chữ cái tiếng Việt (có dấu) + chữ cái Latin thường dùng trong tên người + khoảng trắng.
_VIETNAMESE_NAME_PATTERN = re.compile(
    r"^[A-Za-zÀ-ỹà-ỹĐđ]+(?: [A-Za-zÀ-ỹà-ỹĐđ]+)*$"
)


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


_VALIDATORS: dict[str, Callable[[str], ValidationResult]] = {
    "cccd_12_digits": cccd_12_digits,
    "vietnamese_name": vietnamese_name,
    "required_present": required_present,
}


def validate_field(validator_name: str, value: str | None) -> ValidationResult:
    """Chạy một validator theo tên (tra trong `_VALIDATORS`).

    Ném `KeyError` nếu tên validator không tồn tại — lỗi lập trình (cấu hình
    catalog sai tên validator), không phải lỗi nghiệp vụ nên không bọc mềm.
    """
    validator = _VALIDATORS[validator_name]
    return validator(value if value is not None else "")


def validate_all(
    values: dict[str, str | None], field_validators: dict[str, list[str]]
) -> dict[str, list[ValidationResult]]:
    """Chạy toàn bộ validator cho từng trường.

    `field_validators`: ánh xạ tên trường -> danh sách tên validator áp dụng
    cho trường đó (thứ tự chạy giữ nguyên thứ tự khai báo).
    Chỉ trả về kết quả cho trường có validator được khai báo; trường không có
    trong `field_validators` được bỏ qua (không lỗi, không kết quả).
    """
    results: dict[str, list[ValidationResult]] = {}
    for field_name, validator_names in field_validators.items():
        value = values.get(field_name)
        results[field_name] = [validate_field(name, value) for name in validator_names]
    return results
