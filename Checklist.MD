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
- [x] Kiểm tra `alembic upgrade head` chạy sạch — verify trên SQLite (round-trip + no-drift) **và trên Postgres thật** (docker-compose, `postgres:16-alpine`): `duration_ms` xác nhận là generated column thật, `chk_state`/FK/cascade đúng

> **Hạn chế đã biết (chấp nhận cho MVP, chưa sửa):** migration `REVOKE UPDATE, DELETE ON audit_log/field_history FROM app_user` **không có hiệu lực thật** vì `app_user` (role duy nhất, chạy cả migration lẫn ứng dụng) là **owner** của bảng — Postgres luôn cho owner toàn quyền bất kể REVOKE. Đã verify bằng thực nghiệm: `UPDATE audit_log ... ` bằng `app_user` vẫn thành công. Muốn REVOKE có tác dụng thật cần tách role migration (owner) khỏi role ứng dụng — chưa làm theo yêu cầu ưu tiên tốc độ, cần quay lại trước khi lên production.

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

> **Rút gọn cho MVP demo (quyết định 30/8/2026):** C3 (chuẩn hóa dữ liệu tiếng Việt) và C4 (quy tắc gộp đa lượt) **cắt hẳn khỏi phạm vi này** — không cần cho việc chứng minh AI trích xuất hoạt động; Claude tự xử lý ngôn ngữ tự nhiên đủ tốt mà không cần tiền xử lý chuẩn hóa, và gộp đa lượt chỉ cần khi có nhiều lần trích xuất trên cùng phiên. C1/C2/C6 rút gọn xuống bản tối thiểu, có thể mở rộng lại sau khi luồng chính chạy được. Xem thêm [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp).

### C1. State machine (rút gọn)

- [x] Định nghĩa enum `SessionState` với 12 trạng thái
- [x] Định nghĩa enum `SessionEvent` với đầy đủ sự kiện
- [x] Khai báo bảng chuyển đổi hợp lệ theo Mục 5.3 của Plan
- [x] Viết hàm `transition(current, event) -> SessionState` — **bản rút gọn: không nhận `context`/điều kiện phụ**, chỉ kiểm tra cạnh có hợp lệ trong bảng chuyển đổi hay không
- [x] Định nghĩa exception `InvalidTransitionError` kèm thông báo tiếng Việt rõ ràng

> **Lược bỏ khỏi bản rút gọn:** kiểm tra điều kiện nghiệp vụ phụ (mọi trường `required` đã xác nhận trước khi `FIELDS_CONFIRMED`, có `dossier_code` trước khi `COMPLETED`...) — để tầng service (I) tự kiểm tra trước khi gọi `transition()`, thay vì state machine tự mang theo `context`.

### C2. Validator trường dữ liệu

- [x] Định nghĩa kiểu `ValidationResult` (status, message)
- [x] `cccd_12_digits` — đúng 12 chữ số
- [x] `vietnamese_name` — chỉ chữ cái tiếng Việt có dấu và khoảng trắng, 2–50 ký tự
- [x] `required_present` — trường bắt buộc phải có giá trị
- [x] `vn_phone_10_digits`, `date_not_future`, `date_reasonable_birth`, `in_options`
- [x] Viết hàm `validate_field(spec, value) -> ValidationResult` chạy toàn bộ validator của trường
- [x] Viết hàm `validate_all(schema, values) -> dict[str, ValidationResult]`

> **Cập nhật (30/8/2026, khi làm I2):** ban đầu rút gọn chỉ giữ 3 validator
> đại diện, nhưng catalog thật (D1) tham chiếu đủ 7 tên validator — đã hỏi
> user và bổ sung 4 validator còn thiếu để `ExtractionService` chạy được với
> catalog thật, thay vì sửa catalog để né vấn đề. `in_options` cần tham số
> `options` (từ `FieldSpec.options`) nên `validate_field`/`validate_all` được
> mở rộng thêm tham số tùy chọn `options`/`field_options` (không phá vỡ
> chữ ký cũ). Test: `tests/domain/test_validators.py` (38 test, +17).

### C5. Schema output LLM

- [x] Định nghĩa `ExtractedField` (name, status, value, confidence, evidence, reason)
- [x] Định nghĩa `ExtractionResult` (fields, observations)
- [x] Định nghĩa các Literal type: `Confidence`, `FieldStatus`
- [x] Viết hàm parse JSON có xử lý lỗi, không ném exception ra ngoài
- [x] Viết hàm sinh JSON Schema từ Pydantic model để đưa vào tool definition của LLM

### C6. Sinh cảnh báo (rút gọn — 2 loại)

- [x] Định nghĩa kiểu `Warning` (severity, field, message, code)
- [x] Sinh cảnh báo `error` khi thiếu trường bắt buộc
- [x] Sinh cảnh báo `warning` khi trường `UNCLEAR`
- [x] Sắp xếp cảnh báo theo mức độ nghiêm trọng

> **Lược bỏ khỏi bản rút gọn:** cảnh báo khi validator báo sai định dạng, cảnh báo khi giá trị không truy vết được (gộp chung vào luồng warning cơ bản ở trên thay vì tách riêng loại), câu hỏi gợi ý từ `spoken_hint` (chưa cần khi UI chưa hiển thị câu hỏi gợi ý).

- [x] Bộ test `tests/domain/` (44 test) phủ C1/C2/C5/C6: toàn bộ cạnh chuyển đổi hợp lệ + CANCEL + trạng thái kết thúc, 3 validator với ca hợp lệ/không hợp lệ, parse JSON hợp lệ/lỗi định dạng/lệch schema, sinh cảnh báo error/warning + sắp xếp mức độ nghiêm trọng

---

## D. Procedure Catalog

### D1. Định nghĩa dữ liệu

- [x] Định nghĩa Pydantic model `FieldSpec`, `Document`, `Procedure` (`app/catalog/models.py`)
- [x] Viết file catalog `dang_ky_khai_sinh.json` đầy đủ theo mẫu Mục 6.3 của Plan
- [x] Viết file catalog `dang_ky_ket_hon.json`
- [x] Viết file catalog `chung_thuc_dien_tu.json`
- [x] Mỗi file phải có đủ: `catalog_version`, `approved_by`, `approved_at`, `legal_basis`, `effective_from`

> Bắt đầu với 2–3 thủ tục ưu tiên cao (Mục 6.4 của Plan) là đủ cho MVP; các thủ tục còn lại thêm sau khi luồng chính chạy ổn.

### D2. Catalog Service

- [x] Viết `CatalogService` nạp toàn bộ file JSON khi khởi động ứng dụng
- [x] Hàm `list_active(at: date)` — lọc theo `effective_from`/`effective_to`
- [x] Hàm `get(code, at)` — ném `ProcedureNotFound` nếu không có
- [x] Hàm `get_field_schema(code)`
- [x] Hàm `get_required_documents(code)`
- [x] Hàm `get_readback_template(code)`
- [x] Cache trong bộ nhớ, không đọc file mỗi request
- [x] Bộ test `tests/catalog/` (6 test) + `tests/services/test_catalog_service.py` (7 test): validate model, `is_active` theo mốc thời gian, `list_active`/`get`/`ProcedureNotFound`, và nạp thật 3 file catalog trong `app/static_data/procedures/`

---

## E. Audit logging (rút gọn)

> Giữ lại vì đây là ghi log kỹ thuật cần cho việc gỡ lỗi và truy vết dữ liệu cá nhân — không phải màn hình tra cứu/báo cáo (đã lược bỏ, xem cuối file). **Rút gọn cho MVP demo (30/8/2026):** chỉ ghi vài action chính, bỏ ràng buộc transaction chặt và redact chi tiết — mở rộng lại khi luồng chính ổn định.

- [x] Định nghĩa enum `AuditAction` — **rút gọn: chỉ các action của luồng chính** (`session_created`, `extraction_requested`, `extraction_succeeded`, `extraction_failed`, `field_confirmed`, `session_completed`, `session_cancelled`), không cần đủ danh mục Mục 8.3 của Plan (`app/domain/audit_action.py`)
- [x] Viết `AuditService.log(session_id, actor_type, actor_id, action, detail)` (`app/services/audit_service.py`, bọc `AuditRepository`, validate `ip_address`)
- [ ] Ghi log tự động mọi lần chuyển trạng thái phiên — **để dành cho tầng service điều phối phiên (chưa tồn tại, thuộc phạm vi phần I)**, không thuộc phạm vi E (E chỉ cung cấp cơ chế ghi log, chưa có nơi gọi tự động)

> **Lược bỏ khỏi bản rút gọn:** đảm bảo cùng transaction chặt với thao tác nghiệp vụ (chấp nhận ghi log ngay sau, không cần atomic), loại bỏ giá trị nhạy cảm khỏi `detail` trước khi ghi (tạm không truyền CCCD vào `detail` thay vì xây cơ chế redact riêng) — cứng hóa lại khi chuẩn bị lên môi trường thật.

- [x] Bộ test `tests/domain/test_audit_action.py` (2 test) + `tests/services/test_audit_service.py` (4 test): đủ 7 action, ghi log có/không field tùy chọn, validate IP hợp lệ/không hợp lệ

---

## F. Tầng LLM

### F1. Trừu tượng hóa

- [x] Định nghĩa `LLMProvider` (abstract base class) với hàm `extract()` và `health_check()` (`app/llm/base.py`)
- [x] Định nghĩa dataclass `LLMResponse` (raw_text, input_tokens, output_tokens, latency_ms, model) — không có field `parsed` riêng: parse là việc của `parse_extraction_result` (C5), gọi ngay sau khi có `raw_text`
- [x] Viết `MockLLMProvider` trả kết quả cố định theo transcript đầu vào — dùng để phát triển khi chưa có key thật (`app/llm/mock_provider.py`)
- [x] Viết factory chọn provider theo `settings.llm_provider` (`app/llm/factory.py`)

### F2. Claude provider

