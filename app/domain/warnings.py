"""Sinh cảnh báo cho cán bộ — Mục C6 của Checklist (rút gọn — 2 loại).

Logic thuần, không I/O. Bản rút gọn chỉ sinh 2 loại cảnh báo:
  - error: trường bắt buộc (`required=True`) nhưng bị trích xuất với
    status="missing" — cán bộ phải tự nhập trước khi xác nhận.
  - warning: trường được trích xuất với status="unclear" — AI không chắc,
    cán bộ nên đọc lại evidence/reason trước khi tin.

Các loại cảnh báo khác (mâu thuẫn giữa các lượt nói, giá trị bất thường so
với lịch sử...) bổ sung sau khi cần.
"""

from dataclasses import dataclass
from typing import Literal

from app.catalog.models import FieldSpec
from app.domain.extraction_schema import ExtractedField

Severity = Literal["error", "warning"]

_SEVERITY_ORDER: dict[Severity, int] = {"error": 0, "warning": 1}


@dataclass(frozen=True)
class Warning:
    severity: Severity
    field: str
    message: str
    code: str


def generate_warnings(
    fields: list[FieldSpec], extracted: dict[str, ExtractedField]
) -> list[Warning]:
    """Sinh danh sách cảnh báo từ đặc tả trường (catalog) và kết quả trích xuất.

    `extracted`: ánh xạ tên trường -> `ExtractedField` (chỉ chứa trường AI đã
    xử lý; trường không có trong dict được coi như "missing").
    Kết quả được sắp xếp theo mức độ nghiêm trọng (error trước warning).
    """
    result: list[Warning] = []
    for field in fields:
        item = extracted.get(field.name)
        status = item.status if item is not None else "missing"

        if field.required and status == "missing":
            result.append(
                Warning(
                    severity="error",
                    field=field.name,
                    message=f"Trường bắt buộc '{field.label}' chưa có giá trị, cần cán bộ nhập.",
                    code="required_missing",
                )
            )
        elif status == "unclear":
            result.append(
                Warning(
                    severity="warning",
                    field=field.name,
                    message=f"Trường '{field.label}' AI không chắc chắn, cán bộ cần kiểm tra lại.",
                    code="extraction_unclear",
                )
            )

    result.sort(key=lambda w: _SEVERITY_ORDER[w.severity])
    return result
