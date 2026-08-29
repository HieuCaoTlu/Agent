# KIẾN TRÚC KỸ THUẬT CHI TIẾT
## Trợ lý giọng nói AI hỗ trợ kê khai, nộp hồ sơ thủ tục hành chính trực tuyến
### Phường Yên Sở — Bản kế hoạch triển khai kỹ thuật

---

## 1. Tổng quan kiến trúc

### 1.1. Nguyên tắc thiết kế cốt lõi

Toàn bộ kiến trúc tuân theo nguyên tắc đã được chuẩn hóa trong các triển khai AI khu vực công năm 2026: **"AI gợi ý và truy xuất; hồ sơ do con người lập là bản chính thức"**. Cụ thể:

- AI **không** tự ý gửi, xác nhận, hoặc hoàn tất bất kỳ giao dịch nào với hệ thống chính phủ.
- Mọi output của AI đều ở dạng **gợi ý (suggestion)** hiển thị cho cán bộ, chưa phải dữ liệu đã ghi nhận.
- Cán bộ tự tay xác nhận/gõ **từng trường dữ liệu** — không có nút "đồng ý tất cả" cho toàn bộ form.
- Mọi bước xử lý đều được ghi log đầy đủ: input, output AI, hành động cán bộ, thời gian.
- Không dữ liệu cá nhân nào được gửi ra ngoài phạm vi đã được phê duyệt.

### 1.2. Sơ đồ luồng tổng thể

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│  Công dân   │────▶│  STT         │────▶│  Claude API  │────▶│  Giao diện   │
│  (giọng nói)│     │  (BlazeAI)   │     │  (trích xuất │     │  gợi ý cho   │
└─────────────┘     └──────────────┘     │   + gợi ý)   │     │  cán bộ      │
       ▲                                  └─────────────┘     └──────┬───────┘
       │             ┌──────────────┐                                │
       └─────────────│  TTS         │◀───────────────────────────────┘
                      │  (BlazeAI)   │        (đọc lại xác nhận)
                      └──────────────┘                                │
                                                                       ▼
                                                          ┌────────────────────┐
                                                          │ Cán bộ tự tay nhập  │
                                                          │ vào Cổng DVC/VNeID  │
                                                          │ (thao tác thủ công) │
                                                          └────────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  FastAPI Backend      │
                  │  - Quản lý phiên      │
                  │  - State machine      │
                  │  - Logging đầy đủ     │
                  │  - Lưu trữ tạm thời   │
                  └──────────────────────┘
