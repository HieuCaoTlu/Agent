from app.llm.redactor import PIIRedactor


def test_redact_digit_cccd() -> None:
    redactor = PIIRedactor()
    transcript = "Số CCCD của tôi là 012345678901, sinh năm 1990."
    redacted = redactor.redact(transcript)

    assert "012345678901" not in redacted
    assert "[CCCD_1]" in redacted
    assert "1990" in redacted  # số khác 12 chữ số không bị che


def test_redact_does_not_touch_shorter_or_longer_digit_runs() -> None:
    redactor = PIIRedactor()
    transcript = "Số điện thoại 0912345678, mã bưu điện 123456."
    redacted = redactor.redact(transcript)
    assert redacted == transcript  # không có chuỗi nào đúng 12 chữ số


def test_redact_spoken_digits() -> None:
    redactor = PIIRedactor()
    transcript = "CCCD của tôi là không một hai ba bốn năm sáu bảy tám chín không một"
    redacted = redactor.redact(transcript)
    assert "[CCCD_1]" in redacted
    assert "không một hai" not in redacted


def test_restore_replaces_placeholder_with_real_value() -> None:
    redactor = PIIRedactor()
    transcript = "CCCD: 012345678901"
    redacted = redactor.redact(transcript)

    llm_output = f'{{"value": "{redacted.split(": ")[1]}"}}'
    restored = redactor.restore(llm_output)
    assert "012345678901" in restored
    assert "[CCCD_1]" not in restored


def test_multiple_cccd_get_distinct_placeholders() -> None:
    redactor = PIIRedactor()
    transcript = "CCCD chồng 111111111111, CCCD vợ 222222222222."
    redacted = redactor.redact(transcript)

    assert "[CCCD_1]" in redacted
    assert "[CCCD_2]" in redacted

    restored = redactor.restore(redacted)
    assert "111111111111" in restored
    assert "222222222222" in restored


def test_mapping_never_persisted_only_in_memory() -> None:
    """Xác nhận không có phương thức nào ghi bảng ánh xạ ra ngoài (DB/file) — NT-6."""
    redactor = PIIRedactor()
    public_methods = {name for name in dir(redactor) if not name.startswith("_")}
    assert public_methods == {"redact", "restore"}
