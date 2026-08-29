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