```

### 1.3. Stack công nghệ

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| STT (Speech-to-Text) | BlazeAI | Chuyển giọng nói công dân thành văn bản |
| TTS (Text-to-Speech) | BlazeAI | Đọc lại nội dung để công dân xác nhận |
| LLM xử lý ngôn ngữ | Claude API (Claude Sonnet 5) | Trích xuất trường dữ liệu, gợi ý biểu mẫu, phát hiện thiếu sót |
| Backend | FastAPI (Python) | Điều phối luồng, quản lý phiên, logging |
| Database | PostgreSQL | Lưu phiên làm việc, log, dữ liệu tạm |
| Cache/Queue | Redis | Quản lý trạng thái phiên real-time, hàng đợi xử lý audio |
| Frontend cán bộ | React (hoặc giao diện hiện có) | Hiển thị gợi ý song song với Cổng DVC |

**Vì sao chọn kiến trúc cascaded (tuần tự) thay vì speech-to-speech:** Đây là use case có mức độ rủi ro cao, liên quan đến dữ liệu định danh công dân và cần khả năng kiểm toán (auditability) — pattern chuẩn ngành năm 2026 cho các use case chính phủ/y tế/tài chính là dùng kiến trúc cascaded (STT riêng → LLM riêng → TTS riêng) thay vì mô hình speech-to-speech hợp nhất, vì cascaded cho phép log và kiểm tra được từng bước trung gian, còn speech-to-speech tuy nhanh hơn nhưng khó audit hơn.

---

## 2. Luồng nghiệp vụ chi tiết (7 bước, ánh xạ vào hệ thống)

### Bước 1: Tiếp nhận yêu cầu bằng giọng nói

**Input:** Audio stream từ micro tại điểm hỗ trợ.

**Xử lý:**
1. Frontend ghi âm, gửi audio chunk (streaming) tới FastAPI qua WebSocket.
2. FastAPI forward tới BlazeAI STT API theo thời gian thực.
3. BlazeAI trả về transcript (text) theo từng đoạn.

**Output:** Văn bản thô, ví dụ: *"Tôi muốn đăng ký khai sinh cho con tôi"*.

**Ghi log:** `session_id`, `timestamp`, `audio_duration`, `raw_transcript`.

---

### Bước 2: Chuyên viên đăng nhập hộ, chọn nhóm thủ tục

**Đây là thao tác thủ công của cán bộ** — không tự động hóa. Cán bộ:
1. Đăng nhập tài khoản định danh của công dân trên Cổng DVC/VNeID (theo đúng quy trình xác thực hiện hành).
2. Dựa vào transcript ở Bước 1 (đã hiển thị trên giao diện), chọn nhóm thủ tục phù hợp từ danh sách được định nghĩa sẵn trong hệ thống (dropdown/danh mục thủ tục — **không phải AI tự suy luận và mở ngẫu nhiên**).

**Lý do giữ thủ công ở bước này:** việc chọn đúng loại thủ tục có ảnh hưởng pháp lý trực tiếp; đây là quyết định nghiệp vụ cần con người xác nhận, đúng nguyên tắc "AI outputs limited to reading from verified data; any query outside scope routes to human".

---

### Bước 3: Claude API trích xuất thông tin

**Input:** Transcript đầy đủ (có thể là hội thoại nhiều lượt) + loại thủ tục đã chọn ở Bước 2.

**Xử lý (Claude API call):**

```python
# Ví dụ prompt structure (minh họa, không phải code sản xuất)
system_prompt = """
Bạn là hệ thống trích xuất thông tin hành chính. Nhiệm vụ:
1. Trích xuất các trường dữ liệu từ văn bản: họ tên, ngày sinh, 
   địa chỉ, số CCCD, số điện thoại, nội dung yêu cầu.
2. CHỈ trích xuất thông tin công dân đã nói rõ ràng — không suy đoán, 
   không tự điền giá trị mặc định.
3. Nếu trường nào thiếu hoặc không rõ ràng, đánh dấu "MISSING" hoặc 
   "UNCLEAR", không được bịa giá trị.
4. Trả về kết quả dạng JSON có cấu trúc, kèm độ tin cậy (confidence) 
   cho mỗi trường.
5. Đây là dữ liệu công dân thật — không suy luận ngoài phạm vi thông 
   tin đã cung cấp.
"""