- [x] Viết `ClaudeLLMProvider` dùng SDK `anthropic` bản async (`app/llm/claude_provider.py`)
- [x] Cấu hình `max_tokens=2000`, timeout 30 giây — **`temperature=0` bỏ qua** (đã trao đổi với người dùng): SDK `anthropic` 1.2.0 (bản đang cài) không còn tham số `temperature` trong `messages.create()`, dòng model Claude 5 không expose sampling temperature theo cách cũ nữa
- [x] Dùng tính năng structured output / tool-use để ép định dạng JSON thay vì chỉ dựa vào prompt (tool `submit_extraction_result` với `input_schema` = JSON Schema của `ExtractionResult`, `tool_choice` ép gọi tool này)
- [x] Bắt và phân loại lỗi: timeout, rate limit, lỗi mạng, lỗi API (`app/llm/exceptions.py`: `LLMTimeoutError`, `LLMRateLimitError`, `LLMConnectionError`, `LLMAPIError`)
- [x] Retry 2 lần với backoff 1s và 3s, chỉ retry lỗi tạm thời (không retry `LLMAPIError`)
- [x] Kiểm tra hostname thuộc `approved_ai_hosts` trước khi gọi, ném exception nếu không (`UnapprovedHostError`)

### F3. Prompt

- [x] Viết system prompt đầy đủ theo Mục 10.2 của Plan, lưu thành hằng số có version (`SYSTEM_PROMPT_V1`, `SYSTEM_PROMPT_VERSION` trong `app/llm/prompt.py`)
- [x] Viết hàm dựng user message theo cấu trúc Mục 10.3 của Plan (`build_user_message`)
- [x] Đưa field schema từ catalog vào message dưới dạng JSON
- [x] Đưa danh sách trường đã xác nhận vào message với chỉ dẫn không được thay đổi
- [x] Đánh số lượt thoại trong transcript (`[Lượt 1]`, `[Lượt 2]`...)
- [x] Hỗ trợ chế độ `only_missing_fields` — chỉ yêu cầu điền trường còn thiếu
- [x] Viết hàm sinh prompt cho endpoint sửa một trường (UC4), ngắn gọn hơn prompt đầy đủ (`build_single_field_correction_message`)

### F4. Che dữ liệu nhạy cảm

- [x] Viết class `PIIRedactor` (`app/llm/redactor.py`)
- [x] Nhận diện chuỗi 12 chữ số liên tiếp trong transcript (số CCCD)
- [x] Nhận diện số CCCD nói bằng chữ ("không một hai...")
- [x] Thay bằng placeholder `[CCCD_1]`, `[CCCD_2]`...
- [x] Giữ bảng ánh xạ trong bộ nhớ của phiên, tuyệt đối không ghi xuống DB (không có phương thức nào ghi ra ngoài — verify bằng test)
- [x] Viết hàm khôi phục giá trị thật sau khi nhận kết quả từ LLM (`restore()`)
- [ ] Đọc cấu hình `redact_to_llm` từ catalog để quyết định trường nào cần che — **để dành cho tầng service điều phối trích xuất (phần I, chưa tồn tại)**: `PIIRedactor` chỉ cung cấp cơ chế che/khôi phục, quyết định "có che hay không theo field nào" thuộc về nơi gọi nó

### F5. Kiểm chứng nguồn gốc

- [x] Viết `verify_grounding(result, transcript, schema)` (`app/llm/grounding.py`)
- [x] Loại bỏ mọi trường không có trong schema của catalog
- [x] Với trường `status="extracted"`: kiểm tra `evidence` có rỗng không
- [x] So khớp mờ `evidence` với transcript, ngưỡng tương đồng 0.85 (`difflib.SequenceMatcher`)
- [x] Hạ `confidence` xuống `low` và gắn cờ `unverifiable` khi không khớp (ghi vào `reason`, giữ nguyên giá trị để cán bộ tự đối chiếu)
- [x] Ghi log `schema_violation_detected` khi có trường lạ — trả về dưới dạng `GroundingLogEvent`, tầng gọi (có I/O) ghi thật qua `AuditService` (E)
- [x] Ghi log `unverifiable_value_flagged` khi không truy vết được

- [x] Bộ test `tests/llm/` (31 test): mock provider, factory, prompt (đầy đủ + only_missing_fields + sửa một trường), redactor (số/chữ, khôi phục, không rò rỉ bảng ánh xạ), grounding (giữ nguyên/loại bỏ/hạ confidence), Claude provider (mock hóa `messages.create`, không gọi mạng thật — hostname chặn, retry thành công/hết lượt, lỗi phân loại đúng, health_check)

---

## G. Tầng STT (Blaze API)

> Tài liệu chính thức: `https://api.blaze.vn` — xác thực Bearer token dùng chung cho mọi sản phẩm Blaze. Base URL và các tham số đã đưa vào [.env.example](.env.example).

> **Quyết định:** bỏ qua cơ chế ngưỡng `confidence` cho STT. Tài liệu Blaze không cam kết trả field này, nên không xây luồng nghiệp vụ phụ thuộc vào một giá trị không đảm bảo có mặt. Việc đánh giá "câu nói có rõ hay không" chuyển hoàn toàn cho **cán bộ** — cán bộ nghe/đọc transcript hiển thị trên UI và tự quyết định hỏi lại hay sửa tay.

### G1. Trừu tượng hóa

- [x] Định nghĩa `STTProvider` (abstract) với `transcribe_stream()`, `transcribe_file()` và `health_check()` (`app/stt/base.py`)
- [x] Định nghĩa dataclass `TranscriptChunk` (text, is_final, provider, latency_ms) — **không có field `confidence`**
- [x] Viết `MockSTTProvider` phát lại transcript có sẵn theo kịch bản — dùng để phát triển khi chưa có key thật (`app/stt/mock_provider.py`)
- [x] Viết factory chọn provider theo `settings.stt_provider` (`app/stt/factory.py`)
- [x] Kiểm tra hostname `api.blaze.vn` thuộc `approved_ai_hosts` trước khi gọi (`UnapprovedHostError`)

### G2. Blaze STT — streaming (luồng ghi âm chính tại quầy)

- [x] Viết `BlazeSTTProvider.transcribe_stream()` mở kết nối `WS {BLAZE_WS_BASE_URL}/v1/stt/realtime` (`app/stt/blaze_provider.py`)
- [x] Gửi message xác thực đầu tiên: `{"token": BLAZE_API_TOKEN, "language": "vi", "model": "stt-stream-1.5"}`
- [x] Tùy chọn: gửi kèm `topic`, `context`, `bias_keywords` để tăng độ chính xác thuật ngữ hành chính (chỉ hỗ trợ `stt-stream-1.5`)
- [x] Chờ message `{"type": "ready"}` trước khi bắt đầu gửi audio
- [x] Gửi audio nhị phân qua `ws.send(bytes)` — định dạng PCM 16kHz/mono/16-bit là hợp đồng với frontend (M4, chưa tồn tại), provider không tự validate định dạng byte
- [x] Nhận và phân biệt message `{"type": "partial"}` và `{"type": "final"}`, đọc field `text`
- [x] Đóng kết nối WebSocket đúng cách khi kết thúc lượt ghi âm hoặc hủy phiên (dùng `async with websockets.connect(...)`, tự đóng khi thoát block)
- [x] Xử lý mất kết nối WebSocket giữa chừng — không để mất transcript đã nhận được (mọi chunk đã `yield` trước khi lỗi vẫn giữ nguyên ở tầng gọi, lỗi chỉ ném ra sau khi ngừng nhận thêm được)
- [x] Bọc toàn bộ bằng interface `STTProvider.transcribe_stream()` để tầng trên không biết chi tiết giao thức Blaze

### G3. Blaze STT — non-streaming (dùng cho UC4 amend một trường)

- [x] Viết `BlazeSTTProvider.transcribe_file()` gọi `POST {BLAZE_BASE_URL}/v1/stt/execute?model=stt-async-1.5`
- [x] Gửi file audio dạng `multipart/form-data`, field `audio_file`
- [x] Header `Authorization: Bearer {BLAZE_API_TOKEN}` (không có `Content-Type` thủ công — để `httpx` tự set boundary)
- [x] Parse response JSON, ánh xạ sang `TranscriptChunk`
- [x] Retry có giới hạn cho lỗi mạng tạm thời (không retry vô hạn vì audio hữu hạn) — `_MAX_FILE_RETRIES = 2`, không retry lỗi API cố định (4xx/5xx)

### G4. Kiểm soát chất lượng (thay cho ngưỡng confidence)

- [x] Không retry khi STT lỗi hẳn (audio đã trôi qua theo thời gian thực), báo lỗi ngay cho frontend — `transcribe_stream`/`transcribe_file` ném exception thẳng, không có logic retry-vô-hạn nào ở tầng provider
- [ ] Hiển thị mọi transcript cho cán bộ xem trước khi trích xuất — không tự động lọc đoạn nào — **thuộc tầng frontend (M, chưa tồn tại)**, không phải việc của tầng STT
- [ ] Cung cấp nút "Sửa transcript" và "Hỏi lại" cho **mọi** lượt thoại — **thuộc tầng frontend (M, chưa tồn tại)**

- [x] Bộ test `tests/stt/` (15 test): mock provider (kịch bản, TranscriptChunk không có field confidence), factory (mock/blaze/chặn host), Blaze provider (mock hóa `websockets.connect`/`httpx.AsyncClient` — auth message đúng định dạng, phân biệt partial/final, lỗi kết nối không nuốt transcript đã nhận, retry file thành công/hết lượt/không retry lỗi API)

---

## H. Tầng TTS (Blaze API)

### H1. Trừu tượng hóa

- [x] Định nghĩa `TTSProvider` (abstract) với `synthesize()` và `health_check()` (`app/tts/base.py`)
- [x] Viết `MockTTSProvider` trả file audio mẫu — dùng để phát triển khi chưa có key thật (`app/tts/mock_provider.py`)
- [x] Viết factory chọn provider theo `settings.tts_provider` (`app/tts/factory.py`)
- [x] Kiểm tra hostname `api.blaze.vn` thuộc `approved_ai_hosts` trước khi gọi

### H2. Blaze TTS — batch (đọc lại toàn bộ nội dung)

