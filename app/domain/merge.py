"""Quy tắc gộp dữ liệu qua nhiều lượt trích xuất — Mục 7.1 của Plan.

Logic thuần, không I/O — bản này không nằm trong danh sách rút gọn ban đầu
của Mục C (Checklist chỉ liệt kê C1/C2/C5/C6), nhưng là điều kiện cần để hiện
thực Bước 9 của `ExtractionService` (I2, UC2) nên được thêm ở đây, cùng
khuôn mẫu logic-thuần-có-test-riêng như phần C.

Quy tắc (Mục 7.1), theo (trạng thái hiện tại, giá trị mới) -> kết quả:
  - Trống/missing, có giá trị mới -> nhận giá trị mới.
  - Có giá trị chưa xác nhận, giá trị mới khác -> nhận giá trị mới,
    `changed_from_previous=True`.
  - Có giá trị đã xác nhận, giá trị mới khác -> giữ giá trị đã xác nhận,
    `conflict_with_confirmed=True`.
  - Có giá trị, lượt mới missing -> giữ giá trị cũ (không xóa dữ liệu).
"""

from dataclasses import dataclass

from app.domain.extraction_schema import ExtractedField


@dataclass(frozen=True)
class MergeResult:
    """Kết quả gộp một trường — dùng để `ExtractionService` (I2) quyết định
    ghi gì vào `FieldState` và có sinh cảnh báo `conflict_with_confirmed` hay không.
    """

    value: str | None
    confidence: str | None
    evidence: str | None
    changed_from_previous: bool = False
    conflict_with_confirmed: bool = False


def merge_field(
    current_value: str | None,
    is_confirmed: bool,
    new_field: ExtractedField | None,
) -> MergeResult:
    """Gộp giá trị hiện có của một trường với kết quả trích xuất mới.

    `current_value`: giá trị hiện tại trong `FieldState` (`confirmed_value`
    nếu đã xác nhận, ngược lại `suggested_value`) — `None`/rỗng nếu chưa có.
    `new_field`: kết quả LLM cho trường này ở lượt mới; `None` nếu LLM không
    trả về trường này (coi như tương đương status="missing").
    """
    new_has_value = new_field is not None and new_field.status == "extracted" and new_field.value

    if not new_has_value:
        # Lượt mới không có giá trị (missing/unclear) → giữ nguyên giá trị cũ,
        # không xóa dữ liệu đã có (bảng quy tắc, dòng 4).
        return MergeResult(value=current_value, confidence=None, evidence=None)

    assert new_field is not None  # để type-checker hẹp kiểu — new_has_value đã loại None ở trên

    if not current_value:
        # Trống / missing → nhận giá trị mới (dòng 1).
        return MergeResult(
            value=new_field.value, confidence=new_field.confidence, evidence=new_field.evidence
        )

    if new_field.value == current_value:
        # Giá trị mới trùng giá trị cũ — không có gì để gộp, không đánh dấu thay đổi.
        return MergeResult(
            value=current_value, confidence=new_field.confidence, evidence=new_field.evidence
        )

    if is_confirmed:
        # Có giá trị, ĐÃ xác nhận, giá trị mới khác → giữ giá trị đã xác nhận,
        # gắn cờ xung đột để tầng gọi sinh cảnh báo (dòng 3).
        return MergeResult(
            value=current_value, confidence=None, evidence=None, conflict_with_confirmed=True
        )

    # Có giá trị, CHƯA xác nhận, giá trị mới khác → nhận giá trị mới (dòng 2).
    return MergeResult(
        value=new_field.value,
        confidence=new_field.confidence,
        evidence=new_field.evidence,
        changed_from_previous=True,
    )