# Output kỳ vọng dạng JSON:
{
  "loai_thu_tuc": "dang_ky_khai_sinh",
  "fields": {
    "ho_ten_con": {"value": "Nguyễn Văn A", "confidence": "high"},
    "ngay_sinh": {"value": "MISSING", "confidence": null},
    "ho_ten_cha": {"value": "Nguyễn Văn B", "confidence": "high"},
    "dia_chi": {"value": "UNCLEAR - cần hỏi lại", "confidence": "low"}
  },
  "canh_bao": ["Thiếu ngày sinh", "Địa chỉ chưa rõ ràng, cần xác nhận"]
}
```

**Nguyên tắc bắt buộc:**
- Claude API **chỉ đọc dữ liệu công dân vừa cung cấp trong phiên hiện tại** — không truy cập, không tra cứu chéo với cơ sở dữ liệu dân cư hay hệ thống khác.
- Không gửi kèm số CCCD/dữ liệu định danh đầy đủ nếu không thực sự cần thiết cho việc trích xuất (data minimization).
- Toàn bộ request/response với Claude API được ghi log để phục vụ kiểm tra sau này.

**Output:** JSON có cấu trúc, hiển thị lên giao diện cán bộ — **chưa ghi vào bất kỳ hệ thống chính thức nào**.

---

### Bước 4: Gợi ý biểu mẫu và cảnh báo thiếu sót

Claude API (cùng lời gọi hoặc lời gọi tiếp theo) trả thêm:
- Danh sách thành phần hồ sơ cần chuẩn bị (dựa trên loại thủ tục đã chọn — tra theo danh mục tĩnh do phường cấu hình sẵn, **không phải AI tự bịa quy định pháp luật**).
- Danh sách cảnh báo: trường thiếu, trường không rõ ràng, khả năng sai định dạng (VD: số điện thoại không đủ 10 số).

**Quan trọng:** Danh mục "thủ tục → thành phần hồ sơ cần thiết" phải là **dữ liệu tĩnh, được phòng chuyên môn xác nhận và cấu hình trong hệ thống**, Claude chỉ tra cứu và trình bày lại — không tự sinh ra yêu cầu hồ sơ từ kiến thức chung chung của mô hình (tránh rủi ro hallucination về quy định pháp luật).

---

### Bước 5: Cán bộ kiểm tra, đối chiếu, tự tay nhập liệu

**Hoàn toàn thủ công, đây là bước kiểm soát chính của toàn hệ thống:**
1. Cán bộ xem giao diện gợi ý (từ Bước 3, 4) **song song** với Cổng DVC/VNeID mở ở tab riêng.
2. Đối chiếu với giấy tờ gốc của công dân.
3. Tự tay gõ/copy từng trường vào form thật trên Cổng DVC.
4. Với mỗi trường, giao diện gợi ý có nút "Đã đối chiếu ✓" để cán bộ đánh dấu — phục vụ thống kê, **không phải để AI tự động điền**.

---

### Bước 6: Đọc lại và xác nhận (TTS)

1. Sau khi cán bộ hoàn tất nhập liệu, hệ thống tổng hợp lại toàn bộ nội dung đã kê khai.
2. BlazeAI TTS đọc lại cho công dân nghe (hoặc hiển thị text để công dân đọc).
3. Công dân xác nhận bằng lời nói ("đúng rồi" / "cần sửa") — nếu cần sửa, quay lại Bước 3.
4. Ghi log xác nhận của công dân (timestamp, nội dung xác nhận).

---

### Bước 7: Nộp hồ sơ và thông báo kết quả

1. Cán bộ tự tay bấm nút nộp hồ sơ trên Cổng DVC/VNeID (thao tác gốc của hệ thống chính phủ, không qua AI).
2. Hệ thống nội bộ ghi nhận: mã hồ sơ, trạng thái, thời gian hoàn tất phiên.
3. Thông báo cho công dân qua giọng nói (TTS) hoặc in phiếu.

---

## 3. Các Use Case chính

### UC1 — Kê khai hồ sơ đơn giản (1 lượt nói, đủ thông tin)

**Tình huống:** Công dân nói một lần đầy đủ thông tin, ví dụ: *"Tôi tên Nguyễn Văn A, sinh ngày 5/3/1990, muốn đăng ký khai sinh cho con tên Nguyễn Văn B, sinh ngày 1/1/2026"*.

**Luồng:** Ghi âm → STT ra transcript → Cán bộ chọn thủ tục "Đăng ký khai sinh" → Claude API trích xuất toàn bộ trường ở 1 lần gọi, không có cảnh báo thiếu → Cán bộ đối chiếu giấy tờ, gõ vào Cổng DVC → TTS đọc lại xác nhận → Công dân xác nhận đúng → Nộp hồ sơ.

**Điểm tóm gọn cần làm:** pipeline STT → Claude extraction 1 lần → hiển thị UI → nhập tay → TTS xác nhận.

---

### UC2 — Kê khai thiếu thông tin, cần hỏi lại

**Tình huống:** Công dân chỉ nói sơ lược, thiếu vài trường bắt buộc (VD: thiếu địa chỉ, thiếu ngày sinh).

**Luồng:** STT ra transcript → Claude API trích xuất, trả về cảnh báo các trường `MISSING`/`UNCLEAR` → Giao diện hiển thị rõ trường còn thiếu cho cán bộ → Cán bộ hỏi lại công dân bằng lời → Vòng lặp quay lại Bước 3 (gọi lại Claude API với transcript mới, gộp với dữ liệu cũ) → Lặp đến khi đủ thông tin → tiếp tục như UC1.

**Điểm tóm gọn cần làm:** cơ chế multi-turn (giữ trạng thái các trường đã có qua nhiều lượt gọi), UI đánh dấu trường thiếu, nút "hỏi lại".

---

### UC3 — Nhiều thủ tục trong một lượt tương tác

**Tình huống:** Công dân có nhu cầu 2 thủ tục cùng lúc, ví dụ vừa đăng ký kết hôn vừa xin xác nhận cư trú.

**Luồng:** STT ghi nhận toàn bộ → Cán bộ tách thành 2 session riêng (mỗi thủ tục 1 phiên) → Mỗi phiên chạy độc lập theo luồng UC1/UC2 → Dữ liệu chung (họ tên, CCCD) có thể tái sử dụng giữa 2 phiên để đỡ phải nói lại.

**Điểm tóm gọn cần làm:** cho phép 1 session cha chứa nhiều session con dùng chung dữ liệu định danh cơ bản.

---

### UC4 — Công dân không xác nhận, yêu cầu sửa

**Tình huống:** Ở bước đọc lại (TTS), công dân phát hiện sai thông tin.

**Luồng:** TTS đọc lại → Công dân nói "sai, tôi sinh năm 1991 chứ không phải 1990" → STT ghi nhận câu sửa → Claude API cập nhật lại trường tương ứng (không trích xuất lại từ đầu) → Cán bộ xác nhận lại trường đã sửa → TTS đọc lại lần nữa → Công dân xác nhận đúng → Tiếp tục nộp.

**Điểm tóm gọn cần làm:** endpoint "cập nhật 1 trường" riêng biệt, không chạy lại toàn bộ pipeline trích xuất.

---

### UC5 — Hệ thống STT nhận diện sai/không rõ giọng nói

**Tình huống:** Giọng địa phương, người lớn tuổi nói không rõ, hoặc ồn tại điểm hỗ trợ khiến STT trả kết quả confidence thấp.

**Luồng:** BlazeAI STT trả `confidence` thấp cho một đoạn → Hệ thống không tự đưa đoạn đó vào trích xuất → Giao diện cảnh báo cán bộ "câu nói chưa rõ, cần hỏi lại hoặc nhập tay" → Cán bộ chủ động hỏi lại hoặc gõ trực tiếp.

**Điểm tóm gọn cần làm:** ngưỡng confidence tối thiểu để chấp nhận transcript, fallback nhập tay khi dưới ngưỡng.

---

### UC6 — Claude API lỗi hoặc phản hồi không hợp lệ

**Tình huống:** Claude API timeout, lỗi mạng, hoặc trả về JSON không đúng định dạng.

**Luồng:** Backend gọi Claude API → lỗi hoặc parse JSON thất bại → Hệ thống không hiển thị dữ liệu rác lên UI → Báo cán bộ "AI tạm thời không hỗ trợ được, vui lòng nhập tay" → Cán bộ chuyển sang quy trình nhập liệu thủ công hoàn toàn (như trước khi có sáng kiến).

**Điểm tóm gọn cần làm:** try/catch toàn diện, có luồng dự phòng (fallback) không phụ thuộc AI.

---

## 4. Thiết kế Backend (FastAPI)

### 3.1. Cấu trúc thư mục đề xuất

```
app/
├── main.py                 # FastAPI entrypoint
├── config.py                # Cấu hình (API keys, endpoints — dùng env vars)
├── api/
│   ├── session.py           # Endpoints quản lý phiên làm việc
│   ├── voice.py              # WebSocket nhận audio, gọi STT
│   ├── extraction.py         # Gọi Claude API để trích xuất
│   └── confirmation.py       # Endpoint xác nhận cuối (Bước 6)
├── services/
│   ├── blaze_stt.py           # Wrapper gọi BlazeAI STT
│   ├── blaze_tts.py           # Wrapper gọi BlazeAI TTS
│   ├── claude_extractor.py    # Wrapper gọi Claude API
│   └── audit_logger.py        # Ghi log tập trung
├── models/
│   ├── session.py             # SQLAlchemy models
│   └── schemas.py             # Pydantic schemas
├── db/
│   └── database.py
└── static_data/
    └── thu_tuc_catalog.json   # Danh mục thủ tục → thành phần hồ sơ (dữ liệu tĩnh)