- [x] Viết `BlazeBatchTTS` gọi `POST {BLAZE_BASE_URL}/v1/tts` (`app/tts/blaze_provider.py`)
- [x] Body JSON: `query`, `language: "vi"`, `audio_speed`, `audio_quality`, `audio_format`, `normalization`, `speaker_id`, `model: "v2.0_pro"`
- [x] Header `Authorization: Bearer {BLAZE_API_TOKEN}`, `Content-Type: application/json`
- [x] Chọn và nghe thử `speaker_id` phù hợp (mẫu: `HN-Nam-1-BL` — giọng Hà Nội) — dùng làm mặc định trong config, **chưa nghe thử thật** (cần Blaze API token thật)
- [x] Xử lý response trả về audio — hỗ trợ cả hai khả năng (binary theo `Content-Type: audio/*`, hoặc JSON base64), quyết định dựa vào response header; **chưa xác minh được với API thật** (cần token thật để test tích hợp, ghi rõ trong docstring `blaze_provider.py`)
- [x] Lưu audio kết quả vào Redis với TTL ngắn, phục vụ endpoint tải về (`app/services/tts_cache_service.py`, TTL mặc định 300s)

> **Lược bỏ khỏi MVP:** TTS real-time (WebSocket) — dùng batch (H2) làm mặc định và duy nhất, vì đọc lại tại quầy không yêu cầu độ trễ thấp như hội thoại.

### H3. Nội dung đọc lại

- [x] Viết hàm dựng nội dung đọc lại từ `readback_template` của catalog và giá trị đã xác nhận (`app/tts/readback.py`)
- [x] Che số CCCD trong nội dung gửi tới TTS (chỉ đọc 4 số cuối)
- [x] Đọc số điện thoại thành từng chữ số để người nghe dễ kiểm tra
- [x] Định dạng ngày tháng thành dạng đọc tự nhiên ("ngày mùng 5 tháng 3 năm 2026")
- [x] Fallback khi TTS lỗi: trả về văn bản để frontend hiển thị cỡ chữ lớn (`build_fallback_text`, dùng chung logic định dạng với bản đọc)

- [x] Bộ test `tests/tts/` (22 test) + `tests/services/test_tts_cache_service.py` (4 test): mock provider, factory, Blaze provider (mock hóa `httpx.AsyncClient` — cả 2 dạng response, lỗi mạng/API), readback (định dạng ngày/điện thoại/che CCCD, placeholder khi thiếu giá trị, fallback khớp nội dung đọc), TTS cache (lưu/lấy lại theo TTL)

---

## I. Service điều phối

### I1. SessionService

- [x] `create_session(staff_name, parent_session_id, mode)` — **tạo phiên mới**, ghi audit
- [x] `get_session_state(session_id)` — trả trạng thái đầy đủ gồm mọi trường và cảnh báo
- [x] `record_consent(session_id, consented)` — ghi nhận đồng ý của người dân
- [x] `select_procedure(session_id, code)` — kiểm tra catalog, khởi tạo `field_states` rỗng cho mọi trường
- [x] `cancel_session(session_id, reason)`
- [x] `complete_session(session_id, dossier_code)` — **kết thúc phiên**, kiểm tra đã có xác nhận của người dân
- [x] Kế thừa dữ liệu từ phiên cha (UC3) — chỉ các trường trong danh sách trắng

> **Hiện thực (30/8/2026):** `app/services/session_service.py` — `SessionService`
> + `SessionStateSnapshot` (gồm cảnh báo tính lại từ `FieldState` mỗi lần gọi,
> không lưu DB) + `SessionNotFound`. Chuyển trạng thái đi qua
> `transition()` (C1) thay vì tự kiểm tra điều kiện — "đã có xác nhận của
> người dân" trước `complete_session` được biểu diễn tự nhiên bằng việc chỉ
> `CITIZEN_CONFIRMED` mới có cạnh `COMPLETE` hợp lệ. Whitelist kế thừa
> (`INHERITABLE_FIELDS`) theo đúng Mục UC3 của Plan, kế thừa vào
> `suggested_value`/`suggested_by="parent_session"`, không tự `is_confirmed`.
> Test: `tests/services/test_session_service.py` (14 test).

### I2. ExtractionService

- [x] `extract(session_id, include_turns, only_missing)` — điều phối toàn bộ luồng
- [x] Bước 1: gom transcript từ các lượt đã chọn theo lựa chọn của cán bộ (`include_turns`) — không có bước lọc tự động theo chất lượng
- [x] Bước 2: lấy field schema từ catalog
- [x] Bước 3: che dữ liệu nhạy cảm
- [x] Bước 4: gọi LLM provider
- [x] Bước 5: parse và validate schema
- [x] Bước 6: kiểm chứng nguồn gốc
- [x] Bước 7: khôi phục giá trị đã che
- [x] Bước 8: chạy validator từng trường
- [x] Bước 9: gộp với trạng thái hiện có theo quy tắc merge
- [x] Bước 10: sinh cảnh báo và câu hỏi gợi ý
- [x] Bước 11: lưu `extractions` và cập nhật `field_states`, ghi `field_history`
- [x] Bước 12: ghi audit
- [x] Kiểm tra giới hạn `max_extractions_per_session`
- [x] Xử lý lỗi ở mọi bước, không để dữ liệu rác lọt lên UI
- [x] `amend_field(session_id, field_name, transcript)` — trích xuất một trường (UC4)

> **Hiện thực (30/8/2026):** `app/services/extraction_service.py` —
> `ExtractionService` (12 bước ở `_run_llm_and_save`, dùng chung cho
> `extract()` và `amend_field()`) + `ExtractionOutcome` +
> `SessionNotFoundForExtraction` + `ExtractionLimitExceeded`. Bước 9 (merge)
> dùng `app/domain/merge.py` — module logic thuần **mới** theo Mục 7.1 của
> Plan (không nằm trong danh sách rút gọn ban đầu của C, nhưng là điều kiện
> cần cho I2 nên thêm cùng khuôn mẫu, test riêng `tests/domain/test_merge.py`,
> 9 test). "Câu hỏi gợi ý" (Bước 10, phần `spoken_hint`) chưa hiện thực ở
> tầng service này — thuộc phạm vi hiển thị của frontend (M/O), service chỉ
> trả `warnings` (đã có `field` để tầng UI tự tra `spoken_hint` từ catalog).
> Redactor (F4) tạo mới mỗi lần gọi (không giữ theo phiên) vì chỉ cần sống
> trong phạm vi redact→restore của một lượt gọi. Câu hỏi kỹ thuật phát sinh:
> catalog thật (D1) tham chiếu 4 validator chưa có trong C2 bản rút gọn — đã
> hỏi user, xem ghi chú ở mục C2. Test: `tests/services/test_extraction_service.py`
> (12 test).

### I3. FieldService

- [x] `confirm_field(session_id, field_name, value, staff_name)` — lưu giá trị chốt
- [x] Đánh dấu `was_edited=true` khi giá trị khác gợi ý AI
- [x] Ghi `field_history` với `change_source` phù hợp
- [x] Kiểm tra và tự động chuyển trạng thái sang `FIELDS_CONFIRMED` khi đủ trường bắt buộc
- [x] `unconfirm_field(session_id, field_name)` — bỏ xác nhận, dùng khi người dân yêu cầu sửa
- [x] `get_fields(session_id)` — trả trạng thái mọi trường kèm kết quả validate

> **Hiện thực (30/8/2026):** `app/services/field_service.py` — `FieldService`
> + `FieldWithValidation` + `SessionNotFoundForField` + `FieldNotFound`.
> `was_edited` so với `suggested_value` (gợi ý AI), không so với lần xác nhận
> trước — đúng ý nghĩa "cán bộ có tin gợi ý AI không". Tự động chuyển
> `FIELDS_CONFIRMED` chỉ áp dụng khi phiên đang ở `REVIEWING` (tránh nhảy
> trạng thái ngoài ý muốn nếu gọi `confirm_field` ở trạng thái khác).
> `unconfirm_field` giữ nguyên `confirmed_value`, chỉ tắt `is_confirmed`
> (không xóa dữ liệu, cùng tinh thần quy tắc merge Mục 7.1/I2).
> Test: `tests/services/test_field_service.py` (11 test).

### I4. VoiceService

- [x] `start_recording(session_id)` — **bấm nút hỏi**: tạo lượt thoại mới, cấp `turn_number`
- [x] `process_audio_chunk(session_id, chunk)` — đẩy tới STT, trả kết quả từng phần
- [x] `finalize_turn(session_id, transcript)` — lưu vào `voice_turns`
- [x] `delete_audio_buffer(session_id, turn_id)` — xóa khỏi Redis, ghi `audio_deleted_at`
- [x] `edit_transcript(session_id, turn_id, new_text, staff_name)` — cán bộ sửa (UC5)
- [x] `flag_transcript(session_id, turn_id, staff_name)` — cán bộ chủ động gắn cờ "chưa rõ", ghi audit `transcript_flagged_by_staff`

