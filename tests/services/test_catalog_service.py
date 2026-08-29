import json
from datetime import date
from pathlib import Path

import pytest

from app.domain.exceptions import ProcedureNotFound
from app.services.catalog_service import CatalogService


def _write_procedure_json(
    directory: Path,
    code: str,
    effective_from: str = "2026-09-01",
    effective_to: str | None = None,
) -> None:
    data = {
        "code": code,
        "name": f"Thủ tục {code}",
        "catalog_version": "2026.08.1",
        "approved_by": "Phòng Văn hóa - Xã hội phường Yên Sở",
        "approved_at": "2026-08-15",
        "legal_basis": "Luật mẫu",
        "effective_from": effective_from,
        "effective_to": effective_to,
        "fields": [
            {"name": "ho_ten", "label": "Họ tên", "type": "person_name", "required": True}
        ],
        "required_documents": [{"name": "CCCD"}],
        "readback_template": "Xin đọc lại: {ho_ten}.",
    }
    (directory / f"{code}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def catalog_dir(tmp_path: Path) -> Path:
    _write_procedure_json(tmp_path, "thu_tuc_a")
    _write_procedure_json(tmp_path, "thu_tuc_b", effective_from="2099-01-01")  # chưa hiệu lực
    _write_procedure_json(
        tmp_path, "thu_tuc_c", effective_from="2020-01-01", effective_to="2020-12-31"
    )  # hết hiệu lực
    return tmp_path


def test_list_active_only_returns_currently_effective(catalog_dir: Path) -> None:
    service = CatalogService(catalog_dir=catalog_dir)
    summaries = service.list_active(at=date(2026, 9, 15))
    assert [s.code for s in summaries] == ["thu_tuc_a"]


def test_get_active_procedure_succeeds(catalog_dir: Path) -> None:
    service = CatalogService(catalog_dir=catalog_dir)
    procedure = service.get("thu_tuc_a", at=date(2026, 9, 15))
    assert procedure.code == "thu_tuc_a"


def test_get_unknown_code_raises_not_found(catalog_dir: Path) -> None:
    service = CatalogService(catalog_dir=catalog_dir)
    with pytest.raises(ProcedureNotFound):
        service.get("khong_ton_tai", at=date(2026, 9, 15))


def test_get_not_yet_effective_raises_not_found(catalog_dir: Path) -> None:
    service = CatalogService(catalog_dir=catalog_dir)
    with pytest.raises(ProcedureNotFound):
        service.get("thu_tuc_b", at=date(2026, 9, 15))


def test_get_expired_raises_not_found(catalog_dir: Path) -> None:
    service = CatalogService(catalog_dir=catalog_dir)
    with pytest.raises(ProcedureNotFound):
        service.get("thu_tuc_c", at=date(2026, 9, 15))


def test_get_field_schema_and_documents_and_readback(catalog_dir: Path) -> None:
    service = CatalogService(catalog_dir=catalog_dir)
    at = date(2026, 9, 15)

    fields = service.get_field_schema("thu_tuc_a", at=at)
    assert [f.name for f in fields] == ["ho_ten"]

    documents = service.get_required_documents("thu_tuc_a", at=at)
    assert [d.name for d in documents] == ["CCCD"]

    template = service.get_readback_template("thu_tuc_a", at=at)
    assert "{ho_ten}" in template


def test_loads_real_static_data_directory() -> None:
    """Xác nhận 3 file catalog thật (D1) nạp được, không lỗi schema."""
    service = CatalogService()
    at = date(2026, 9, 15)
    codes = {s.code for s in service.list_active(at=at)}
    assert codes == {"chung_thuc_dien_tu", "dang_ky_khai_sinh", "dang_ky_ket_hon"}