```

### 3.2. Data model chính (PostgreSQL)

```sql
-- Phiên làm việc
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citizen_ref VARCHAR(50),          -- mã tham chiếu, KHÔNG lưu CCCD đầy đủ nếu không cần
    staff_id VARCHAR(50) NOT NULL,
    procedure_type VARCHAR(100),
    status VARCHAR(20) DEFAULT 'in_progress', -- in_progress, confirmed, submitted, cancelled
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Log từng lượt thoại
CREATE TABLE voice_turns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    turn_number INT,
    raw_transcript TEXT,
    audio_duration_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Kết quả trích xuất từ Claude API (theo từng lần gọi)
CREATE TABLE extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    voice_turn_id UUID REFERENCES voice_turns(id),
    extracted_json JSONB,
    warnings JSONB,
    claude_request_id VARCHAR(100),   -- để đối chiếu với log API
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Xác nhận của cán bộ cho từng trường
CREATE TABLE field_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    field_name VARCHAR(100),
    suggested_value TEXT,
    confirmed_value TEXT,             -- có thể khác giá trị AI gợi ý
    confirmed_by VARCHAR(50),
    confirmed_at TIMESTAMPTZ DEFAULT now()
);

-- Xác nhận cuối của công dân (Bước 6)
CREATE TABLE citizen_confirmations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES sessions(id),
    confirmation_text TEXT,           -- transcript của lời xác nhận
    confirmed BOOLEAN,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Audit log tổng (mọi hành động quan trọng)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID,
    actor VARCHAR(50),                -- 'system', 'staff:<id>', 'citizen'
    action VARCHAR(100),
    detail JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### 3.3. API Endpoints chính

