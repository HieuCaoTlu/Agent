# CHECKLIST XÂY DỰNG PHẦN MỀM (MVP)

## Trợ lý giọng nói AI hỗ trợ kê khai, nộp hồ sơ thủ tục hành chính trực tuyến

**Tài liệu tham chiếu:** [Plan.MD](Plan.MD)
**Phạm vi:** MVP chạy được — tập trung vào luồng tương tác cốt lõi: **tạo phiên mới → ghi âm/hỏi lại → trích xuất → xác nhận trường → đọc lại → kết thúc phiên**.
**Đã lược bỏ khỏi MVP này (xem ghi chú cuối file):** đăng nhập/phân quyền nhiều vai trò, dashboard thống kê/báo cáo, bộ test đầy đủ.
**Cách dùng:** Đánh dấu `[x]` khi hoàn thành. Mỗi mục là một đơn vị công việc có thể giao cho một người và kiểm tra được kết quả.

---

## MỤC LỤC

- [A. Khởi tạo dự án](#a-khởi-tạo-dự-án)
- [B. Tầng dữ liệu](#b-tầng-dữ-liệu)
- [C. Domain — logic thuần](#c-domain--logic-thuần)
- [D. Procedure Catalog](#d-procedure-catalog)
- [E. Audit logging](#e-audit-logging)
- [F. Tầng LLM](#f-tầng-llm)
- [G. Tầng STT (Blaze API)](#g-tầng-stt-blaze-api)
- [H. Tầng TTS (Blaze API)](#h-tầng-tts-blaze-api)
- [I. Service điều phối](#i-service-điều-phối)
- [J. API endpoints](#j-api-endpoints)
- [K. WebSocket giọng nói](#k-websocket-giọng-nói)
- [L. Độ tin cậy và xử lý lỗi tối thiểu](#l-độ-tin-cậy-và-xử-lý-lỗi-tối-thiểu)
- [M. Frontend — nền tảng](#m-frontend--nền-tảng)
- [N. Frontend — màn hình](#n-frontend--màn-hình)
- [O. Frontend — component nghiệp vụ](#o-frontend--component-nghiệp-vụ)
- [P. Kiểm thử tối thiểu](#p-kiểm-thử-tối-thiểu)
- [Q. Đóng gói và chạy](#q-đóng-gói-và-chạy)
- [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp)

---

## A. Khởi tạo dự án

### A1. Cấu trúc và công cụ

- [x] Tạo `pyproject.toml` khai báo metadata dự án, Python 3.12
- [x] Khai báo dependency chính: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `pydantic`, `pydantic-settings`, `redis`, `httpx`, `anthropic`, `structlog`
- [x] Khai báo dependency dev: `pytest`, `pytest-asyncio`, `respx`, `ruff`
- [x] Chạy `uv sync`, xác nhận sinh được `uv.lock`
- [x] Tạo cây thư mục cơ bản (`app/`, `tests/`, `frontend/`, `scripts/`, `migrations/`)
- [x] Tạo file `__init__.py` cho mọi package Python
- [x] Tạo `.gitignore` — bắt buộc có `.env`, `.venv/`, `__pycache__/`, `*.pyc`, `node_modules/`, `dist/`
- [x] Khởi tạo git repository, commit đầu tiên

### A2. Cấu hình

- [x] Viết `app/config.py` với class `Settings(BaseSettings)`
- [x] Tạo `.env.example` liệt kê đầy đủ biến môi trường — đã có sẵn tại [.env.example](.env.example), gồm cấu hình Blaze STT/TTS thật (base URL, model, speaker_id...)
- [x] Thêm field cấu hình Blaze vào `Settings`: `blaze_api_token`, `blaze_base_url`, `blaze_ws_base_url`, `blaze_stt_async_model`, `blaze_stt_stream_model`, `blaze_stt_language`, `blaze_stt_topic`, `blaze_stt_context`, `blaze_stt_bias_keywords` (list), `blaze_tts_model`, `blaze_tts_realtime_model`, `blaze_tts_speaker_id`, `blaze_tts_audio_format`, `blaze_tts_audio_quality`, `blaze_tts_audio_speed`, `blaze_tts_normalization`, `blaze_tts_pcm_sample_rate`
- [x] Thêm validator bắt buộc có `anthropic_api_key` khi `llm_provider="claude"`
- [x] Thêm validator bắt buộc có `blaze_api_token` khi `stt_provider="blaze"` hoặc `tts_provider="blaze"`
- [x] Parse `approved_ai_hosts` và `blaze_stt_bias_keywords` từ chuỗi phân cách dấu phẩy trong `.env` thành `list[str]`
- [x] Viết hàm `get_settings()` có cache (`lru_cache`) để dùng làm FastAPI dependency

### A3. Ứng dụng FastAPI

- [x] Viết `app/main.py` khởi tạo FastAPI với `title`, `version`
- [x] Cấu hình CORS middleware, chỉ cho phép origin của frontend
- [x] Viết exception handler chung trả về định dạng lỗi thống nhất theo Mục 9.1 của Plan
- [x] Viết exception handler riêng cho `InvalidTransitionError` → HTTP 409
- [x] Viết exception handler riêng cho `ProcedureNotFound` → HTTP 404
- [x] Đăng ký lifespan handler: kết nối/ngắt DB, Redis, nạp catalog khi khởi động (khung sẵn, TODO nối B1/D2)
- [x] Endpoint `GET /health` — kiểm tra DB, Redis, các provider AI (khung sẵn, health_check thật nối ở B/F/G/H)

---

## B. Tầng dữ liệu

### B1. Kết nối

- [x] Viết `app/db/database.py`: async engine, `async_sessionmaker`, dependency `get_db()`
- [x] Viết `app/db/redis_client.py`: connection pool, dependency `get_redis()`

### B2. SQLAlchemy models

- [x] `app/models/base.py` — `DeclarativeBase`, mixin `created_at`/`updated_at`
- [x] `app/models/session.py` — model `Session` (gồm quan hệ tự tham chiếu `parent_session_id`)
- [x] `app/models/voice.py` — model `VoiceTurn`
- [x] `app/models/extraction.py` — model `Extraction`, `FieldState`, `FieldHistory`
- [x] `app/models/confirmation.py` — model `CitizenConfirmation`
- [x] `app/models/audit.py` — model `AuditLog`
- [x] Khai báo đầy đủ relationship và cascade delete
- [x] Khai báo `CheckConstraint` cho cột `state` của bảng `sessions`
- [x] Khai báo `UniqueConstraint` cho `(session_id, turn_number)` và `(session_id, field_name)`

> **Ghi chú kỹ thuật:** để phát triển/kiểm thử được khi chưa có Docker/Postgres sẵn, các model dùng kiểu đa dialect tự viết trong `app/models/base.py` (`GUID`, `BigAutoIncrement`) — tương đương UUID/BIGSERIAL thật trên Postgres (production), map sang kiểu tương thích trên SQLite (chỉ dùng cho dev/test cục bộ, xem `tests/conftest.py`). Không ảnh hưởng schema Postgres thật.

> **Lược bỏ:** model `StaffUser` — không có bảng người dùng riêng ở MVP này (xem [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp)). Các cột từng tham chiếu `staff_id`/`confirmed_by`/`recorded_by` giữ nguyên kiểu nhưng không ràng buộc khóa ngoại tới bảng người dùng — dùng một chuỗi định danh cán bộ đơn giản (ví dụ tên nhập tay lúc tạo phiên) thay vì tài khoản đăng nhập.

### B3. Migration

- [x] Khởi tạo Alembic, cấu hình `alembic.ini` đọc `database_url` từ settings
- [x] Cấu hình `env.py` hỗ trợ async engine
- [x] Sinh migration đầu tiên tạo toàn bộ bảng theo Mục 8.2 của Plan
- [x] Viết migration tạo cột tính toán `duration_ms` cho bảng `sessions`
- [x] Viết migration `REVOKE UPDATE, DELETE` trên `audit_log` và `field_history`
- [x] Kiểm tra `alembic upgrade head` chạy sạch — đã verify trên SQLite (upgrade/downgrade round-trip + no-drift check); **cần re-verify trên Postgres thật khi Docker sẵn sàng**

### B4. Repository layer

- [x] `SessionRepository` — CRUD phiên, truy vấn theo ngày/trạng thái
- [x] `VoiceTurnRepository` — thêm lượt thoại, lấy danh sách theo phiên, tự tăng `turn_number`
- [x] `ExtractionRepository` — lưu kết quả trích xuất, lấy lịch sử
- [x] `FieldStateRepository` — upsert trạng thái trường, lấy toàn bộ trường của phiên
- [x] `FieldHistoryRepository` — chỉ có hàm append, không có update/delete
- [x] `AuditRepository` — append log, truy vấn theo phiên/hành động/thời gian
- [x] Bộ test `tests/repositories/` (22 test) phủ CRUD, unique constraint, cascade delete, append-only, truy vấn theo ngày/trạng thái/hành động

---

## C. Domain — logic thuần

> Toàn bộ mục này **không được** import bất kỳ thứ gì liên quan I/O (không DB, không HTTP, không Redis).

### C1. State machine

- [ ] Định nghĩa enum `SessionState` với 12 trạng thái
- [ ] Định nghĩa enum `SessionEvent` với đầy đủ sự kiện
- [ ] Khai báo bảng chuyển đổi hợp lệ theo Mục 5.3 của Plan
- [ ] Viết hàm `transition(current, event, context) -> SessionState`
- [ ] Định nghĩa exception `InvalidTransitionError` kèm thông báo tiếng Việt rõ ràng
- [ ] Kiểm tra điều kiện chuyển sang `FIELDS_CONFIRMED`: mọi trường `required` đã xác nhận
- [ ] Kiểm tra điều kiện chuyển sang `COMPLETED`: có `dossier_code`

### C2. Validator trường dữ liệu

- [ ] Định nghĩa kiểu `ValidationResult` (status, message)
- [ ] `cccd_12_digits` — đúng 12 chữ số
- [ ] `vn_phone_10_digits` — 10 chữ số, đầu số hợp lệ 03/05/07/08/09
- [ ] `date_not_future` — không phải ngày tương lai
- [ ] `date_reasonable_birth` — trong khoảng 130 năm
- [ ] `vietnamese_name` — chỉ chữ cái tiếng Việt có dấu và khoảng trắng, 2–50 ký tự
- [ ] `in_options` — thuộc danh sách `options` của trường enum
- [ ] `required_present` — trường bắt buộc phải có giá trị
- [ ] Viết registry ánh xạ tên validator → hàm, dùng cho catalog
- [ ] Viết hàm `validate_field(spec, value) -> ValidationResult` chạy toàn bộ validator của trường
- [ ] Viết hàm `validate_all(schema, values) -> dict[str, ValidationResult]`

### C3. Chuẩn hóa dữ liệu tiếng Việt

- [ ] Chuẩn hóa ngày tháng nói bằng lời: "mùng 5 tháng 3 năm 2026", "5/3/2026", "năm nay" → định dạng chuẩn
- [ ] Chuẩn hóa số nói bằng chữ: "không tám một hai..." → chuỗi số
- [ ] Chuẩn hóa họ tên: viết hoa chữ cái đầu, gộp khoảng trắng thừa
- [ ] Chuẩn hóa số điện thoại: bỏ dấu chấm, gạch ngang, khoảng trắng
- [ ] Chuẩn hóa giới tính: "trai"/"nam"/"con trai" → "Nam"

### C4. Quy tắc gộp đa lượt

- [ ] Định nghĩa kiểu `MergeDecision` (giá trị mới, có ghi đè không, cảnh báo phát sinh)
- [ ] Hiện thực bảng quy tắc 4 trường hợp theo Mục 7.1 của Plan
- [ ] Xử lý: trường đã xác nhận **không bị** ghi đè, sinh cảnh báo `conflict_with_confirmed`
- [ ] Xử lý: giá trị mới `MISSING` không xóa giá trị cũ
- [ ] Viết hàm `merge_extraction(current_states, new_extraction) -> list[MergeDecision]`

### C5. Schema output LLM

- [ ] Định nghĩa `ExtractedField` (name, status, value, confidence, evidence, reason)
- [ ] Định nghĩa `ExtractionResult` (fields, observations)
- [ ] Định nghĩa các Literal type: `Confidence`, `FieldStatus`
- [ ] Viết hàm parse JSON có xử lý lỗi, không ném exception ra ngoài
- [ ] Viết hàm sinh JSON Schema từ Pydantic model để đưa vào tool definition của LLM

### C6. Sinh cảnh báo

- [ ] Định nghĩa kiểu `Warning` (severity, field, message, code)
- [ ] Sinh cảnh báo `error` khi thiếu trường bắt buộc
- [ ] Sinh cảnh báo `warning` khi trường `UNCLEAR`
- [ ] Sinh cảnh báo `warning` khi validator báo sai định dạng
- [ ] Sinh cảnh báo `warning` khi giá trị không truy vết được về transcript
- [ ] Sắp xếp cảnh báo theo mức độ nghiêm trọng
- [ ] Sinh câu hỏi gợi ý cho cán bộ từ `spoken_hint` của trường còn thiếu

---

## D. Procedure Catalog

### D1. Định nghĩa dữ liệu

- [ ] Định nghĩa Pydantic model `FieldSpec`, `Document`, `Procedure`
- [ ] Viết file catalog `dang_ky_khai_sinh.json` đầy đủ theo mẫu Mục 6.3 của Plan
- [ ] Viết file catalog `dang_ky_ket_hon.json`
- [ ] Viết file catalog `chung_thuc_dien_tu.json`
- [ ] Mỗi file phải có đủ: `catalog_version`, `approved_by`, `approved_at`, `legal_basis`, `effective_from`

> Bắt đầu với 2–3 thủ tục ưu tiên cao (Mục 6.4 của Plan) là đủ cho MVP; các thủ tục còn lại thêm sau khi luồng chính chạy ổn.

### D2. Catalog Service

- [ ] Viết `CatalogService` nạp toàn bộ file JSON khi khởi động ứng dụng
- [ ] Hàm `list_active(at: date)` — lọc theo `effective_from`/`effective_to`
- [ ] Hàm `get(code, at)` — ném `ProcedureNotFound` nếu không có
- [ ] Hàm `get_field_schema(code)`
- [ ] Hàm `get_required_documents(code)`
- [ ] Hàm `get_readback_template(code)`
- [ ] Cache trong bộ nhớ, không đọc file mỗi request

---

## E. Audit logging

> Giữ lại vì đây là ghi log kỹ thuật cần cho việc gỡ lỗi và truy vết dữ liệu cá nhân — không phải màn hình tra cứu/báo cáo (đã lược bỏ, xem cuối file).

- [ ] Định nghĩa enum `AuditAction` với đầy đủ hành động theo Mục 8.3 của Plan
- [ ] Viết `AuditService.log(session_id, actor_type, actor_id, action, detail)`
- [ ] Đảm bảo ghi audit nằm cùng transaction với thao tác nghiệp vụ
- [ ] Ghi log tự động mọi lần chuyển trạng thái phiên
- [ ] Loại bỏ giá trị nhạy cảm khỏi `detail` trước khi ghi (không lưu CCCD nguyên vẹn)

---

## F. Tầng LLM

### F1. Trừu tượng hóa

- [ ] Định nghĩa `LLMProvider` (abstract base class) với hàm `extract()` và `health_check()`
- [ ] Định nghĩa dataclass `LLMResponse` (raw_text, parsed, input_tokens, output_tokens, latency_ms, model)
- [ ] Viết `MockLLMProvider` trả kết quả cố định theo transcript đầu vào — dùng để phát triển khi chưa có key thật
- [ ] Viết factory chọn provider theo `settings.llm_provider`

### F2. Claude provider

- [ ] Viết `ClaudeLLMProvider` dùng SDK `anthropic` bản async
- [ ] Cấu hình `temperature=0`, `max_tokens=2000`, timeout 30 giây
- [ ] Dùng tính năng structured output / tool-use để ép định dạng JSON thay vì chỉ dựa vào prompt
- [ ] Bắt và phân loại lỗi: timeout, rate limit, lỗi mạng, lỗi API
- [ ] Retry 2 lần với backoff 1s và 3s, chỉ retry lỗi tạm thời
- [ ] Kiểm tra hostname thuộc `approved_ai_hosts` trước khi gọi, ném exception nếu không

### F3. Prompt

- [ ] Viết system prompt đầy đủ theo Mục 10.2 của Plan, lưu thành hằng số có version
- [ ] Viết hàm dựng user message theo cấu trúc Mục 10.3 của Plan
- [ ] Đưa field schema từ catalog vào message dưới dạng JSON
- [ ] Đưa danh sách trường đã xác nhận vào message với chỉ dẫn không được thay đổi
- [ ] Đánh số lượt thoại trong transcript (`[Lượt 1]`, `[Lượt 2]`...)
- [ ] Hỗ trợ chế độ `only_missing_fields` — chỉ yêu cầu điền trường còn thiếu
- [ ] Viết hàm sinh prompt cho endpoint sửa một trường (UC4), ngắn gọn hơn prompt đầy đủ

### F4. Che dữ liệu nhạy cảm

- [ ] Viết class `PIIRedactor`
- [ ] Nhận diện chuỗi 12 chữ số liên tiếp trong transcript (số CCCD)
- [ ] Nhận diện số CCCD nói bằng chữ ("không tám một hai...")
- [ ] Thay bằng placeholder `[CCCD_1]`, `[CCCD_2]`...
- [ ] Giữ bảng ánh xạ trong bộ nhớ của phiên, tuyệt đối không ghi xuống DB
- [ ] Viết hàm khôi phục giá trị thật sau khi nhận kết quả từ LLM
- [ ] Đọc cấu hình `redact_to_llm` từ catalog để quyết định trường nào cần che

### F5. Kiểm chứng nguồn gốc

- [ ] Viết `verify_grounding(result, transcript, schema)`
- [ ] Loại bỏ mọi trường không có trong schema của catalog
- [ ] Với trường `status="extracted"`: kiểm tra `evidence` có rỗng không
- [ ] So khớp mờ `evidence` với transcript, ngưỡng tương đồng 0.85
- [ ] Hạ `confidence` xuống `low` và gắn cờ `unverifiable` khi không khớp
- [ ] Ghi log `schema_violation_detected` khi có trường lạ
- [ ] Ghi log `unverifiable_value_flagged` khi không truy vết được

---

## G. Tầng STT (Blaze API)

> Tài liệu chính thức: `https://api.blaze.vn` — xác thực Bearer token dùng chung cho mọi sản phẩm Blaze. Base URL và các tham số đã đưa vào [.env.example](.env.example).

> **Quyết định:** bỏ qua cơ chế ngưỡng `confidence` cho STT. Tài liệu Blaze không cam kết trả field này, nên không xây luồng nghiệp vụ phụ thuộc vào một giá trị không đảm bảo có mặt. Việc đánh giá "câu nói có rõ hay không" chuyển hoàn toàn cho **cán bộ** — cán bộ nghe/đọc transcript hiển thị trên UI và tự quyết định hỏi lại hay sửa tay.

### G1. Trừu tượng hóa

- [ ] Định nghĩa `STTProvider` (abstract) với `transcribe_stream()`, `transcribe_file()` và `health_check()`
- [ ] Định nghĩa dataclass `TranscriptChunk` (text, is_final, provider, latency_ms) — **không có field `confidence`**
- [ ] Viết `MockSTTProvider` phát lại transcript có sẵn theo kịch bản — dùng để phát triển khi chưa có key thật
- [ ] Viết factory chọn provider theo `settings.stt_provider`
- [ ] Kiểm tra hostname `api.blaze.vn` thuộc `approved_ai_hosts` trước khi gọi

### G2. Blaze STT — streaming (luồng ghi âm chính tại quầy)

- [ ] Viết `BlazeStreamingSTT` mở kết nối `WS {BLAZE_WS_BASE_URL}/v1/stt/realtime`
- [ ] Gửi message xác thực đầu tiên: `{"token": BLAZE_API_TOKEN, "language": "vi", "model": "stt-stream-1.5"}`
- [ ] Tùy chọn: gửi kèm `topic`, `context`, `bias_keywords` để tăng độ chính xác thuật ngữ hành chính (chỉ hỗ trợ `stt-stream-1.5`)
- [ ] Chờ message `{"type": "ready"}` trước khi bắt đầu gửi audio
- [ ] Gửi audio nhị phân PCM 16kHz, mono, 16-bit qua `ws.send(bytes)` — khớp định dạng frontend ghi âm (xem M4)
- [ ] Nhận và phân biệt message `{"type": "partial"}` và `{"type": "final"}`, đọc field `text`
- [ ] Đóng kết nối WebSocket đúng cách khi kết thúc lượt ghi âm hoặc hủy phiên
- [ ] Xử lý mất kết nối WebSocket giữa chừng — không để mất transcript đã nhận được
- [ ] Bọc toàn bộ bằng interface `STTProvider.transcribe_stream()` để tầng trên không biết chi tiết giao thức Blaze

### G3. Blaze STT — non-streaming (dùng cho UC4 amend một trường)

- [ ] Viết `BlazeFileSTT` gọi `POST {BLAZE_BASE_URL}/v1/stt/execute?model=stt-async-1.5`
- [ ] Gửi file audio dạng `multipart/form-data`, field `audio_file`
- [ ] Header `Authorization: Bearer {BLAZE_API_TOKEN}` (không có `Content-Type` thủ công — để `requests`/`httpx` tự set boundary)
- [ ] Parse response JSON, ánh xạ sang `TranscriptChunk`
- [ ] Retry có giới hạn cho lỗi mạng tạm thời (không retry vô hạn vì audio hữu hạn)

### G4. Kiểm soát chất lượng (thay cho ngưỡng confidence)

- [ ] Không retry khi STT lỗi hẳn (audio đã trôi qua theo thời gian thực), báo lỗi ngay cho frontend
- [ ] Hiển thị mọi transcript cho cán bộ xem trước khi trích xuất — không tự động lọc đoạn nào
- [ ] Cung cấp nút "Sửa transcript" và "Hỏi lại" cho **mọi** lượt thoại

---

## H. Tầng TTS (Blaze API)

### H1. Trừu tượng hóa

- [ ] Định nghĩa `TTSProvider` (abstract) với `synthesize()` và `health_check()`
- [ ] Viết `MockTTSProvider` trả file audio mẫu — dùng để phát triển khi chưa có key thật
- [ ] Viết factory chọn provider theo `settings.tts_provider`
- [ ] Kiểm tra hostname `api.blaze.vn` thuộc `approved_ai_hosts` trước khi gọi

### H2. Blaze TTS — batch (đọc lại toàn bộ nội dung)

- [ ] Viết `BlazeBatchTTS` gọi `POST {BLAZE_BASE_URL}/v1/tts`
- [ ] Body JSON: `query`, `language: "vi"`, `audio_speed`, `audio_quality`, `audio_format`, `normalization`, `speaker_id`, `model: "v2.0_pro"`
- [ ] Header `Authorization: Bearer {BLAZE_API_TOKEN}`, `Content-Type: application/json`
- [ ] Chọn và nghe thử `speaker_id` phù hợp (mẫu: `HN-Nam-1-BL` — giọng Hà Nội)
- [ ] Xử lý response trả về audio (kiểm tra định dạng response thật: base64 trong JSON hay binary trực tiếp — cần test thực tế)
- [ ] Lưu audio kết quả vào Redis với TTL ngắn, phục vụ endpoint tải về

> **Lược bỏ khỏi MVP:** TTS real-time (WebSocket) — dùng batch (H2) làm mặc định và duy nhất, vì đọc lại tại quầy không yêu cầu độ trễ thấp như hội thoại.

### H3. Nội dung đọc lại

- [ ] Viết hàm dựng nội dung đọc lại từ `readback_template` của catalog và giá trị đã xác nhận
- [ ] Che số CCCD trong nội dung gửi tới TTS
- [ ] Đọc số điện thoại thành từng chữ số để người nghe dễ kiểm tra
- [ ] Định dạng ngày tháng thành dạng đọc tự nhiên ("ngày mùng 5 tháng 3 năm 2026")
- [ ] Fallback khi TTS lỗi: trả về văn bản để frontend hiển thị cỡ chữ lớn

---

## I. Service điều phối

### I1. SessionService

- [ ] `create_session(staff_name, parent_session_id, mode)` — **tạo phiên mới**, ghi audit
- [ ] `get_session_state(session_id)` — trả trạng thái đầy đủ gồm mọi trường và cảnh báo
- [ ] `record_consent(session_id, consented)` — ghi nhận đồng ý của người dân
- [ ] `select_procedure(session_id, code)` — kiểm tra catalog, khởi tạo `field_states` rỗng cho mọi trường
- [ ] `cancel_session(session_id, reason)`
- [ ] `complete_session(session_id, dossier_code)` — **kết thúc phiên**, kiểm tra đã có xác nhận của người dân
- [ ] Kế thừa dữ liệu từ phiên cha (UC3) — chỉ các trường trong danh sách trắng

### I2. ExtractionService

- [ ] `extract(session_id, include_turns, only_missing)` — điều phối toàn bộ luồng
- [ ] Bước 1: gom transcript từ các lượt đã chọn theo lựa chọn của cán bộ (`include_turns`) — không có bước lọc tự động theo chất lượng
- [ ] Bước 2: lấy field schema từ catalog
- [ ] Bước 3: che dữ liệu nhạy cảm
- [ ] Bước 4: gọi LLM provider
- [ ] Bước 5: parse và validate schema
- [ ] Bước 6: kiểm chứng nguồn gốc
- [ ] Bước 7: khôi phục giá trị đã che
- [ ] Bước 8: chạy validator từng trường
- [ ] Bước 9: gộp với trạng thái hiện có theo quy tắc merge
- [ ] Bước 10: sinh cảnh báo và câu hỏi gợi ý
- [ ] Bước 11: lưu `extractions` và cập nhật `field_states`, ghi `field_history`
- [ ] Bước 12: ghi audit
- [ ] Kiểm tra giới hạn `max_extractions_per_session`
- [ ] Xử lý lỗi ở mọi bước, không để dữ liệu rác lọt lên UI
- [ ] `amend_field(session_id, field_name, transcript)` — trích xuất một trường (UC4)

### I3. FieldService

- [ ] `confirm_field(session_id, field_name, value, staff_name)` — lưu giá trị chốt
- [ ] Đánh dấu `was_edited=true` khi giá trị khác gợi ý AI
- [ ] Ghi `field_history` với `change_source` phù hợp
- [ ] Kiểm tra và tự động chuyển trạng thái sang `FIELDS_CONFIRMED` khi đủ trường bắt buộc
- [ ] `unconfirm_field(session_id, field_name)` — bỏ xác nhận, dùng khi người dân yêu cầu sửa
- [ ] `get_fields(session_id)` — trả trạng thái mọi trường kèm kết quả validate

### I4. VoiceService

- [ ] `start_recording(session_id)` — **bấm nút hỏi**: tạo lượt thoại mới, cấp `turn_number`
- [ ] `process_audio_chunk(session_id, chunk)` — đẩy tới STT, trả kết quả từng phần
- [ ] `finalize_turn(session_id, transcript)` — lưu vào `voice_turns`
- [ ] `delete_audio_buffer(session_id, turn_id)` — xóa khỏi Redis, ghi `audio_deleted_at`
- [ ] `edit_transcript(session_id, turn_id, new_text, staff_name)` — cán bộ sửa (UC5)
- [ ] `flag_transcript(session_id, turn_id, staff_name)` — cán bộ chủ động gắn cờ "chưa rõ", ghi audit `transcript_flagged_by_staff`

### I5. ReadbackService

- [ ] `generate_readback(session_id)` — dựng nội dung từ template và giá trị đã xác nhận
- [ ] Gọi TTS sinh audio, xử lý fallback sang văn bản khi lỗi
- [ ] Tăng `readback_round` mỗi lần đọc lại
- [ ] `record_citizen_confirmation(session_id, confirmed, note)` — lưu xác nhận hoặc từ chối
- [ ] Khi người dân từ chối: chuyển phiên về `REVIEWING`, ghi audit

---

## J. API endpoints

> Không có middleware xác thực/JWT ở MVP này — xem [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp). Toàn bộ endpoint dùng trực tiếp trong mạng nội bộ điểm hỗ trợ.

### J1. Danh mục thủ tục

- [ ] `GET /api/v1/procedures` — danh sách thủ tục đang hiệu lực
- [ ] `GET /api/v1/procedures/{code}` — chi tiết gồm field schema và thành phần hồ sơ

### J2. Quản lý phiên

- [ ] `POST /api/v1/sessions` — **tạo phiên mới**
- [ ] `GET /api/v1/sessions/{id}` — trạng thái đầy đủ
- [ ] `GET /api/v1/sessions` — danh sách phiên gần đây, có phân trang
- [ ] `POST /api/v1/sessions/{id}/consent` — ghi nhận đồng ý của người dân
- [ ] `POST /api/v1/sessions/{id}/procedure` — chọn thủ tục
- [ ] `POST /api/v1/sessions/{id}/cancel` — hủy phiên
- [ ] `POST /api/v1/sessions/{id}/complete` — **kết thúc phiên** với mã hồ sơ

### J3. Lượt thoại

- [ ] `GET /api/v1/sessions/{id}/turns` — danh sách lượt thoại
- [ ] `PATCH /api/v1/sessions/{id}/turns/{turn_id}` — cán bộ sửa transcript

### J4. Trích xuất

- [ ] `POST /api/v1/sessions/{id}/extract` — gọi LLM trích xuất
- [ ] `GET /api/v1/sessions/{id}/extractions` — lịch sử các lần trích xuất

### J5. Trường dữ liệu

- [ ] `GET /api/v1/sessions/{id}/fields` — trạng thái mọi trường
- [ ] `POST /api/v1/sessions/{id}/fields/{name}/confirm` — xác nhận một trường
- [ ] `POST /api/v1/sessions/{id}/fields/{name}/unconfirm` — bỏ xác nhận
- [ ] `POST /api/v1/sessions/{id}/fields/{name}/amend` — sửa một trường bằng giọng nói
- [ ] Khẳng định trong test: **không tồn tại** endpoint xác nhận hàng loạt

### J6. Đọc lại và xác nhận

- [ ] `POST /api/v1/sessions/{id}/readback` — sinh nội dung và audio
- [ ] `GET /api/v1/sessions/{id}/readback/audio` — tải audio TTS
- [ ] `POST /api/v1/sessions/{id}/citizen-confirm` — ghi nhận xác nhận của người dân

### J7. Chuẩn chung cho mọi endpoint

- [ ] Khai báo response model bằng Pydantic cho mọi endpoint
- [ ] Khai báo mã lỗi có thể trả về trong OpenAPI
- [ ] Hỗ trợ header `Idempotency-Key` cho `confirm`, `complete`, `citizen-confirm`
- [ ] Ghi audit cho mọi thao tác thay đổi dữ liệu

---

## K. WebSocket giọng nói

- [ ] Viết endpoint `WS /api/v1/sessions/{id}/voice`
- [ ] Xử lý message `start` — **bấm nút hỏi**: khởi tạo lượt thoại, mở kết nối tới STT
- [ ] Xử lý message `audio` — kiểm tra kích thước chunk, đẩy tới STT
- [ ] Xử lý message `stop` — chốt transcript, lưu DB, xóa audio buffer
- [ ] Gửi message `partial` khi có kết quả từng phần
- [ ] Gửi message `final` khi chốt một lượt
- [ ] Gửi message `error` khi STT lỗi
- [ ] Gửi message `audio_deleted` xác nhận đã xóa buffer
- [ ] Xử lý ngắt kết nối đột ngột — dọn dẹp buffer, ghi audit
- [ ] Giới hạn thời lượng ghi âm, tự động dừng khi vượt

---

## L. Độ tin cậy và xử lý lỗi tối thiểu

### L1. Suy giảm mềm (bắt buộc — đây là nguyên tắc lõi NT-8)

- [ ] LLM lỗi → chuyển phiên sang `AI_UNAVAILABLE`, cho phép nhập tay
- [ ] STT lỗi → cho phép cán bộ gõ transcript trực tiếp
- [ ] TTS lỗi → trả văn bản để hiển thị
- [ ] Redis lỗi → chuyển sang lưu trạng thái phiên trong PostgreSQL

### L2. Giới hạn cơ bản

- [ ] Giới hạn số lần extraction mỗi phiên (`max_extractions_per_session`)
- [ ] Giới hạn kích thước audio chunk
- [ ] Trả HTTP 429 kèm thông báo tiếng Việt rõ ràng khi vượt giới hạn

> **Lược bỏ khỏi MVP:** circuit breaker nhiều trạng thái (CLOSED/OPEN/HALF_OPEN) dùng Redis chia sẻ giữa worker, giới hạn tần suất theo cán bộ/giờ — thêm khi hệ thống có nhiều người dùng đồng thời thật sự cần bảo vệ.

---

## M. Frontend — nền tảng

### M1. Khởi tạo

- [ ] Khởi tạo Vite + React 18 + TypeScript trong `frontend/`
- [ ] Cấu hình Tailwind CSS
- [ ] Cấu hình đường dẫn alias (`@/` → `src/`)
- [ ] Cấu hình biến môi trường cho URL backend
- [ ] Cấu hình proxy dev server trỏ về backend

### M2. Tầng API client

- [ ] Viết HTTP client bọc `fetch` có xử lý lỗi thống nhất
- [ ] Tự động sinh `X-Request-ID`
- [ ] Sinh type TypeScript từ OpenAPI schema của backend
- [ ] Viết hàm gọi API cho từng nhóm endpoint

### M3. Quản lý trạng thái

- [ ] Cài đặt state management (khuyến nghị TanStack Query cho dữ liệu server)
- [ ] Viết hook `useSession(id)` — lấy và cache trạng thái phiên
- [ ] Viết hook `useFields(sessionId)` — trạng thái các trường
- [ ] Viết hook `useProcedures()` — danh mục thủ tục
- [ ] Cấu hình tự động làm mới dữ liệu phiên sau mỗi thao tác

### M4. WebSocket client

- [ ] Viết hook `useVoiceStream(sessionId)`
- [ ] Xin quyền truy cập micro của trình duyệt
- [ ] Ghi âm bằng `AudioWorklet` (không dùng `MediaRecorder` vì nó encode sang WebM/Opus, còn Blaze STT streaming yêu cầu **PCM thô 16kHz, mono, 16-bit**) — cần resample nếu thiết bị mặc định 44.1kHz/48kHz
- [ ] Gửi audio chunk nhị phân qua WebSocket nội bộ (`/sessions/{id}/voice`) theo lô nhỏ (ví dụ 20–50ms/chunk) để backend chuyển tiếp tới Blaze
- [ ] Nhận và hiển thị transcript từng phần theo thời gian thực
- [ ] Xử lý mất kết nối, tự động kết nối lại
- [ ] Hiển thị mức âm lượng đầu vào để cán bộ biết micro có hoạt động không
- [ ] Dừng ghi âm tự động khi vượt giới hạn thời lượng

---

## N. Frontend — màn hình

- [ ] **Bảng điều khiển** `/` — danh sách phiên gần đây, **nút tạo phiên mới**
- [ ] **Tạo phiên** `/sessions/new` — chọn chế độ, ghi nhận đồng ý của người dân
- [ ] **Màn hình làm việc** `/sessions/:id` — bố cục 2 cột theo Mục 11.1 của Plan, chứa nút ghi âm/hỏi lại và các trường dữ liệu
- [ ] **Đọc lại** `/sessions/:id/readback` — phát audio, nút xác nhận/từ chối
- [ ] **Hoàn tất** `/sessions/:id/complete` — nhập mã hồ sơ, **kết thúc phiên**
- [ ] Màn hình 404 và màn hình lỗi chung

> **Lược bỏ khỏi MVP:** `/login`, `/audit`, `/audit/:sessionId`, `/stats`, `/admin/users` và router bảo vệ theo vai trò — xem [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp).

---

## O. Frontend — component nghiệp vụ

### O1. Component ghi âm (nút hỏi)

- [ ] Nút ghi âm lớn, trạng thái rõ ràng (sẵn sàng / đang ghi / đang xử lý)
- [ ] Hiển thị mức âm lượng theo thời gian thực
- [ ] Hiển thị đồng hồ đếm thời lượng
- [ ] Thông báo rõ khi trình duyệt từ chối quyền micro

### O2. Component transcript

- [ ] Hiển thị danh sách lượt thoại theo thứ tự
- [ ] Mỗi lượt đều có sẵn nút "Sửa" và "Hỏi lại" — không có phân biệt tự động "rõ/chưa rõ" vì không dùng ngưỡng confidence
- [ ] Nút "Sửa" mở ô nhập cho cán bộ chỉnh transcript
- [ ] Nút "Hỏi lại" quay về trạng thái ghi âm
- [ ] Nút "Gắn cờ chưa rõ" cho cán bộ chủ động đánh dấu một lượt (xem I4)
- [ ] Hiển thị transcript từng phần khi đang ghi âm

### O3. Component trường dữ liệu

- [ ] Hiển thị nhãn tiếng Việt đầy đủ của trường
- [ ] Nền màu riêng cho giá trị AI gợi ý, kèm nhãn "Gợi ý AI — chưa xác nhận"
- [ ] Hiển thị đoạn transcript làm căn cứ ngay dưới giá trị
- [ ] Ô nhập cho phép cán bộ sửa giá trị
- [ ] Nút "Đã đối chiếu ✓" xác nhận trường
- [ ] Viền đỏ và nhãn "BẮT BUỘC" cho trường bắt buộc còn thiếu
- [ ] Hiển thị thông báo validate khi sai định dạng
- [ ] Hiển thị câu hỏi gợi ý cho cán bộ khi trường thiếu

### O4. Component khác

- [ ] Checklist thành phần hồ sơ, có ô tích cho cán bộ đánh dấu
- [ ] Thanh tiến độ "Đã xác nhận N/M trường bắt buộc"
- [ ] Danh sách cảnh báo, sắp xếp theo mức độ nghiêm trọng
- [ ] Banner "Chế độ nhập tay" khi AI không khả dụng
- [ ] Hộp thoại xác nhận cho thao tác quan trọng (hủy phiên, hoàn tất)

### O5. Yêu cầu giao diện chung

- [ ] Cỡ chữ tối thiểu 16px toàn ứng dụng
- [ ] Mọi nhãn và thông báo bằng tiếng Việt có dấu, không viết tắt kỹ thuật
- [ ] Khóa nút "Đọc lại cho người dân" cho tới khi đủ trường bắt buộc
- [ ] **Không tạo** nút "Xác nhận tất cả" ở bất kỳ đâu
- [ ] Hiển thị trạng thái đang tải cho mọi thao tác bất đồng bộ

---

## P. Kiểm thử tối thiểu

> Chỉ giữ những test bảo vệ đúng các nguyên tắc lõi và luồng chính có thể chạy được — không xây bộ test toàn diện ở MVP này.

- [ ] Test state machine: các chuyển đổi hợp lệ chính (theo luồng UC1) và một vài trường hợp bất hợp lệ tiêu biểu
- [ ] Test `PIIRedactor` che đúng số CCCD, kể cả dạng nói bằng chữ
- [ ] Test `verify_grounding` bắt được giá trị bịa không có trong transcript (chống hallucination — bắt buộc, đây là rủi ro cao nhất)
- [ ] **Test khẳng định không tồn tại endpoint xác nhận hàng loạt**
- [ ] Test thủ công (không cần tự động hóa) luồng chính đầu-cuối: tạo phiên → ghi âm → trích xuất → xác nhận từng trường → đọc lại → kết thúc phiên
- [ ] Test thủ công: mọi provider AI lỗi, phiên vẫn hoàn tất được bằng nhập tay (UC6)

---

## Q. Đóng gói và chạy

- [ ] Viết `docker-compose.yml` cho local: PostgreSQL, Redis, backend, frontend
- [ ] Viết `Dockerfile` cho backend
- [ ] Viết `README.md` hướng dẫn chạy local: cài đặt, biến môi trường, migration, seed catalog
- [ ] Script `scripts/run_dev.sh` hoặc lệnh `make dev` khởi động backend + frontend cùng lúc
</content>
</invoke>
