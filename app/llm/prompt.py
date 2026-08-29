"""Prompt cho tầng trích xuất — Mục F3 của Checklist, Mục 10.2/10.3 của Plan.

`SYSTEM_PROMPT_V1` là hằng số có version (đổi nội dung → tăng version) — mọi
lần gọi LLM ghi lại version prompt đã dùng để truy vết (giống `catalog_version`
của D). Hàm `build_user_message()` dựng theo đúng cấu trúc Mục 10.3.
"""

import json

from app.catalog.models import FieldSpec

SYSTEM_PROMPT_VERSION = "v1"

SYSTEM_PROMPT_V1 = """\
Bạn là công cụ trích xuất thông tin hành chính, hỗ trợ cán bộ tại Tổ chuyển
đổi số cộng đồng phường Yên Sở. Bạn KHÔNG phải là người ra quyết định.

NHIỆM VỤ DUY NHẤT: đọc lời nói của người dân đã được chuyển thành văn bản,
và điền các trường dữ liệu được liệt kê trong danh sách cho sẵn.

QUY TẮC BẮT BUỘC:
1. CHỈ trích xuất thông tin người dân đã nói rõ ràng trong đoạn văn bản.
2. TUYỆT ĐỐI KHÔNG suy đoán, không điền giá trị mặc định, không dùng kiến
   thức bên ngoài để bổ sung thông tin.
3. Nếu một trường không có thông tin → "missing".
   Nếu có nhắc tới nhưng không đủ rõ để dùng → "unclear" kèm lý do.
4. Với MỖI giá trị trích xuất được, phải trích dẫn nguyên văn đoạn trong
   văn bản làm căn cứ (trường "evidence"). Không có căn cứ thì không được
   điền giá trị.
5. CHỈ điền các trường có trong danh sách được cung cấp. KHÔNG tự thêm
   trường mới.
6. KHÔNG đưa ra tư vấn pháp lý, KHÔNG kết luận hồ sơ hợp lệ hay không,
   KHÔNG nêu quy định pháp luật. Đó là việc của cán bộ.
7. KHÔNG tự quyết định thủ tục cần giấy tờ gì — danh sách giấy tờ do hệ
   thống cung cấp, không phải do bạn sinh ra.
8. Chỉ trả lời bằng cách gọi tool được cung cấp, không thêm bất kỳ văn bản
   giải thích nào ngoài tool đó.

VỀ ĐỘ TIN CẬY (confidence):
- "high": người dân nói rõ ràng, trực tiếp, không mơ hồ.
- "medium": suy ra được từ ngữ cảnh nhưng chắc chắn hợp lý.
- "low": có dấu hiệu nhưng mơ hồ, cần cán bộ kiểm tra kỹ.

LƯU Ý: đây là dữ liệu của người dân thật, dùng cho hồ sơ hành chính có giá
trị pháp lý. Một giá trị bịa ra có thể khiến người dân phải đi lại nhiều lần.
Thà để missing còn hơn đoán sai.
"""


def build_user_message(
    procedure_name: str,
    procedure_code: str,
    fields: list[FieldSpec],
    confirmed_values: dict[str, str],
    transcript_turns: list[str],
    only_missing_fields: bool = False,
) -> str:
    """Dựng user message theo cấu trúc Mục 10.3 của Plan.

    `fields`: toàn bộ trường của thủ tục theo catalog (D). Khi
    `only_missing_fields=True`, chỉ đưa vào các trường CHƯA có trong
    `confirmed_values` — dùng khi hỏi lại/bổ sung, không cần LLM xử lý lại
    toàn bộ schema.
    `transcript_turns`: mỗi phần tử là nội dung một lượt nói, được đánh số
    tự động thành `[Lượt 1]`, `[Lượt 2]`...
    """
    if only_missing_fields:
        fields = [f for f in fields if f.name not in confirmed_values]

    fields_json = _fields_to_prompt_json(fields)
    confirmed_json = _confirmed_values_to_prompt_json(confirmed_values)
    numbered_turns = "\n".join(f"[Lượt {i}] {turn}" for i, turn in enumerate(transcript_turns, 1))

    return f"""\
### Loại thủ tục
{procedure_name} (mã: {procedure_code})

### Các trường cần trích xuất
{fields_json}

### Các trường đã có giá trị (đã được cán bộ xác nhận — KHÔNG thay đổi)
{confirmed_json}

### Lời nói của người dân (đã chuyển thành văn bản)
---
{numbered_turns}
---

### Yêu cầu
Trả về JSON đúng định dạng schema đã cho.
"""


def build_single_field_correction_message(
    field: FieldSpec, transcript_turns: list[str]
) -> str:
    """Prompt ngắn gọn cho UC4 (sửa một trường) — không cần schema đầy đủ."""
    numbered_turns = "\n".join(f"[Lượt {i}] {turn}" for i, turn in enumerate(transcript_turns, 1))
    return f"""\
### Trường cần trích xuất lại
{_fields_to_prompt_json([field])}

### Lời nói của người dân (đã chuyển thành văn bản)
---
{numbered_turns}
---

### Yêu cầu
Trả về JSON đúng định dạng schema đã cho, chỉ với trường trên.
"""


def _fields_to_prompt_json(fields: list[FieldSpec]) -> str:
    return json.dumps(
        [
            {
                "name": f.name,
                "label": f.label,
                "type": f.type,
                "required": f.required,
            }
            for f in fields
        ],
        ensure_ascii=False,
    )


def _confirmed_values_to_prompt_json(confirmed_values: dict[str, str]) -> str:
    return json.dumps(confirmed_values, ensure_ascii=False)
