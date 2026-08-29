from datetime import date

import pytest
from pydantic import ValidationError

from app.catalog.models import Document, FieldSpec, Procedure


def _make_procedure(**overrides: object) -> Procedure:
    defaults: dict[str, object] = {
        "code": "thu_tuc_mau",
        "name": "Thủ tục mẫu",
        "catalog_version": "2026.08.1",
        "approved_by": "Phòng Văn hóa - Xã hội phường Yên Sở",
        "approved_at": date(2026, 8, 15),
        "legal_basis": "Luật mẫu",
        "effective_from": date(2026, 9, 1),
        "effective_to": None,
        "fields": [FieldSpec(name="ho_ten", label="Họ tên", type="person_name", required=True)],
        "required_documents": [Document(name="CCCD")],
        "readback_template": "Xin đọc lại: {ho_ten}.",
    }
    defaults.update(overrides)
    return Procedure.model_validate(defaults)


def test_field_spec_defaults() -> None:
    field = FieldSpec(name="x", label="X", type="text")
    assert field.required is False
    assert field.sensitive is False
    assert field.redact_to_llm is False
    assert field.options is None
    assert field.validators == []


def test_field_spec_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        FieldSpec(name="x", label="X", type="khong_ton_tai")  # type: ignore[arg-type]


def test_procedure_is_active_within_range() -> None:
    procedure = _make_procedure(effective_from=date(2026, 9, 1), effective_to=date(2026, 12, 31))
    assert procedure.is_active(date(2026, 9, 1)) is True
    assert procedure.is_active(date(2026, 10, 15)) is True
    assert procedure.is_active(date(2026, 12, 31)) is True


def test_procedure_is_active_before_effective_from() -> None:
    procedure = _make_procedure(effective_from=date(2026, 9, 1))
    assert procedure.is_active(date(2026, 8, 31)) is False


def test_procedure_is_active_after_effective_to() -> None:
    procedure = _make_procedure(effective_from=date(2026, 9, 1), effective_to=date(2026, 12, 31))
    assert procedure.is_active(date(2027, 1, 1)) is False


def test_procedure_is_active_no_effective_to_means_open_ended() -> None:
    procedure = _make_procedure(effective_from=date(2026, 9, 1), effective_to=None)
    assert procedure.is_active(date(2099, 1, 1)) is True
