"""Định nghĩa dữ liệu của Procedure Catalog — Mục D1 của Checklist, Mục 6.3 của Plan.

Catalog là nguồn chân lý duy nhất về thủ tục nào được hỗ trợ, trường dữ liệu nào
cần thiết, thành phần hồ sơ gì — LLM không bao giờ được tự quyết định những điều
này (NT-4). Các model ở đây chỉ mô tả *hình dạng* dữ liệu (validate khi nạp file
JSON); logic nạp/tra cứu catalog nằm ở `app/services/catalog_service.py` (D2).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

FieldType = Literal[
    "person_name", "date", "national_id", "phone", "address", "enum", "text"
]


class FieldSpec(BaseModel):
    """Đặc tả một trường dữ liệu của thủ tục — Mục 6.3 của Plan."""

    name: str
    label: str
    type: FieldType
    required: bool = False
    sensitive: bool = False
    redact_to_llm: bool = False
    options: list[str] | None = None
    spoken_hint: str | None = None
    validators: list[str] = Field(default_factory=list)


class Document(BaseModel):
    """Một thành phần hồ sơ (giấy tờ) cần nộp/xuất trình."""

    name: str
    note: str | None = None


class Procedure(BaseModel):
    """Một thủ tục hành chính đầy đủ — nội dung của một file catalog JSON."""

    code: str
    name: str
    catalog_version: str
    approved_by: str
    approved_at: date
    legal_basis: str
    effective_from: date
    effective_to: date | None = None
    fields: list[FieldSpec]
    required_documents: list[Document] = Field(default_factory=list)
    readback_template: str

    def is_active(self, at: date) -> bool:
        """Thủ tục có hiệu lực tại ngày `at` hay không (dựa trên effective_from/to)."""
        if at < self.effective_from:
            return False
        if self.effective_to is not None and at > self.effective_to:
            return False
        return True


class ProcedureSummary(BaseModel):
    """Bản tóm tắt thủ tục — dùng khi liệt kê danh mục (không kèm toàn bộ field/document)."""

    code: str
    name: str
    catalog_version: str