| Method | Endpoint | Mô tả |
|---|---|---|
| POST | `/sessions` | Tạo phiên làm việc mới |
| WS | `/sessions/{id}/voice` | WebSocket streaming audio → STT |
| POST | `/sessions/{id}/extract` | Gửi transcript tới Claude API, nhận JSON gợi ý |
| POST | `/sessions/{id}/fields/{field_name}/confirm` | Cán bộ xác nhận 1 trường cụ thể |
| POST | `/sessions/{id}/readback` | Sinh audio TTS đọc lại toàn bộ nội dung |
| POST | `/sessions/{id}/citizen-confirm` | Ghi nhận xác nhận cuối của công dân |
| POST | `/sessions/{id}/complete` | Đóng phiên sau khi cán bộ đã nộp hồ sơ trên Cổng DVC |
| GET | `/sessions/{id}/audit` | Truy xuất log đầy đủ của 1 phiên (phục vụ kiểm tra) |

### 3.4. Ví dụ code lõi — gọi Claude API để trích xuất (minh họa)

```python
# services/claude_extractor.py
import anthropic
from typing import Optional
import json

client = anthropic.Anthropic()  # API key từ biến môi trường

EXTRACTION_SYSTEM_PROMPT = """
Bạn là hệ thống hỗ trợ trích xuất thông tin hành chính cho cán bộ 
tại Tổ chuyển đổi số cộng đồng. Nhiệm vụ CHỈ là trích xuất, KHÔNG 
suy luận hay bổ sung thông tin công dân không nói ra.

Quy tắc bắt buộc:
1. Chỉ trích xuất thông tin công dân đã nói rõ ràng trong transcript.
2. Nếu thiếu hoặc không rõ, đánh dấu rõ ràng là thiếu — KHÔNG tự bịa.
3. Không đưa ra tư vấn pháp lý hay khẳng định về tính hợp lệ hồ sơ — 
   chỉ nêu observation để cán bộ tự quyết định.
4. Trả lời CHỈ bằng JSON hợp lệ, không thêm text giải thích.
"""

def extract_fields(transcript: str, procedure_type: str, 
                    procedure_schema: dict) -> dict:
    """
    transcript: toàn bộ nội dung công dân đã nói (accumulated)
    procedure_type: loại thủ tục đã được cán bộ chọn (Bước 2)
    procedure_schema: schema các trường cần thiết, lấy từ static_data 
                       (KHÔNG để Claude tự quyết định thủ tục cần gì)
    """
    user_message = f"""
    Loại thủ tục: {procedure_type}
    Các trường cần trích xuất: {json.dumps(procedure_schema, ensure_ascii=False)}
    
    Nội dung công dân đã nói:
    ---
    {transcript}
    ---
    
    Trả về JSON theo đúng cấu trúc các trường trên.
    """
    
    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1500,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )
    
    result_text = response.content[0].text
    # Luôn validate JSON output trước khi dùng — không tin tưởng mù quáng
    try:
        result = json.loads(result_text)
    except json.JSONDecodeError:
        # fallback: đánh dấu lỗi, không throw dữ liệu rác lên UI
        return {"error": "extraction_parse_failed", "raw": result_text}
    
    return result
```

