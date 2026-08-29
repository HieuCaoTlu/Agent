"""`FieldSpec` tối giản — đủ dùng cho tầng LLM (F) và verify_grounding.

Đây KHÔNG phải bản đầy đủ của catalog (D1 sẽ định nghĩa `FieldSpec`, `Document`,
`Procedure` đầy đủ với `validators`, `spoken_hint`, `redact_to_llm`...). Bản này
chỉ giữ phần tối thiểu để tầng F (LLM) build được prompt và chạy verify_grounding
độc lập với D — khi D1 hoàn thiện, hợp nhất lại thành một nguồn duy nhất.
"""

from typing import Literal

from pydantic import BaseModel

FieldType = Literal[
    "person_name", "date", "national_id", "phone", "address", "enum", "text"
]


class FieldSpec(BaseModel):
    name: str
    label: str
    type: FieldType
    required: bool = False
    options: list[str] | None = None
    spoken_hint: str | None = None
    redact_to_llm: bool = False