> **Hiện thực (30/8/2026):** `app/services/voice_service.py` — `VoiceService`
> + `SessionNotFoundForVoice` + `VoiceTurnNotFound`. Vấn đề kỹ thuật đã hỏi
> người dùng: `STTProvider.transcribe_stream()` (G1) nhận một
> `AsyncIterator[bytes]` — một luồng hoàn chỉnh — trong khi
> `process_audio_chunk()` theo Checklist phải nhận audio đẩy tới theo từng
> chunk rời rạc qua nhiều lần gọi (khớp với cách tầng K/WebSocket sẽ dùng
> thật). Hai giao diện không khớp trực tiếp; người dùng chọn phương án
> **dùng `asyncio.Queue` làm cầu nối (Recommended)**: mỗi lượt đang ghi âm
> có một `asyncio.Queue[bytes | None]` riêng + một task nền
> (`_consume_stream`) đọc queue như `AsyncIterator[bytes]` để đưa vào
> `transcribe_stream()`, gom `TranscriptChunk` (partial/final) vào
> `_ActiveTurn.results`; tầng gọi đọc kết quả gom được qua
> `get_partial_results(turn_id)` (không trả trực tiếp từ
> `process_audio_chunk()` vì STT chạy độc lập trong task nền). `None` trong
> queue là tín hiệu kết thúc luồng — `finalize_turn()` đẩy `None` rồi `await`
> task nền trước khi dọn `_active_turns`.
> `process_audio_chunk()` vừa đẩy chunk vào queue vừa `rpush` + `expire` vào
> Redis (`audio_buffer:{turn_id}`, TTL `audio_buffer_ttl_seconds` mặc định
> 120s — Mục 8.4/NT-6 của Plan.MD). `delete_audio_buffer()` xóa key Redis và
> ghi `audio_deleted_at` làm bằng chứng tường minh, tách biệt với việc dựa
> vào TTL tự hết hạn. `flag_transcript()` dùng
> `AuditAction.TRANSCRIPT_FLAGGED_BY_STAFF` (đã bổ sung enum ở
> `app/domain/audit_action.py`, cập nhật test
> `tests/domain/test_audit_action.py` từ 7 lên 8 giá trị). Các action audit
> khác (`recording_started`, `transcript_received`, `audio_buffer_deleted`,
> `transcript_edited_by_staff`) dùng chuỗi trực tiếp theo đúng tên liệt kê ở
> Mục 8.3 của Plan.MD (dòng 813) — không đưa vào `AuditAction` enum vì bản
> rút gọn C2/E chỉ giữ action của luồng chính; có thể bổ sung sau nếu cần
> kiểm tra tường minh bằng enum.
> Thêm `VoiceTurnRepository.update()` (flush thay đổi trong transaction hiện
> tại) — trước đó repository chỉ có `add`/`get`/`list_by_session`, chưa có
> chỗ ghi thay đổi (`raw_transcript`, `edited_transcript`,
> `flagged_by_staff`, `audio_deleted_at`) sau khi tạo.
> Test: `tests/services/test_voice_service.py` (16 test) — dùng
> `_EchoSTTProvider` (fake, trả partial theo từng chunk + 1 final khi luồng
> kết thúc) và `AsyncMock` cho Redis client (cùng kỹ thuật đã dùng ở
> `test_tts_cache_service.py`).
>
> **Bổ sung (30/8/2026, khi làm K):** thêm `stream_results(turn_id)` +
> `_ActiveTurn.results_queue` (`asyncio.Queue[TranscriptChunk | None]`) —
> vấn đề kỹ thuật đã hỏi người dùng: WebSocket (K) cần đẩy `partial`/`final`
> về client NGAY khi STT trả về, nhưng `get_partial_results()` chỉ đọc
> snapshot list `results` (polling, không real-time). Người dùng chọn
> **thêm callback/queue kết quả vào VoiceService (Recommended)**:
> `_consume_stream()` giờ vừa append vào `results` (giữ nguyên cho polling)
> vừa `put()` ngay vào `results_queue` riêng; `stream_results()` bọc queue
> đó thành `AsyncIterator[TranscriptChunk]` để WebSocket `async for` trực
> tiếp. `None` đẩy vào `results_queue` khi `transcribe_stream()` kết thúc
> tự nhiên, để vòng lặp `async for` dừng đúng lúc.
>
> **Sửa lỗi (30/8/2026, khi làm K):** phát hiện race condition thật —
> `stop` phải đọc text cuối TRƯỚC hay SAU khi đóng luồng audio? Chunk
> `is_final` chỉ phát sinh SAU khi luồng audio đóng (STT cần nhận hết audio
> mới trả kết quả cuối), nên đọc `get_partial_results()` trước khi đóng
> luồng có nguy cơ thiếu chunk cuối. Đã hỏi người dùng, chọn **thêm
> `close_recording_stream()` riêng, tầng gọi tự ghép text (Recommended)**:
> tách `finalize_turn(turn_id, transcript)` thành 2 bước — method mới
> `close_recording_stream(turn_id)` chỉ đóng queue + đợi task nền + trả kết
> quả gom được đầy đủ (an toàn gọi nhiều lần/turn không active, trả `[]`);
> `finalize_turn()` giờ chỉ lưu DB (gọi `close_recording_stream()` bên trong
> để tương thích ngược nếu tầng gọi chưa tự đóng trước). K gọi
> `close_recording_stream()` trước, tự ghép text cuối, rồi mới gọi
> `finalize_turn()`. Test bổ sung:
> `test_close_recording_stream_returns_final_chunk_before_finalize`,
> `test_close_recording_stream_unknown_turn_returns_empty` (18 test tổng).

### I5. ReadbackService

- [x] `generate_readback(session_id)` — dựng nội dung từ template và giá trị đã xác nhận
- [x] Gọi TTS sinh audio, xử lý fallback sang văn bản khi lỗi
- [x] Tăng `readback_round` mỗi lần đọc lại
- [x] `record_citizen_confirmation(session_id, confirmed, note)` — lưu xác nhận hoặc từ chối
- [x] Khi người dân từ chối: chuyển phiên về `REVIEWING`, ghi audit

> **Hiện thực (30/8/2026):** `app/services/readback_service.py` —
> `ReadbackService` + `ReadbackOutcome` + `SessionNotFoundForReadback` +
> `NoProcedureSelected`. Tái dùng `build_readback_text()`/`build_fallback_text()`
> (H3, đã có sẵn — định dạng ngày/điện thoại tự nhiên, che CCCD) và
> `TTSProvider.synthesize()` (H1); không viết lại logic định dạng/che dữ liệu.
> `generate_readback()` chuyển `FIELDS_CONFIRMED` → `READBACK` qua
> `transition()` (C1), tính `readback_round` kế tiếp qua
> `CitizenConfirmationRepository.next_readback_round()`, gọi TTS — bắt
> `TTSError` để suy giảm mềm sang trả về văn bản fallback (NT-2, không ném
> lỗi ra ngoài). Cố ý **không** tạo bản ghi `CitizenConfirmation` ở bước này:
> cột `confirmed` của bảng là `BOOLEAN NOT NULL`, không có trạng thái "đang
> chờ", nên bản ghi chỉ được tạo tại `record_citizen_confirmation()` khi đã
> biết kết quả thật.
> `record_citizen_confirmation()` lưu `CitizenConfirmation` mới, chuyển
> `READBACK` → `CITIZEN_CONFIRMED` (xác nhận) hoặc → `REVIEWING` (từ chối,
> UC4) qua `transition()`, ghi audit `citizen_confirmed`/`citizen_rejected`
> tương ứng.
> Thêm mới `app/repositories/citizen_confirmation_repository.py` —
> `CitizenConfirmationRepository` (`next_readback_round`, `add`,
> `list_by_session`, `get_latest`) — chưa tồn tại trước I5.
> Các audit action (`readback_played`, `citizen_confirmed`,
> `citizen_rejected`) dùng chuỗi trực tiếp theo đúng tên liệt kê ở Mục 8.3
> của Plan.MD (dòng 816), cùng cách xử lý như các action ngoài luồng chính
> đã làm ở I4 — không đưa vào `AuditAction` enum rút gọn.
> Test: `tests/services/test_readback_service.py` (12 test) — dùng
> `_StubTTSProvider` (thành công/lỗi có kiểm soát) và catalog thật
> `dang_ky_khai_sinh` với kỹ thuật `_FixedDate` (đã dùng nhất quán từ I1).
> Bao gồm: sinh audio + chuyển trạng thái, định dạng ngày sinh đọc tự nhiên,
> fallback văn bản khi TTS lỗi, phiên/thủ tục không tồn tại, chuyển trạng
> thái sai gọi từ trạng thái không hợp lệ ném `InvalidTransitionError`, xác
> nhận/từ chối của người dân, và tăng `readback_round` qua nhiều vòng.

---

## J. API endpoints

> Không có middleware xác thực/JWT ở MVP này — xem [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp). Toàn bộ endpoint dùng trực tiếp trong mạng nội bộ điểm hỗ trợ.

### J1. Danh mục thủ tục

- [x] `GET /api/v1/procedures` — danh sách thủ tục đang hiệu lực
- [x] `GET /api/v1/procedures/{code}` — chi tiết gồm field schema và thành phần hồ sơ

### J2. Quản lý phiên

- [x] `POST /api/v1/sessions` — **tạo phiên mới**
- [x] `GET /api/v1/sessions/{id}` — trạng thái đầy đủ
- [x] `GET /api/v1/sessions` — danh sách phiên gần đây, có phân trang
- [x] `POST /api/v1/sessions/{id}/consent` — ghi nhận đồng ý của người dân
- [x] `POST /api/v1/sessions/{id}/procedure` — chọn thủ tục
- [x] `POST /api/v1/sessions/{id}/cancel` — hủy phiên
- [x] `POST /api/v1/sessions/{id}/complete` — **kết thúc phiên** với mã hồ sơ

### J3. Lượt thoại

- [x] `GET /api/v1/sessions/{id}/turns` — danh sách lượt thoại
- [x] `PATCH /api/v1/sessions/{id}/turns/{turn_id}` — cán bộ sửa transcript

### J4. Trích xuất

- [x] `POST /api/v1/sessions/{id}/extract` — gọi LLM trích xuất
- [x] `GET /api/v1/sessions/{id}/extractions` — lịch sử các lần trích xuất

### J5. Trường dữ liệu

- [x] `GET /api/v1/sessions/{id}/fields` — trạng thái mọi trường
- [x] `POST /api/v1/sessions/{id}/fields/{name}/confirm` — xác nhận một trường
- [x] `POST /api/v1/sessions/{id}/fields/{name}/unconfirm` — bỏ xác nhận
- [x] `POST /api/v1/sessions/{id}/fields/{name}/amend` — sửa một trường bằng giọng nói
- [x] Khẳng định trong test: **không tồn tại** endpoint xác nhận hàng loạt

### J6. Đọc lại và xác nhận

- [x] `POST /api/v1/sessions/{id}/readback` — sinh nội dung và audio
- [x] `GET /api/v1/sessions/{id}/readback/audio` — tải audio TTS
- [x] `POST /api/v1/sessions/{id}/citizen-confirm` — ghi nhận xác nhận của người dân

### J7. Chuẩn chung cho mọi endpoint

- [x] Khai báo response model bằng Pydantic cho mọi endpoint
- [ ] Khai báo mã lỗi có thể trả về trong OpenAPI — **chưa làm**, xem ghi chú dưới
- [ ] Hỗ trợ header `Idempotency-Key` cho `confirm`, `complete`, `citizen-confirm` — **lược bỏ theo quyết định người dùng**, xem ghi chú
- [x] Ghi audit cho mọi thao tác thay đổi dữ liệu (đã có sẵn ở tầng service I1-I5, router chỉ gọi qua)

