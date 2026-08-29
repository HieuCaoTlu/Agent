from app.catalog.models import FieldSpec
from app.llm.prompt import (
    SYSTEM_PROMPT_V1,
    build_single_field_correction_message,
    build_user_message,
)

_FIELDS = [
    FieldSpec(name="ho_ten", label="Họ và tên", type="person_name", required=True),
    FieldSpec(name="ngay_sinh", label="Ngày sinh", type="date", required=True),
]


def test_system_prompt_contains_key_rules() -> None:
    assert "missing" in SYSTEM_PROMPT_V1
    assert "unclear" in SYSTEM_PROMPT_V1
    assert "evidence" in SYSTEM_PROMPT_V1
    assert "KHÔNG" in SYSTEM_PROMPT_V1


def test_build_user_message_includes_procedure_and_fields() -> None:
    message = build_user_message(
        procedure_name="Đăng ký khai sinh",
        procedure_code="dang_ky_khai_sinh",
        fields=_FIELDS,
        confirmed_values={},
        transcript_turns=["Tôi muốn đăng ký khai sinh."],
    )
    assert "Đăng ký khai sinh" in message
    assert "dang_ky_khai_sinh" in message
    assert "ho_ten" in message
    assert "ngay_sinh" in message
    assert "[Lượt 1]" in message


def test_build_user_message_numbers_multiple_turns() -> None:
    message = build_user_message(
        procedure_name="X",
        procedure_code="x",
        fields=_FIELDS,
        confirmed_values={},
        transcript_turns=["câu một", "câu hai", "câu ba"],
    )
    assert "[Lượt 1] câu một" in message
    assert "[Lượt 2] câu hai" in message
    assert "[Lượt 3] câu ba" in message


def test_build_user_message_includes_confirmed_values() -> None:
    message = build_user_message(
        procedure_name="X",
        procedure_code="x",
        fields=_FIELDS,
        confirmed_values={"ho_ten": "Nguyễn Văn A"},
        transcript_turns=["..."],
    )
    assert "Nguyễn Văn A" in message


def test_only_missing_fields_excludes_confirmed() -> None:
    message = build_user_message(
        procedure_name="X",
        procedure_code="x",
        fields=_FIELDS,
        confirmed_values={"ho_ten": "Nguyễn Văn A"},
        transcript_turns=["..."],
        only_missing_fields=True,
    )
    # ho_ten đã confirmed nên không nằm trong danh sách "cần trích xuất" nữa
    fields_section = message.split("### Các trường cần trích xuất")[1].split("###")[0]
    assert "ngay_sinh" in fields_section
    assert '"name": "ho_ten"' not in fields_section


def test_build_single_field_correction_message_is_short() -> None:
    message = build_single_field_correction_message(_FIELDS[0], ["tôi tên Nguyễn Văn A"])
    assert "ho_ten" in message
    assert "[Lượt 1]" in message
    assert "Các trường cần trích xuất" not in message  # không dùng heading của prompt đầy đủ
