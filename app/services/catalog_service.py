"""Catalog Service — Mục D2 của Checklist, Mục 6.5 của Plan.

Nạp toàn bộ file JSON trong `app/static_data/procedures/` vào bộ nhớ lúc khởi
động, cache lại (không đọc file mỗi request). Đây là tầng duy nhất tra cứu
catalog — service khác (LLM, API) không tự đọc file JSON.
"""

import json
from datetime import date
from pathlib import Path

from app.catalog.models import Document, FieldSpec, Procedure, ProcedureSummary
from app.domain.exceptions import ProcedureNotFound

_DEFAULT_CATALOG_DIR = Path(__file__).resolve().parent.parent / "static_data" / "procedures"


class CatalogService:
    """Nạp và tra cứu danh mục thủ tục hành chính.

    LLM không bao giờ được tự quyết định thủ tục nào tồn tại hay trường nào
    cần thiết (NT-4) — mọi câu trả lời cho những câu hỏi đó đi qua service này.
    """

    def __init__(self, catalog_dir: Path | None = None) -> None:
        self._catalog_dir = catalog_dir or _DEFAULT_CATALOG_DIR
        self._procedures: dict[str, Procedure] = {}
        self._load()

    def _load(self) -> None:
        for path in sorted(self._catalog_dir.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            procedure = Procedure.model_validate(raw)
            self._procedures[procedure.code] = procedure

    def list_active(self, at: date) -> list[ProcedureSummary]:
        """Danh sách thủ tục đang có hiệu lực tại ngày `at`, sắp xếp theo mã."""
        return [
            ProcedureSummary(code=p.code, name=p.name, catalog_version=p.catalog_version)
            for p in sorted(self._procedures.values(), key=lambda x: x.code)
            if p.is_active(at)
        ]

    def get(self, code: str, at: date) -> Procedure:
        """Lấy thủ tục theo mã, chỉ khi đang có hiệu lực tại ngày `at`.

        Ném `ProcedureNotFound` nếu không tồn tại hoặc đã hết/chưa tới hiệu lực
        — cố ý không phân biệt hai trường hợp này với người gọi (đều là
        "không dùng được thủ tục này lúc này").
        """
        procedure = self._procedures.get(code)
        if procedure is None or not procedure.is_active(at):
            raise ProcedureNotFound(code)
        return procedure

    def get_field_schema(self, code: str, at: date) -> list[FieldSpec]:
        return self.get(code, at).fields

    def get_required_documents(self, code: str, at: date) -> list[Document]:
        return self.get(code, at).required_documents

    def get_readback_template(self, code: str, at: date) -> str:
        return self.get(code, at).readback_template