> **Hiện thực (30/8/2026):** Toàn bộ 22 endpoint J1-J6 — `app/api/deps.py`
> (dependency injection tập trung: mỗi `get_*_service` dựng service từ
> `Depends(get_db)` + catalog/provider AI cache qua `lru_cache`, để test có
> thể `app.dependency_overrides[...]`), `app/api/schemas.py` (Pydantic
> response/request model riêng — không serialize thẳng ORM object),
> `app/api/routers/{procedures,sessions,turns,extraction,fields,readback}.py`,
> wire vào `app/main.py` (lifespan dọn dẹp engine/pool lúc tắt, `/health`
> gọi `health_check()` thật của DB/Redis/LLM/STT/TTS, exception handler
> `ExtractionLimitExceeded` → 429 và `DomainError` chung → 404 nếu tên lớp
> chứa "NotFound" còn lại → 409).
> Mỗi router `flush()` qua service rồi tự `db.commit()` — service (I1-I5)
> chỉ `flush()`, không tự commit; một request HTTP = một transaction trọn vẹn.
> Thêm `pyproject.toml`: `ignore = ["B008"]` cho ruff — `Depends(...)` làm giá
> trị mặc định tham số là idiom chuẩn FastAPI, không phải lỗi.
> Bổ sung `TTSCacheService.store_for_session()`/`retrieve_for_session()` (H2)
> — key Redis cố định theo `session_id` (không phải UUID ngẫu nhiên như
> `store()`) để `GET /readback/audio` tải lại đúng audio vừa sinh;
> `ReadbackService` (I5) cập nhật nhận thêm `tts_cache_service`, lưu audio
> ngay sau khi TTS thành công.
> **J7 lược bỏ theo quyết định người dùng:** cơ chế `Idempotency-Key` chưa
> hiện thực ở MVP này — mỗi endpoint `confirm`/`complete`/`citizen-confirm`
> chỉ ghi TODO tham chiếu mục này trong docstring, tập trung nguồn lực cho
> phần còn lại của J trước. Khai báo mã lỗi trong OpenAPI (`responses=` của
> từng route) cũng chưa làm — có thể bổ sung sau, không chặn phần K trở đi.
>
> **Khoảng trống thiết kế đã phát hiện (chưa sửa theo quyết định người
> dùng — "cách ít tốn kém nhất"):** bảng chuyển trạng thái (C1) có các cạnh
> `start_listening` (CREATED→LISTENING),
> `request_extraction`/`extraction_success`/`extraction_failed`
> (PROCEDURE_SELECTED→EXTRACTING→SUGGESTED/AI_UNAVAILABLE), `open_review`
> (SUGGESTED→REVIEWING), `manual_entry` (AI_UNAVAILABLE→REVIEWING),
> `ask_again` (REVIEWING→LISTENING) mà **không service hay endpoint nào**
> (I1-I5, J1-J6) hiện gọi tới — `ExtractionService.extract()` không đụng
> `session.state` dù trích xuất thành công/thất bại, và J2 không có endpoint
> tương ứng cho `start_listening`/`open_review`/`manual_entry`/`ask_again`.
> Nghĩa là luồng CREATED → COMPLETED không thể đi hết bằng cách chỉ gọi API
> — cần set thẳng `session.state` qua DB ở các bước đó (đã làm trong test
> E2E, xem `tests/api/test_e2e_flow.py`). Đây là việc còn thiếu thật sự,
> để dành sửa sau (có thể ở một mục riêng khi rà lại toàn bộ luồng, không
> thuộc phạm vi J) — không tự sửa ở đây vì sẽ phải động vào
> `ExtractionService` (I2, đã hoàn thiện + test kỹ) chỉ để phục vụ một
> thay đổi ngoài yêu cầu ban đầu của J.
>
> Test: `tests/api/conftest.py` (fixture `client` — `httpx.AsyncClient` +
> `ASGITransport` gọi thẳng app, override `get_db`/`get_redis`/
> `get_catalog_service`; Redis giả lập bằng `dict` trong bộ nhớ để
> `set`/`get`/`delete` hoạt động thật giữa nhiều lệnh gọi trong cùng test).
> **Phạm vi test có chủ đích hẹp** (quyết định người dùng: không lặp lại
> từng nhánh nghiệp vụ đã test kỹ ở I1-I5) — `tests/api/test_e2e_flow.py`
> chỉ 2 test: một luồng tích hợp duy nhất đi hết J1→J6 theo đúng thứ tự
> B1-B7 của Plan.MD (xác nhận các router nối đúng với nhau qua HTTP, đúng
> response_model, đúng mã lỗi domain → HTTP 404/409), và một smoke test
> riêng cho `GET /fields` (kết quả validate hiển thị đúng).

---

## K. WebSocket giọng nói

- [x] Viết endpoint `WS /api/v1/sessions/{id}/voice`
- [x] Xử lý message `start` — **bấm nút hỏi**: khởi tạo lượt thoại, mở kết nối tới STT
- [x] Xử lý message `audio` — kiểm tra kích thước chunk, đẩy tới STT
- [x] Xử lý message `stop` — chốt transcript, lưu DB, xóa audio buffer
- [x] Gửi message `partial` khi có kết quả từng phần
- [x] Gửi message `final` khi chốt một lượt
- [x] Gửi message `error` khi STT lỗi
- [x] Gửi message `audio_deleted` xác nhận đã xóa buffer
- [x] Xử lý ngắt kết nối đột ngột — dọn dẹp buffer, ghi audit
- [x] Giới hạn thời lượng ghi âm, tự động dừng khi vượt

> **Hiện thực (30/8/2026):** `app/api/routers/voice.py` — một endpoint
> `@router.websocket("/api/v1/sessions/{session_id}/voice")`, giao thức
> đúng Mục 9.2 của Plan.MD (dòng 982-997): nhận `start`/`audio`/`stop`, gửi
> `partial`/`final`/`error`/`audio_deleted`.
> Kiến trúc: một task nền (`_forward_results`) `async for` trực tiếp
> `VoiceService.stream_results(turn_id)` (I4, bổ sung khi làm K — xem ghi
> chú ở mục I4) để đẩy `partial`/`final` về client ngay khi STT trả về,
> chạy song song với vòng lặp chính nhận message JSON từ client — cần thiết
> vì STT trả kết quả không đồng bộ với nhịp client gửi chunk.
> `audio`: giải mã base64, chặn payload giải mã vượt `_MAX_CHUNK_BYTES`
> (256 KiB, tự chọn — đủ cho vài trăm ms PCM 16kHz/mono/16-bit, chưa có
> setting riêng trong `Settings` cho giới hạn này) trả lỗi
> `CHUNK_TOO_LARGE` (L2).
> `stop`: gọi `close_recording_stream()` (I4, method mới tách ra để tránh
> race condition — xem ghi chú mục I4) lấy kết quả cuối, ghép text final,
> `finalize_turn()` lưu DB, đợi `_forward_results` kết thúc (timeout 5s,
> hủy nếu quá), rồi `delete_audio_buffer()` và gửi `audio_deleted`.
> Giới hạn thời lượng ghi âm: `recording_deadline` tính từ lúc `start`
> (`asyncio.get_event_loop().time() + settings.max_recording_seconds`),
> vòng lặp chính `asyncio.wait_for(websocket.receive_json(), timeout=...)`
> với timeout còn lại tới deadline — hết giờ tự động chạy lại logic `stop`
> rồi gửi `error` code `RECORDING_TIMEOUT`, không đóng kết nối (cán bộ ghi
> âm lượt kế tiếp bình thường).
> Ngắt kết nối đột ngột: bắt `WebSocketDisconnect`, hủy task nền, gọi
> `delete_audio_buffer()` (bỏ qua `VoiceTurnNotFound` nếu turn chưa từng
> tồn tại), ghi log `warning` — không có message `stop` từ client nên
> không gọi `finalize_turn()` (transcript coi như chưa hoàn tất, giữ
> `raw_transcript=None`).
> Test: `tests/api/test_voice_websocket.py` (1 test, cùng phạm vi hẹp có
> chủ đích như J — dùng `MockSTTProvider`, override `get_stt_provider`) —
> một luồng `start` → `audio` → `stop` xác nhận đúng message `final` +
> `audio_deleted`. `tests/api/conftest.py` bổ sung `rpush`/`expire` vào
> Redis giả lập (`redis_mock`) — cần cho `process_audio_chunk()`.

---

## L. Độ tin cậy và xử lý lỗi tối thiểu

### L1. Suy giảm mềm (bắt buộc — đây là nguyên tắc lõi NT-8)

- [x] LLM lỗi → chuyển phiên sang `AI_UNAVAILABLE`, cho phép nhập tay — **Hiện thực (30/8/2026)**:
      phát hiện khoảng trống đã ghi nhận từ phần J (không service nào từng gọi
      `transition()` với `REQUEST_EXTRACTION`/`EXTRACTION_SUCCESS`/`EXTRACTION_FAILED`
      — session không bao giờ thực sự vào `EXTRACTING`). Vì đây là yêu cầu bắt buộc
      (không thể lược bỏ như đã làm tạm thời ở J), đã sửa `ExtractionService.extract()`
      để tự điều khiển state machine đúng chuẩn C1: gọi `REQUEST_EXTRACTION` (→
      `EXTRACTING`) trước khi gọi LLM, rồi `EXTRACTION_SUCCESS` (→ `SUGGESTED`) hoặc
      `EXTRACTION_FAILED` (→ `AI_UNAVAILABLE`, chỉ khi `status == "api_error"` —
      **không** áp dụng cho `parse_failed`, quyết định của người dùng vì JSON sai định
      dạng không phải lỗi hạ tầng AI) sau đó. Thêm helper `_advance_state()` khoan dung
      có chủ đích: nếu `event` không hợp lệ từ trạng thái hiện tại (ví dụ trích xuất lại
      khi phiên đã ở `SUGGESTED`/`REVIEWING` — luồng "trích xuất lại" chưa được mô hình
      hóa trong bảng chuyển đổi C1), bỏ qua và giữ nguyên state thay vì ném lỗi làm hỏng
      luồng nghiệp vụ hợp lệ khác. `amend_field()` (UC4 — sửa một trường) **không** đổi
      state cả phiên (tham số `advance_state=False` khi gọi `_run_llm_and_save()`) — sửa
      một trường không nên lùi cả phiên về `AI_UNAVAILABLE`/`SUGGESTED`. 5 test mới trong
      `tests/services/test_extraction_service.py` (api_error → `AI_UNAVAILABLE`, success →
      `SUGGESTED`, parse_failed → giữ nguyên, amend_field lỗi → giữ nguyên, luồng thật từ
      `PROCEDURE_SELECTED`).
