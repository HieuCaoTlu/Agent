"""Kiểm chứng nguồn gốc (grounding check) — Mục F5 của Checklist, Mục 10.4 của Plan.

Lớp 3 trong kiến trúc chống ảo giác (Mục 10.1): mỗi giá trị AI trích xuất
phải truy vết được về transcript gốc — không thì hạ độ tin cậy và gắn cờ,
KHÔNG bao giờ tự sửa/loại bỏ giá trị (đó là việc của cán bộ ở Lớp 4).
"""

from dataclasses import dataclass
from difflib import SequenceMatcher

from app.catalog.models import FieldSpec
from app.domain.extraction_schema import ExtractedField, ExtractionResult

_SIMILARITY_THRESHOLD = 0.85


@dataclass(frozen=True)
class GroundingLogEvent:
    """Sự kiện cần ghi audit log sau khi grounding-check chạy xong."""

    code: str  # "schema_violation_detected" | "unverifiable_value_flagged"
    field_name: str


def verify_grounding(
    result: ExtractionResult, transcript: str, schema: list[FieldSpec]
) -> tuple[ExtractionResult, list[GroundingLogEvent]]:
    """Hậu kiểm bắt buộc sau khi parse kết quả LLM (C5).

    1. Loại bỏ mọi trường không có trong `schema` (NT-4) — LLM không được tự
       thêm trường ngoài catalog.
    2. Với trường `status="extracted"`: nếu `evidence` rỗng HOẶC không khớp
       transcript (so khớp mờ, ngưỡng 0.85) → hạ `confidence` xuống "low" và
       gắn cờ trong `reason` (KHÔNG xóa giá trị — cán bộ vẫn cần thấy để tự
       đối chiếu, chỉ là không còn được coi là đáng tin).
    3. Trả kèm danh sách sự kiện cần ghi log — tầng gọi (service, có I/O)
       chịu trách nhiệm ghi thật qua `AuditService` (E).
    """
    allowed_names = {f.name for f in schema}
    events: list[GroundingLogEvent] = []
    kept_fields: list[ExtractedField] = []

    for field in result.fields:
        if field.name not in allowed_names:
            events.append(GroundingLogEvent("schema_violation_detected", field.name))
            continue
        kept_fields.append(_check_field_grounding(field, transcript, events))

    return ExtractionResult(fields=kept_fields, observations=result.observations), events


def _check_field_grounding(
    field: ExtractedField, transcript: str, events: list[GroundingLogEvent]
) -> ExtractedField:
    if field.status != "extracted":
        return field

    if not field.evidence or not _is_evidence_grounded(field.evidence, transcript):
        events.append(GroundingLogEvent("unverifiable_value_flagged", field.name))
        return field.model_copy(
            update={
                "confidence": "low",
                "reason": "unverifiable: không truy vết được evidence trong transcript",
            }
        )
    return field


def _is_evidence_grounded(evidence: str, transcript: str) -> bool:
    if evidence in transcript:
        return True
    return _similarity(evidence, transcript) >= _SIMILARITY_THRESHOLD


def _similarity(a: str, b: str) -> float:
    """Độ tương đồng mờ giữa `a` và toàn bộ `b`, dùng khớp đoạn con dài nhất.

    `SequenceMatcher.ratio()` trên toàn chuỗi `b` dài sẽ luôn cho điểm thấp
    (vì `b` là cả transcript, dài hơn nhiều `a`) — thay vào đó tìm đoạn khớp
    tốt nhất trong `b` có cùng độ dài với `a` rồi so `ratio()` trên cặp đó.
    """
    matcher = SequenceMatcher(None, a, b)
    match = matcher.find_longest_match(0, len(a), 0, len(b))
    if match.size == 0:
        return 0.0
    window = b[max(0, match.b - 5) : match.b + match.size + 5]
    return SequenceMatcher(None, a, window).ratio()