**Lưu ý bảo mật quan trọng trong code trên:**
- `procedure_schema` (danh sách trường cần thiết) lấy từ dữ liệu tĩnh nội bộ, **không để Claude tự "biết" thủ tục cần trường gì** — tránh rủi ro model đưa thông tin sai về yêu cầu pháp lý.
- Luôn validate JSON, không tin tưởng output mù quáng.
- Model được yêu cầu rõ **không đưa tư vấn pháp lý** — giữ đúng vai trò hỗ trợ trích xuất dữ liệu.

---

## 5. Thiết kế tích hợp BlazeAI (STT/TTS)

```python
# services/blaze_stt.py (minh họa cấu trúc, cần thay theo API thực tế của BlazeAI)
import httpx

class BlazeSTTClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url

    async def transcribe_stream(self, audio_chunk: bytes) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/v1/stt/stream",
                headers={"Authorization": f"Bearer {self.api_key}"},
                content=audio_chunk,
            )
            resp.raise_for_status()
            return resp.json()  # {"transcript": "...", "is_final": bool, "confidence": float}
```

**Điểm cần làm rõ với BlazeAI trước khi tích hợp thật (bạn cần tự kiểm tra tài liệu BlazeAI vì đây là bên thứ ba, tôi không có thông tin xác thực về API của họ):**
- BlazeAI xử lý dữ liệu ở đâu (server tại Việt Nam hay nước ngoài) — quan trọng vì liên quan tới quy định về dữ liệu công dân.
- Có lưu trữ bản ghi âm sau khi xử lý không — cần đối chiếu với cam kết "không lưu trữ bản ghi âm khi không còn cần thiết" đã nêu trong báo cáo gốc.
- Độ chính xác với giọng địa phương, phương ngữ (nên test trước với dữ liệu thật của phường).