- [x] STT lỗi → cho phép cán bộ gõ transcript trực tiếp — **Hiện thực (30/8/2026)**: đã
      thỏa mãn từ phần J/K, không cần code mới. `PATCH /sessions/{id}/turns/{turn_id}`
      ([turns.py](app/api/routers/turns.py)) gọi `VoiceService.edit_transcript()` không
      điều kiện tiên quyết nào — cán bộ luôn có thể ghi đè `raw_transcript` bằng tay. Khi
      STT lỗi giữa chừng lúc ghi âm qua WebSocket, handler `audio` bắt `STTError` và gửi
      message `{"type": "error", "code": "STT_UNAVAILABLE"}` **không đóng kết nối** — cán
      bộ bấm `stop` (transcript rỗng/thiếu vẫn được lưu) rồi sửa tay qua `PATCH` như trên.
- [x] TTS lỗi → trả văn bản để hiển thị — **Hiện thực (30/8/2026)**: đã thỏa mãn từ phần
      I5, không cần code mới. `ReadbackService.generate_readback()`
      ([readback_service.py](app/services/readback_service.py)) bắt `TTSError`, đặt
      `used_fallback=True`, và trả `build_fallback_text()` (văn bản đọc lại ghép từ
      template + giá trị đã xác nhận) thay vì audio — cán bộ hiển thị text này lên màn
      hình cho người dân đọc thay vì nghe.
- [x] Redis lỗi → chuyển sang lưu trạng thái phiên trong PostgreSQL — **Hiện thực
      (30/8/2026)**: đã thỏa mãn sẵn theo thiết kế hiện tại, khác Plan.MD Mục 13.1 (dự
      tính Redis là nơi lưu trạng thái phiên chính, PostgreSQL chỉ là fallback) — kiến
      trúc thực tế (từ phần C/I1) đặt `Session.state` trực tiếp trong PostgreSQL **ngay
      từ đầu**, không có tầng cache Redis nào phía trước. Redis chỉ dùng cho hai loại dữ
      liệu vốn đã tạm thời/không phải nguồn sự thật: audio buffer khi ghi âm (TTL 120s,
      [voice_service.py](app/services/voice_service.py)) và cache audio TTS
      ([tts_cache_service.py](app/services/tts_cache_service.py)) — Redis lỗi ở hai chỗ
      này không làm mất trạng thái nghiệp vụ, chỉ mất dữ liệu tạm (audio chưa transcript
      xong, hoặc cache TTS phải sinh lại). Quyết định của người dùng: không cần thêm
      try/except quanh các lệnh gọi Redis trong `voice_service`/`tts_cache_service` cho
      MVP — khác Plan.MD nhưng an toàn hơn (không có single point of failure nào phụ
      thuộc Redis cho state).

### L2. Giới hạn cơ bản

- [x] Giới hạn số lần extraction mỗi phiên (`max_extractions_per_session`) — **Hiện thực
      (30/8/2026)**: đã có từ phần I2 — `ExtractionService` đếm `count_by_session()` so
      với `max_extractions_per_session` (mặc định 5), ném `ExtractionLimitExceeded`.
- [x] Giới hạn kích thước audio chunk — **Hiện thực (30/8/2026)**: đã có từ phần K —
      `_MAX_CHUNK_BYTES = 256 * 1024` (256 KiB) trong
      [voice.py](app/api/routers/voice.py), kiểm tra sau khi giải mã base64.
- [x] Trả HTTP 429 kèm thông báo tiếng Việt rõ ràng khi vượt giới hạn — **Hiện thực
      (30/8/2026)**: đã có từ phần J — handler `handle_extraction_limit_exceeded` trong
      [main.py](app/main.py) trả 429 với `code=EXTRACTION_LIMIT_EXCEEDED`,
      `fallback_available=True`, và thông báo tiếng Việt từ
      `ExtractionLimitExceeded.__init__()`.

> **Lược bỏ khỏi MVP:** circuit breaker nhiều trạng thái (CLOSED/OPEN/HALF_OPEN) dùng Redis chia sẻ giữa worker, giới hạn tần suất theo cán bộ/giờ — thêm khi hệ thống có nhiều người dùng đồng thời thật sự cần bảo vệ.

---

## M. Frontend — nền tảng

### M1. Khởi tạo

- [x] Khởi tạo Vite + React 18 + TypeScript trong `frontend/` — **Hiện thực (30/8/2026)**:
      `npm create vite@latest . -- --template react-ts`. React thực tế là 19.x (bản mới nhất
      của template Vite hiện hành) thay vì 18 — không có yêu cầu ràng buộc phiên bản cụ thể
      nào khác trong Plan.MD, và 19 tương thích ngược với API đã dùng (hooks, không dùng
      tính năng 18-only nào).
- [x] Cấu hình Tailwind CSS — **Hiện thực (30/8/2026)**: dùng `@tailwindcss/vite` (Tailwind
      v4, plugin Vite chính thức — không cần `tailwind.config.js`/`postcss.config.js` riêng
      như v3). [vite.config.ts](frontend/vite.config.ts), `@import "tailwindcss"` trong
      [index.css](frontend/src/index.css).
- [x] Cấu hình đường dẫn alias (`@/` → `src/`) — **Hiện thực (30/8/2026)**:
      [vite.config.ts](frontend/vite.config.ts) (`resolve.alias`) +
      [tsconfig.app.json](frontend/tsconfig.app.json) (`compilerOptions.paths`) — cả hai đều
      cần khai báo (Vite cho runtime bundling, TS cho type-check/IDE).
- [x] Cấu hình biến môi trường cho URL backend — **Hiện thực (30/8/2026)**:
      [.env.example](frontend/.env.example) — `VITE_API_BASE_URL` để trống mặc định (dùng
      qua proxy dev server), chỉ cần đặt khi frontend/backend khác origin lúc build production.
- [x] Cấu hình proxy dev server trỏ về backend — **Hiện thực (30/8/2026)**:
      [vite.config.ts](frontend/vite.config.ts) `server.proxy['/api']` → `http://localhost:8000`
      (cổng uvicorn mặc định), `ws: true` để WebSocket giọng nói (K) cũng đi qua proxy này.

### M2. Tầng API client

- [x] Viết HTTP client bọc `fetch` có xử lý lỗi thống nhất — **Hiện thực (30/8/2026)**:
      [client.ts](frontend/src/api/client.ts) — parse `ErrorResponse` của backend
      (`app/api/schemas.py`) thành `ApiError` (có `code`, `status`, `requestId`,
      `fallbackAvailable`); `fetchBlob` riêng cho audio đọc lại (không parse JSON).
- [x] Tự động sinh `X-Request-ID` — **Hiện thực (30/8/2026)**: mỗi request tạo UUID mới
      (`createRequestId()`, [client.ts](frontend/src/api/client.ts)) — khớp `request_id` mà
      backend trả trong lỗi để đối chiếu log hai phía.
- [x] Sinh type TypeScript từ OpenAPI schema của backend — **Hiện thực khác đi (30/8/2026)**:
      không chạy công cụ codegen runtime (`openapi-typescript` cần backend đang chạy để
      introspect `/openapi.json`) — thay vào đó viết tay
      [types/api.ts](frontend/src/types/api.ts) đối chiếu trực tiếp từng field với
      `app/api/schemas.py`/`app/catalog/models.py`. Ghi chú lệnh codegen thật trong comment
      đầu file nếu cần tự động hóa sau này khi có backend chạy sẵn ở CI.
- [x] Viết hàm gọi API cho từng nhóm endpoint — **Hiện thực (30/8/2026)**:
      [api/procedures.ts](frontend/src/api/procedures.ts),
      [api/sessions.ts](frontend/src/api/sessions.ts), [api/turns.ts](frontend/src/api/turns.ts)
      (kèm `flag()` — xem ghi chú backend bên dưới),
      [api/extraction.ts](frontend/src/api/extraction.ts), [api/fields.ts](frontend/src/api/fields.ts)
      (cố ý không có hàm "xác nhận tất cả", NT-1/NT-3),
      [api/readback.ts](frontend/src/api/readback.ts).
      **Phát hiện khi build frontend**: `VoiceService.flag_transcript()` (I4) đã có từ trước
      nhưng chưa có router endpoint tương ứng — bổ sung
      `POST /sessions/{id}/turns/{turn_id}/flag` ở [turns.py](app/api/routers/turns.py) +
      `FlagTranscriptRequest` ở [schemas.py](app/api/schemas.py) để O2 ("Gắn cờ chưa rõ") có
      API để gọi. Backend vẫn ruff clean, 256 test cũ pass sau khi thêm.

### M3. Quản lý trạng thái

- [x] Cài đặt state management (khuyến nghị TanStack Query cho dữ liệu server) — **Hiện thực
      (30/8/2026)**: `@tanstack/react-query`, cấu hình dùng chung ở
      [lib/queryClient.ts](frontend/src/lib/queryClient.ts) (`refetchOnWindowFocus: false` —
      cán bộ làm việc lâu trên một phiên, không muốn bị ghi đè dữ liệu đang nhập khi chuyển tab).
- [x] Viết hook `useSession(id)` — **Hiện thực (30/8/2026)**: [useSession.ts](frontend/src/hooks/useSession.ts).
- [x] Viết hook `useFields(sessionId)` — **Hiện thực (30/8/2026)**: [useFields.ts](frontend/src/hooks/useFields.ts)
      (kèm mutation `useConfirmField`/`useUnconfirmField`/`useAmendField`/`useExtract`).
