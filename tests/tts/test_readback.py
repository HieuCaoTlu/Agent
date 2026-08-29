from app.catalog.models import FieldSpec
from app.tts.readback import build_fallback_text, build_readback_text

_FIELDS = [
    FieldSpec(name="ho_ten", label="Họ tên", type="person_name", required=True),
    FieldSpec(name="ngay_sinh", label="Ngày sinh", type="date", required=True),
    FieldSpec(name="so_dien_thoai", label="Số điện thoại", type="phone", required=True),
    FieldSpec(name="so_cccd", label="Số CCCD", type="national_id", required=True),
]

_TEMPLATE = (
    "Họ tên: {ho_ten}. Ngày sinh: {ngay_sinh}. "
    "Số điện thoại: {so_dien_thoai}. CCCD: {so_cccd}."
)


def test_build_readback_text_fills_all_confirmed_values() -> None:
    text = build_readback_text(
        _TEMPLATE,
        {
            "ho_ten": "Nguyễn Văn A",
            "ngay_sinh": "2026-03-05",
            "so_dien_thoai": "0912345678",
            "so_cccd": "012345678901",
        },
        _FIELDS,
    )
    assert "Nguyễn Văn A" in text
    assert "ngày mùng 5 tháng 3 năm 2026" in text


def test_phone_number_spelled_out_digit_by_digit() -> None:
    text = build_readback_text(
        "SĐT: {so_dien_thoai}",
        {"so_dien_thoai": "0912345678"},
        _FIELDS,
    )
    assert "không chín một hai ba bốn năm sáu bảy tám" in text


def test_national_id_masked_not_spoken_in_full() -> None:
    text = build_readback_text(
        "CCCD: {so_cccd}",
        {"so_cccd": "012345678901"},
        _FIELDS,
    )
    assert "012345678901" not in text
    assert "8 9 0 1" in text  # chỉ 4 số cuối


def test_date_before_day_ten_uses_mung() -> None:
    text = build_readback_text("Ngày: {ngay_sinh}", {"ngay_sinh": "2026-01-09"}, _FIELDS)
    assert "mùng 9" in text


def test_date_after_day_ten_no_mung() -> None:
    text = build_readback_text("Ngày: {ngay_sinh}", {"ngay_sinh": "2026-01-15"}, _FIELDS)
    assert "mùng" not in text
    assert "ngày 15 tháng 1 năm 2026" in text


def test_missing_confirmed_value_uses_placeholder_not_crash() -> None:
    text = build_readback_text(_TEMPLATE, {"ho_ten": "Nguyễn Văn A"}, _FIELDS)
    assert "Nguyễn Văn A" in text
    assert "(chưa xác nhận)" in text


def test_unknown_date_format_passed_through_unchanged() -> None:
    text = build_readback_text("Ngày: {ngay_sinh}", {"ngay_sinh": "không rõ"}, _FIELDS)
    assert "không rõ" in text


def test_build_fallback_text_matches_readback_content() -> None:
    values = {"ho_ten": "Nguyễn Văn A", "so_dien_thoai": "0912345678"}
    assert build_fallback_text(_TEMPLATE, values, _FIELDS) == build_readback_text(
        _TEMPLATE, values, _FIELDS
    )
