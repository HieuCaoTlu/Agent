"""Nội dung đọc lại — Mục H3 của Checklist.

Dựng văn bản đọc lại từ `readback_template` của catalog (D) và giá trị đã
xác nhận, định dạng lại một số loại trường cho tự nhiên khi nghe (ngày tháng,
số điện thoại đọc từng chữ số), và che số CCCD trước khi gửi cho TTS — người
dân không cần nghe đọc lại số CCCD của chính mình vì đã cầm giấy tờ gốc, và
gửi giọng đọc CCCD ra dịch vụ TTS bên ngoài là rủi ro không cần thiết (NT-6).
"""

import re
from datetime import date

from app.catalog.models import FieldSpec

_DIGIT_WORDS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def build_readback_text(
    template: str, confirmed_values: dict[str, str], fields: list[FieldSpec]
) -> str:
    """Dựng nội dung đọc lại đầy đủ, đã định dạng và che CCCD.

    `template`: `readback_template` từ catalog (D), chứa placeholder `{field_name}`.
    `fields`: dùng để biết `type` của từng trường — quyết định cách định dạng
    (ngày → đọc tự nhiên, phone → đọc từng chữ số, national_id → che).
    """
    field_by_name = {f.name: f for f in fields}
    formatted_values = {
        name: _format_value_for_speech(value, field_by_name.get(name))
        for name, value in confirmed_values.items()
    }
    try:
        return template.format(**formatted_values)
    except KeyError:
        # Trường chưa có trong confirmed_values (chưa xác nhận) — điền placeholder
        # trung lập thay vì để .format() ném lỗi làm hỏng toàn bộ nội dung đọc lại.
        return _format_with_missing_placeholders(template, formatted_values)


def build_fallback_text(
    template: str, confirmed_values: dict[str, str], fields: list[FieldSpec]
) -> str:
    """Fallback khi TTS lỗi: trả về văn bản để frontend hiển thị cỡ chữ lớn.

    Cố ý dùng cùng logic với `build_readback_text()` — nội dung fallback phải
    khớp nội dung lẽ ra được đọc, không phải một bản tóm tắt khác.
    """
    return build_readback_text(template, confirmed_values, fields)


def _format_value_for_speech(value: str, field: FieldSpec | None) -> str:
    if field is None:
        return value
    if field.type == "national_id":
        return _mask_national_id(value)
    if field.type == "phone":
        return _spell_out_digits(value)
    if field.type == "date":
        return _format_date_for_speech(value)
    return value


def _mask_national_id(value: str) -> str:
    """Che số CCCD trước khi gửi TTS — chỉ để lại số cuối cho ngữ cảnh nói."""
    digits = re.sub(r"\D", "", value)
    if len(digits) <= 4:
        return "số đã được che"
    return f"số kết thúc bằng {' '.join(digits[-4:])}"


def _spell_out_digits(value: str) -> str:
    """Đọc số điện thoại thành từng chữ số, cách nhau bởi khoảng trắng."""
    digits = re.sub(r"\D", "", value)
    return " ".join(_DIGIT_WORDS[int(d)] for d in digits)


def _format_date_for_speech(value: str) -> str:
    """Định dạng ngày ISO (YYYY-MM-DD) thành dạng đọc tự nhiên tiếng Việt.

    Ví dụ: "2026-03-05" → "ngày mùng 5 tháng 3 năm 2026".
    Nếu `value` không đúng định dạng ISO, trả nguyên văn (không đoán/sửa).
    """
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value

    # "mùng" chỉ dùng cho ngày 1-9 theo thói quen nói tiếng Việt (mùng 1 - mùng 9,
    # từ ngày 10 trở đi nói "ngày mười", "ngày hai mươi..." không kèm "mùng").
    day_part = f"mùng {parsed.day}" if parsed.day <= 9 else f"{parsed.day}"
    return f"ngày {day_part} tháng {parsed.month} năm {parsed.year}"


def _format_with_missing_placeholders(template: str, values: dict[str, str]) -> str:
    """`str.format_map` với giá trị mặc định "(chưa xác nhận)" cho key thiếu."""

    class _DefaultDict(dict):
        def __missing__(self, key: str) -> str:
            return "(chưa xác nhận)"

    return template.format_map(_DefaultDict(values))