- [x] Viết hook `useProcedures()` — **Hiện thực (30/8/2026)**: [useProcedures.ts](frontend/src/hooks/useProcedures.ts)
      (kèm `useProcedureDetail(code)`).
- [x] Cấu hình tự động làm mới dữ liệu phiên sau mỗi thao tác — **Hiện thực (30/8/2026)**: mọi
      mutation trong `useFields.ts`/`useSessionActions.ts`/`useTurns.ts` gọi
      `invalidateQueries` cho cả `session` lẫn `fields` khi thành công (`SessionStateSnapshot`
      chứa cả hai — làm mới một phía mà không làm mới phía kia sẽ hiển thị dữ liệu lệch nhau).

### M4. WebSocket client

- [x] Viết hook `useVoiceStream(sessionId)` — **Hiện thực (30/8/2026)**: [useVoiceStream.ts](frontend/src/hooks/useVoiceStream.ts).
- [x] Xin quyền truy cập micro của trình duyệt — **Hiện thực (30/8/2026)**:
      `navigator.mediaDevices.getUserMedia` trong [audioCapture.ts](frontend/src/lib/audioCapture.ts).
- [x] Ghi âm bằng `AudioWorklet` — **Hiện thực (30/8/2026)**:
      [public/pcm-worklet.js](frontend/public/pcm-worklet.js) (chạy trên audio thread, gửi
      Float32 block về main thread) + [audioCapture.ts](frontend/src/lib/audioCapture.ts)
      (resample về 16kHz bằng linear interpolation — đủ tốt cho giọng nói ở MVP, không cần bộ
      lọc chống alias phức tạp — rồi encode Int16 PCM, base64).
- [x] Gửi audio chunk nhị phân qua WebSocket — **Hiện thực (30/8/2026)**: mỗi block
      `AudioWorklet` (128 sample ở sample rate gốc thiết bị, resample xuống ~ tương ứng ở
      16kHz) gửi ngay dưới dạng `{"type": "audio", "data": "<base64>"}` — không gộp thêm
      thành lô lớn hơn ở MVP, đơn giản hơn và độ trễ thấp hơn là gộp buffer.
- [x] Nhận và hiển thị transcript từng phần theo thời gian thực — **Hiện thực (30/8/2026)**:
      xử lý message `partial`/`final` trong `useVoiceStream`, hiển thị ở
      [TranscriptList.tsx](frontend/src/components/TranscriptList.tsx).
- [x] Xử lý mất kết nối, tự động kết nối lại — **Hiện thực (30/8/2026)**: `ws.onclose` tự gọi
      lại `connect` (qua `connectRef`, tránh vấn đề tự tham chiếu biến đang khởi tạo) tối đa 3
      lần với backoff tuyến tính (1s, 2s, 3s), báo lỗi rõ ràng nếu vẫn thất bại.
- [x] Hiển thị mức âm lượng đầu vào — **Hiện thực (30/8/2026)**: RMS tính trong worklet
      callback, đọc qua `getVolumeLevel()`, hiển thị bằng box-shadow động ở
      [RecordButton.tsx](frontend/src/components/RecordButton.tsx).
- [x] Dừng ghi âm tự động khi vượt giới hạn thời lượng — **Hiện thực (30/8/2026)**: backend đã
      tự chốt lượt và gửi `{"type": "error", "code": "RECORDING_TIMEOUT"}` (K) — frontend nhận
      message này, dọn audio capture, quay về `idle` (không cần tự đếm giờ phía client để trùng
      lặp logic).

---

## N. Frontend — màn hình

- [x] **Bảng điều khiển** `/` — **Hiện thực (30/8/2026)**: [DashboardPage.tsx](frontend/src/pages/DashboardPage.tsx).
- [x] **Tạo phiên** `/sessions/new` — **Hiện thực (30/8/2026)**: [NewSessionPage.tsx](frontend/src/pages/NewSessionPage.tsx)
      — tạo phiên rồi gọi `POST /consent` ngay trong cùng thao tác gửi form (hai lời gọi API
      tách biệt ở backend, J2).
- [x] **Màn hình làm việc** `/sessions/:id` — **Hiện thực (30/8/2026)**: [WorkspacePage.tsx](frontend/src/pages/WorkspacePage.tsx)
      — bố cục 2 cột đúng Plan.MD Mục 11.1 (trái: transcript + ghi âm + checklist hồ sơ; phải:
      trường dữ liệu + cảnh báo + tiến độ + nút đọc lại), áp dụng đủ 10 quy tắc GD-1..GD-10
      (Mục 11.2) bao gồm nút "Chép" mỗi trường (GD-4) và banner cố định chân trang (GD-7, xem
      [ResponsibilityBanner.tsx](frontend/src/components/ResponsibilityBanner.tsx)). Hiện màn
      hình chọn thủ tục lồng bên trong khi `session.procedure_code === null` thay vì một route
      riêng — Checklist N không liệt kê `/sessions/:id/procedure` như một màn hình độc lập.
- [x] **Đọc lại** `/sessions/:id/readback` — **Hiện thực (30/8/2026)**: [ReadbackPage.tsx](frontend/src/pages/ReadbackPage.tsx)
      — tự gọi `POST /readback` khi vào trang, phát audio nếu có, hiện text + cảnh báo rõ ràng
      khi `used_fallback` (TTS lỗi, L1), hai nút xác nhận/từ chối gọi `POST /citizen-confirm`.
- [x] **Hoàn tất** `/sessions/:id/complete` — **Hiện thực (30/8/2026)**: [CompletePage.tsx](frontend/src/pages/CompletePage.tsx).
- [x] Màn hình 404 và màn hình lỗi chung — **Hiện thực (30/8/2026)**: [NotFoundPage.tsx](frontend/src/pages/NotFoundPage.tsx),
      [ErrorPage.tsx](frontend/src/pages/ErrorPage.tsx) + [ErrorBoundary.tsx](frontend/src/components/ErrorBoundary.tsx)
      bọc toàn bộ `<App>` để bắt lỗi runtime React chưa xử lý thay vì màn hình trắng.

