"""Schema output của LLM — Mục 10.4 của Plan.

Toàn bộ module này là logic thuần (không I/O) — chỉ định nghĩa kiểu dữ liệu
và hàm parse/sinh JSON Schema.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

Confidence = Literal["high", "medium", "low"]
FieldStatus = Literal["extracted", "missing", "unclear"]


class ExtractedField(BaseModel):
    name: str
    status: FieldStatus
    value: str | None = None
    confidence: Confidence | None = None
    evidence: str | None = Field(
        default=None,
        description="Đoạn nguyên văn trong transcript làm căn cứ",
    )
    reason: str | None = Field(
        default=None,
        description="Lý do khi status là unclear",
    )


class ExtractionResult(BaseModel):
    fields: list[ExtractedField]
    observations: list[str] = Field(
        default_factory=list,
        description="Ghi nhận trung lập, KHÔNG phải kết luận pháp lý",
    )


class ExtractionParseError(Exception):
    """Lỗi parse JSON trả về từ LLM — không phải lỗi hệ thống, cần xử lý mềm."""

    def __init__(self, message: str, raw_text: str) -> None:
        self.raw_text = raw_text
        super().__init__(message)


def parse_extraction_result(raw_text: str) -> ExtractionResult:
    """Parse chuỗi JSON thô từ LLM thành `ExtractionResult`.

    Không bao giờ ném exception ra ngoài ngoại trừ `ExtractionParseError` —
    lỗi parse là tình huống nghiệp vụ bình thường (LLM trả sai định dạng),
    tầng gọi (ExtractionService — I2) phải bắt và xử lý mềm (status=parse_failed),
    không phải một lỗi hệ thống bất ngờ.
    """
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ExtractionParseError(f"JSON không hợp lệ: {exc}", raw_text) from exc

    try:
        return ExtractionResult.model_validate(data)
    except ValidationError as exc:
        raise ExtractionParseError(f"Không khớp schema ExtractionResult: {exc}", raw_text) from exc


def extraction_result_json_schema() -> dict[str, Any]:
    """Sinh JSON Schema từ `ExtractionResult` — dùng làm tool definition cho LLM (F2/F3)."""
    return ExtractionResult.model_json_schema()