---

## 6. Bảo mật và tuân thủ dữ liệu

| Yêu cầu | Cách triển khai |
|---|---|
| Không lưu bản ghi âm không cần thiết | Xóa audio buffer ngay sau khi có transcript; chỉ giữ transcript text trong thời gian phiên làm việc + thời hạn lưu trữ theo quy định |
| Không đưa dữ liệu cá nhân lên nền tảng chưa được phép | Kiểm tra rõ chính sách dữ liệu của BlazeAI trước khi ký hợp đồng; với Claude API, chỉ gửi dữ liệu tối thiểu cần thiết cho trích xuất, không gửi kèm CCCD đầy đủ nếu không bắt buộc |
| Ghi log đầy đủ | Bảng `audit_log` ghi mọi hành động: ai, làm gì, khi nào, dữ liệu nào được AI xử lý |
| Giới hạn phạm vi truy cập AI | Claude API không có quyền truy cập trực tiếp cơ sở dữ liệu dân cư hay hệ thống VNeID — chỉ nhận transcript qua tham số truyền vào |
| Xác thực & phân quyền | Cán bộ đăng nhập qua tài khoản nội bộ có phân quyền (RBAC); mỗi session gắn với `staff_id` cụ thể |
| Mã hóa | Dữ liệu truyền qua HTTPS/WSS; dữ liệu nhạy cảm trong DB mã hóa at-rest |

---

## 7. Timeline triển khai đề xuất

| Giai đoạn | Nội dung | Thời gian |
|---|---|---|
| Giai đoạn 1 | Setup hạ tầng: FastAPI skeleton, PostgreSQL, tích hợp Claude API cơ bản (test extraction với dữ liệu mẫu) | 2 tuần |
| Giai đoạn 2 | Tích hợp BlazeAI STT/TTS, xây WebSocket streaming audio | 2 tuần |
| Giai đoạn 3 | Xây giao diện cán bộ (hiển thị gợi ý song song), luồng xác nhận từng trường | 2 tuần |
| Giai đoạn 4 | Xây danh mục thủ tục tĩnh (phối hợp phòng chuyên môn xác nhận nội dung), luồng cảnh báo thiếu sót | 1.5 tuần |
| Giai đoạn 5 | Test nội bộ với dữ liệu giả lập, kiểm tra bảo mật, logging | 1.5 tuần |
| Giai đoạn 6 | Thí điểm thật tại điểm hỗ trợ, thu thập phản hồi (khảo sát) | Theo kế hoạch thí điểm (1/7 – 15/12/2026) |

**Tổng thời gian xây dựng trước thí điểm: khoảng 9 tuần.**

---

## PHỤ LỤC: Định hướng phát triển giai đoạn tiếp theo

### Tự động hóa thao tác trên Cổng Dịch vụ công / VNeID

**Ý tưởng:** Ở giai đoạn phát triển tiếp theo, hệ thống có thể mở rộng để AI tự động điều hướng đến đúng phần hồ sơ công dân yêu cầu và tự động điền các trường dữ liệu trên giao diện Cổng DVC/VNeID, dựa trên việc đọc cấu trúc trang, sau khi cán bộ xác nhận. Đây là hướng mở rộng nhằm giảm thêm thao tác thủ công, tiến tới quy trình gần như liền mạch từ giọng nói đến hồ sơ hoàn chỉnh.

Hạng mục này cần sự phối hợp và chấp thuận của đơn vị chủ quản hệ thống (VNeID/Cổng Dịch vụ công quốc gia) trước khi triển khai, nên được đề xuất như một định hướng phát triển dài hạn, nằm ngoài phạm vi thí điểm hiện tại.

---

*Tài liệu này phục vụ mục đích lập kế hoạch kỹ thuật nội bộ, cần được rà soát bởi bộ phận pháp chế và an toàn thông tin trước khi triển khai chính thức.*