> **Lược bỏ khỏi MVP:** `/login`, `/audit`, `/audit/:sessionId`, `/stats`, `/admin/users` và router bảo vệ theo vai trò — xem [Đã lược bỏ khỏi MVP](#đã-lược-bỏ-khỏi-mvp).

---

## O. Frontend — component nghiệp vụ

### O1. Component ghi âm (nút hỏi)

- [x] Nút ghi âm lớn, trạng thái rõ ràng — **Hiện thực (30/8/2026)**: [RecordButton.tsx](frontend/src/components/RecordButton.tsx)
      (5 trạng thái: idle/connecting/recording/processing/error, nhãn tiếng Việt cho từng trạng thái).
- [x] Hiển thị mức âm lượng theo thời gian thực — **Hiện thực (30/8/2026)**: box-shadow động theo `volumeLevel` (M4).
- [x] Hiển thị đồng hồ đếm thời lượng — **Hiện thực (30/8/2026)**: `mm:ss` tính từ `recordingStartedAt`, cập nhật mỗi 250ms.
- [x] Thông báo rõ khi trình duyệt từ chối quyền micro — **Hiện thực (30/8/2026)**: `startAudioCapture()`
      ném lỗi bắt được ở `useVoiceStream`, hiển thị thông báo tiếng Việt cụ thể (không phải lỗi kỹ thuật thô).

### O2. Component transcript

- [x] Hiển thị danh sách lượt thoại theo thứ tự — **Hiện thực (30/8/2026)**: [TranscriptList.tsx](frontend/src/components/TranscriptList.tsx).
- [x] Nút "Sửa" và "Hỏi lại" trên mọi lượt, không phân biệt tự động rõ/chưa rõ — **Hiện thực (30/8/2026)**.
- [x] Nút "Sửa" mở ô nhập chỉnh transcript — **Hiện thực (30/8/2026)**: `textarea` inline, gọi `PATCH /turns/{id}` (J3).
- [x] Nút "Hỏi lại" quay về trạng thái ghi âm — **Hiện thực (30/8/2026)**: gọi lại `voice.start()`.
- [x] Nút "Gắn cờ chưa rõ" — **Hiện thực (30/8/2026)**: gọi endpoint mới `POST .../flag` (xem
      ghi chú M2 — bổ sung backend còn thiếu khi làm phần này).
- [x] Hiển thị transcript từng phần khi đang ghi âm — **Hiện thực (30/8/2026)**: `partialText`
      hiện dưới dạng dòng in nghiêng có viền nét đứt, phân biệt rõ với lượt đã chốt.

### O3. Component trường dữ liệu

- [x] Toàn bộ mục O3 — **Hiện thực (30/8/2026)**: [FieldCard.tsx](frontend/src/components/FieldCard.tsx)
      — nhãn tiếng Việt (`spec.label`), nền xanh nhạt + nhãn "Gợi ý AI — chưa xác nhận" khi
      `is_confirmed === false && suggested_value !== null`, `evidence_span` hiển thị ngay dưới
      dạng "Căn cứ: ...", input sửa được (khóa khi đã xác nhận, dùng `unconfirm` để mở lại),
      nút "Đã đối chiếu ✓", viền đỏ + nhãn "BẮT BUỘC" khi `required && !is_confirmed &&
      !suggested_value`, thông báo `validation_message` khi `validation_status === 'format_error'`,
      `spoken_hint` hiện khi trường bắt buộc còn thiếu. Nút "Chép" (GD-4, không có trong danh
      sách O3 gốc nhưng có trong Plan.MD 11.2) cũng thêm vào đây.

### O4. Component khác

- [x] Checklist thành phần hồ sơ — **Hiện thực (30/8/2026)**: [DocumentChecklist.tsx](frontend/src/components/DocumentChecklist.tsx)
      — trạng thái tích chỉ ở client (không đồng bộ server, chỉ hỗ trợ trí nhớ tại quầy, mất khi tải lại trang).
- [x] Thanh tiến độ — **Hiện thực (30/8/2026)**: [ProgressBar.tsx](frontend/src/components/ProgressBar.tsx).
- [x] Danh sách cảnh báo theo mức độ nghiêm trọng — **Hiện thực (30/8/2026)**: [WarningList.tsx](frontend/src/components/WarningList.tsx)
      (thứ tự error > warning > info).
- [x] Banner "Chế độ nhập tay" — **Hiện thực (30/8/2026)**: [ManualModeBanner.tsx](frontend/src/components/ManualModeBanner.tsx),
      hiện khi `session.state === 'AI_UNAVAILABLE'` (L1).
- [x] Hộp thoại xác nhận — **Hiện thực (30/8/2026)**: [ConfirmDialog.tsx](frontend/src/components/ConfirmDialog.tsx),
      dùng cho hủy phiên ở `WorkspacePage`.

### O5. Yêu cầu giao diện chung

- [x] Cỡ chữ tối thiểu 16px toàn ứng dụng — **Hiện thực (30/8/2026)**: `html { font-size: 16px }`
      ở gốc ([index.css](frontend/src/index.css)) + mọi text dùng `text-base` (16px) trở lên,
      không dùng `text-sm`/`text-xs` cho nội dung chính (chỉ nhãn phụ như timestamp).
- [x] Nhãn/thông báo tiếng Việt có dấu — **Hiện thực (30/8/2026)**: toàn bộ UI text.
- [x] Khóa nút "Đọc lại cho người dân" tới khi đủ trường bắt buộc — **Hiện thực (30/8/2026)**:
      `disabled={!allRequiredConfirmed}` ở `WorkspacePage`.
- [x] Không có nút "Xác nhận tất cả" — **Hiện thực (30/8/2026)**: xác nhận bằng kiểm tra thủ
      công toàn bộ component/API — không tồn tại hàm/nút nào lặp `confirm()` cho nhiều trường.
- [x] Hiển thị trạng thái đang tải — **Hiện thực (30/8/2026)**: [LoadingIndicator.tsx](frontend/src/components/LoadingIndicator.tsx)
      dùng ở Dashboard/Workspace/Readback; nút submit disable + đổi nhãn khi `isPending`.

> **Kiểm tra đã chạy cho M/N/O**: `npx tsc --noEmit` (0 lỗi), `npm run build` (thành công),
> `npm run lint` (oxlint, 0 cảnh báo sau khi sửa 2 vấn đề react-hooks phát hiện — xem commit).
> **Chưa làm ở phần này**: test tự động cho frontend (unit/component/E2E) — nằm ở phạm vi mục
> P (kiểm thử tối thiểu), vốn đã giới hạn chỉ giữ test cho nguyên tắc lõi backend + test thủ
> công cho luồng frontend, không có bộ test tự động frontend trong MVP này.

---

## P. Kiểm thử tối thiểu

> Chỉ giữ những test bảo vệ đúng các nguyên tắc lõi và luồng chính có thể chạy được — không xây bộ test toàn diện ở MVP này.

- [x] Test state machine: các chuyển đổi hợp lệ chính và bất hợp lệ tiêu biểu — **Hiện thực
      (30/8/2026)**: đã có từ phần C1 —
      [tests/domain/test_session_state.py](tests/domain/test_session_state.py), 10 test
      (luồng đầy đủ, extraction_failed→AI_UNAVAILABLE, citizen_rejected, ask_again, cancel
      hợp lệ/bất hợp lệ ở trạng thái cuối, cạnh không tồn tại, trạng thái cuối không có lối ra).
- [x] Test `PIIRedactor` che đúng số CCCD, kể cả dạng nói bằng chữ — **Hiện thực (30/8/2026)**:
      đã có từ phần G/redactor — [tests/llm/test_redactor.py](tests/llm/test_redactor.py), 6 test.
- [x] Test `verify_grounding` bắt được giá trị bịa (chống hallucination) — **Hiện thực
      (30/8/2026)**: đã có từ phần I2 — [tests/llm/test_grounding.py](tests/llm/test_grounding.py), 6 test.
- [x] **Test khẳng định không tồn tại endpoint xác nhận hàng loạt** — **Hiện thực (30/8/2026)**:
      viết lại thành [tests/api/test_no_bulk_confirm.py](tests/api/test_no_bulk_confirm.py) —
      file gốc mà docstring của `fields.py` từng tham chiếu
      (`tests/api/test_fields_router.py`) đã bị xóa khi thu hẹp phạm vi test ở phần J (theo
      yêu cầu người dùng: giới hạn test tích hợp, một luồng E2E thay vì nhiều test nhỏ theo
      từng router) — mục P liệt kê đây là một yêu cầu bắt buộc riêng nên viết lại độc lập,
      gọn (thử 4 đường dẫn khả dĩ cho "xác nhận hàng loạt", khẳng định đều 404/405). Cập nhật
      lại tham chiếu trong docstring của [fields.py](app/api/routers/fields.py).
- [x] Test thủ công: luồng chính đầu-cuối — **Hiện thực (30/8/2026)**: kịch bản 1 trong
      [tests/manual/README.md](tests/manual/README.md) — 11 bước qua giao diện thật (tạo
      phiên → ghi âm qua micro thật/AudioWorklet → xác nhận từng trường → đọc lại → hoàn
      tất), có bảng "bước / kết quả mong đợi" để người thực hiện đối chiếu.
- [x] Test thủ công: mọi provider AI lỗi, vẫn hoàn tất bằng nhập tay (UC6) — **Hiện thực
      (30/8/2026)**: kịch bản 2 trong [tests/manual/README.md](tests/manual/README.md) — hướng
      dẫn giả lập lỗi cả 3 provider (LLM/STT/TTS) qua mock hoặc token sai, xác nhận banner
      "Chế độ nhập tay" hiện đúng lúc và toàn bộ luồng vẫn hoàn tất được chỉ bằng nhập tay.

> **Không tự động hóa 2 mục cuối theo đúng quyết định của Checklist gốc** — dựng bộ giả lập
> trình duyệt/micro/audio đầu-cuối (Playwright + WebAudio giả lập...) không tương xứng với
> giá trị mang lại ở quy mô MVP; ưu tiên kịch bản thủ công rõ ràng, dễ chạy lại trước mỗi lần
> release.

---

## Q. Đóng gói và chạy

- [ ] Viết `docker-compose.yml` cho local: PostgreSQL, Redis, backend, frontend
- [ ] Viết `Dockerfile` cho backend
- [ ] Viết `README.md` hướng dẫn chạy local: cài đặt, biến môi trường, migration, seed catalog
- [ ] Script `scripts/run_dev.sh` hoặc lệnh `make dev` khởi động backend + frontend cùng lúc

---

## Đã lược bỏ khỏi MVP

Tổng hợp mọi hạng mục đã quyết định lược bỏ hoặc rút gọn khỏi phạm vi MVP này, kèm lý do — để tránh hiểu nhầm là "quên làm". Thêm lại khi có nhu cầu thật (nhiều người dùng đồng thời, chuẩn bị lên môi trường thật, mở rộng thêm loại trường/thủ tục...).

| Hạng mục | Trạng thái | Lý do |
|---|---|---|
| Đăng nhập/phân quyền nhiều vai trò (`staff_users`, JWT, `/auth/*`) | Lược bỏ hẳn | MVP dùng trong mạng nội bộ điểm hỗ trợ, một cán bộ/máy; không cần phân quyền để chứng minh luồng cốt lõi |
| Dashboard thống kê/báo cáo (KPI-2, KPI-3, KPI-6) | Lược bỏ hẳn | Cần dữ liệu vận hành thật tích lũy mới có ý nghĩa; không phải luồng tương tác cốt lõi |
| Bộ test đầy đủ (P) | Rút gọn | Chỉ giữ test bảo vệ nguyên tắc lõi (chống hallucination, state machine, không có bulk-confirm) và test thủ công luồng chính |
| Màn hình `/login`, `/audit`, `/stats`, `/admin/users` | Lược bỏ hẳn | Đi cùng với việc bỏ đăng nhập/phân quyền và dashboard ở trên |
| **C3 — Chuẩn hóa dữ liệu tiếng Việt** (ngày/số nói bằng lời, giới tính...) | **Cắt hẳn (30/8/2026)** | Không cần cho việc chứng minh AI trích xuất hoạt động; Claude tự xử lý ngôn ngữ tự nhiên đủ tốt mà không cần tiền xử lý chuẩn hóa riêng |
| **C4 — Quy tắc gộp đa lượt** (`MergeDecision`, merge 4 trường hợp) | **Cắt hẳn (30/8/2026)** | Chỉ cần khi có nhiều lần trích xuất trên cùng phiên cần hợp nhất; demo một lần trích xuất là đủ |
| **C1 — điều kiện phụ của state machine** (`context`, kiểm tra required-confirmed/dossier_code trong `transition()`) | Rút gọn (30/8/2026) | Chuyển trách nhiệm kiểm tra điều kiện nghiệp vụ sang tầng service (I), state machine chỉ còn kiểm tra cạnh chuyển đổi hợp lệ |
| **C2 — validator** (`vn_phone_10_digits`, `date_not_future`, `date_reasonable_birth`, `in_options`, registry động) | Rút gọn còn 3 validator đại diện (30/8/2026) | Đủ để chứng minh cơ chế validator hoạt động; thêm lại khi hỗ trợ thêm loại trường |
| **C6 — cảnh báo** (warning riêng cho sai định dạng / không truy vết được, câu hỏi gợi ý từ `spoken_hint`) | Rút gọn còn 2 loại cảnh báo (30/8/2026) | UI chưa hiển thị câu hỏi gợi ý; các loại cảnh báo gộp chung vào luồng cơ bản |
| **E — Audit logging** (đủ danh mục `AuditAction` theo Mục 8.3, ràng buộc transaction chặt, redact `detail`) | Rút gọn còn action của luồng chính (30/8/2026) | Đủ để truy vết luồng chính khi gỡ lỗi; cứng hóa lại (transaction atomic, redact PII trong detail) trước khi lên môi trường thật |
| TTS real-time (WebSocket), circuit breaker nhiều trạng thái, giới hạn theo cán bộ/giờ | Lược bỏ hẳn | Đã ghi chú tại chỗ ở mục H và L — không cần cho quầy hỗ trợ có cán bộ, một phiên tại một thời điểm |
| Model `StaffUser` (bảng người dùng riêng) | Lược bỏ hẳn | Đã ghi chú tại chỗ ở mục B2 — dùng chuỗi tên cán bộ thay vì tài khoản đăng nhập |
</content>
</invoke>
