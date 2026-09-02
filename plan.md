# Plan — Đơn giản hóa thành AI Agent giọng nói thuần

## Mục tiêu

Bỏ hoàn toàn cơ chế điều khiển trình duyệt/extension/thao tác DOM tự động
(scan form, tự điền, tự bấm nộp hồ sơ qua WebSocket `/extension`). Hệ thống
sau đợt này CHỈ còn là một AI Agent nói chuyện bằng giọng nói với người dùng
về thủ tục hành chính — không đăng nhập, không cài gì thêm, ai vào trang
cũng dùng được ngay.

Các nghiệp vụ cũ liên quan "thành phần hồ sơ", "các bước nộp hồ sơ", "cần
chuẩn bị những gì" được giữ lại nhưng đổi cách thể hiện: AI nói bằng giọng
nói + đồng thời hệ thống hiện card minh họa dạng bước (step) trên giao diện
web, có nút "Mở nơi nộp hồ sơ thủ tục" trỏ thẳng tới link chính thức trên
dichvucong.gov.vn (mở tab mới, người dùng tự thao tác tiếp — web không tự
mở/điều khiển trang đó nữa).

Dữ liệu tĩnh đã khảo sát trước (`procedure_flat_index.json` 319 thủ tục,
`required_documents_cache.json` thành phần hồ sơ) được giữ nguyên và tái sử
dụng — đây là nguồn duy nhất để tra cứu, không còn quét DOM runtime qua
extension. Làm mới lại 2 nguồn dữ liệu này (không chỉ thành phần hồ sơ như
trước) qua 1 script chạy tay gộp sẵn (`scripts/refresh_all.py`, Playwright —
dev-dependency, không gỡ) — KHÔNG chạy nền tự động trong server production
(quyết định lại sau khi trao đổi: server không cần Docker/Playwright chạy
nền, chỉ cần fetch thủ công lúc dev rồi deploy lại cache mới).

**Không tự test gọi API Gemini thật trong lúc code (theo yêu cầu) — chỉ kiểm
tra bằng cách đọc lại code, không chạy `uv run` gọi model.**

## Loại bỏ hoàn toàn

- `extension/` (toàn bộ thư mục Chrome extension MV3)
- `app/extension_bridge.py` (ExtensionManager, WebSocket `/extension`)
- `app/submit_flow.py` (SUBMIT_PROVINCE/WARD, build_search_url — không còn
  luồng tự mở/tự điền nên tỉnh/phường cố định không còn ý nghĩa runtime;
  giữ khái niệm "địa chỉ mặc định Yên Sở" nhưng chuyển thành hằng số đơn giản
  trong `voice_provider.py` chỉ để AI trả lời câu hỏi địa chỉ)
- `app/dom_ai.py` (analyze_form, pick_search_result, eform_field_to_scan_field
  — toàn bộ phần đọc HTML/DOM thật qua AI, không còn extension để lấy HTML)
- Trong `app/main.py`: `_handle_scan_form_fields`, `_handle_ai_fill_fields`,
  `_handle_submit_procedure`, `_attempt_submit_procedure`, `/extension`
  endpoint, `/extension/status` endpoint, JWT auth (`_check_ws_token`) trên
  `/ws` — bỏ luôn vì không cần đăng nhập nữa
- `app/auth.py`, `data/allowed_users.json`, JWT liên quan — bỏ hẳn xác thực
  người dùng thường; `/auth/login` xóa. `ADMIN_PASSWORD` cho `/admin.html`/
  `/manage.html` GIỮ NGUYÊN (không liên quan voice, vẫn cần bảo vệ RAG PDF).
- Trong `app/voice_provider.py`: tool `scan_form_fields`, `fill_form_fields`
  (function calling thật) — bỏ. Tool `propose_submit_procedure` + cơ chế nút
  đếm ngược tự động nộp — bỏ (không còn "nộp hộ" runtime).
- Frontend: `#submitPrompt`, `#postSubmitActions`, `#retryBtn`,
  `#extensionStatus`/`#extensionStatusChat`, `startScanTest()`, toàn bộ logic
  liên quan trong `static/app.js`.
- `data/eform_2056_apiid_scan.json/.progress`, `data/form_inspect/` — dữ liệu
  khảo sát form hộ tịch điện tử qua extension, không còn dùng, xóa.
- `scripts/inspect_form_live.py`, `scripts/brute_force_eform_apiid.py` — công
  cụ khảo sát form runtime qua Playwright + extension, không còn liên quan.

## Giữ nguyên / tái dùng

- `procedure_index.py` (tra cứu thủ tục qua index tĩnh IDF) — vẫn dùng y hệt,
  chỉ đổi nơi gọi (từ luồng submit sang tool `show_procedure_steps`).
- `required_documents.py` — bỏ nhánh gọi `extension_manager.send_command`
  trong `scan_raw`; nếu cache thiếu `items` thì trả rỗng kèm cờ báo "chưa có
  dữ liệu" thay vì quét runtime. Giữ nguyên `summarize()` (gọi text model tóm
  tắt, cache lại).
- `text_model.py`, `conversation_log.py`, `rag.py`, `build_index.py`,
  `static/manage.html/js/css`, `static/admin.html/js` — không đổi.
- `data/procedure_flat_index.json`, `data/required_documents_cache.json` —
  không đổi định dạng, chỉ đổi cách được refresh (scheduler thay vì script
  chạy tay).
- Playwright vẫn là dev-dependency thường trực (không gỡ, theo ghi nhớ
  [[keep-playwright-installed]]).

## Kiến trúc mới

### 1. Backend — 2 tool mới thay cho toàn bộ cụm cũ

Trong `voice_provider.py`, thay 3 tool cũ (`scan_form_fields`,
`fill_form_fields`, `propose_submit_procedure`) bằng 2 tool:

- **`show_required_documents(procedure_name: str)`** — AI gọi khi người dùng
  hỏi "cần chuẩn bị giấy tờ gì", "thành phần hồ sơ gồm những gì". Backend:
  1. `procedure_index.lookup_candidates()` + `pick_variant_href()` (tái dùng
     y hệt logic cũ) để xác định đúng thủ tục + href tĩnh.
  2. `required_documents.get_cached(name)` — đọc thẳng cache tĩnh (không
     scan runtime). Thiếu summary thì gọi `summarize()` (vẫn gọi text model
     tóm tắt, có cache).
  3. Trả tool_response ngắn gọn (số lượng + vài ví dụ, như cũ) cho Gemini
     Live đọc; đồng thời qua `websocket.send_json` gửi message riêng
     `procedure_info` (data đầy đủ: tên, href, danh sách giấy tờ) để
     frontend render card.

- **`show_submission_steps(procedure_name: str)`** — AI gọi khi người dùng
  hỏi "các bước nộp hồ sơ thế nào", "nộp ở đâu". Backend xác định thủ tục
  (dùng lại `lookup_candidates`/`pick_variant_href`), trả về:
  - `procedure_name`, `href` (link chi tiết thật trên dichvucong.gov.vn, để
    trống nếu không tra được)
  - Danh sách bước cố định dạng tĩnh (không cần AI sinh động — 4 bước chuẩn:
    xác định đúng thủ tục → chuẩn bị hồ sơ → nộp trực tuyến tại link chính
    thức (VNeID) → theo dõi kết quả xử lý), do backend viết cứng.
  Gửi message `submission_steps` cho frontend render card kèm nút "Mở nơi
  nộp hồ sơ thủ tục" → `<a target="_blank" href="{href}">`.

  Nếu không tra được thủ tục nào (không có candidates), trả lỗi ngắn để AI
  tự hỏi lại rõ tên thủ tục — không đoán bừa href.

Không còn khái niệm "phiên đã submit 1 thủ tục" / chặn đề nghị lặp lại — 2
tool trên là tra cứu thuần, gọi lại bao nhiêu lần cũng được, không cần guard.

`system_instruction` viết lại theo đúng tinh thần cũ (câu chào cố định, biết
địa chỉ Yên Sở/Hà Nội, tự giới thiệu khi được hỏi) nhưng mô tả lại 2 khả
năng mới: (1) tra cứu thành phần hồ sơ, (2) hướng dẫn các bước + đưa link
nộp hồ sơ chính thức — bỏ hẳn phần "tự động mở/điền hộ form".

`/ws` bỏ toàn bộ nhánh `submit_procedure`/`cancel_submit`/`trigger_scan_form`/
`request_required_documents` kiểu cũ trong `from_browser()` — không còn nút
bấm nào kích hoạt các message này nữa (UI chỉ còn mic + hiển thị card do tool
call sinh ra), nên bỏ luôn nhánh xử lý phía backend.

`/ws` bỏ luôn xác thực JWT (`_check_ws_token`) — public.

### 2. Frontend (`static/index.html`, `app.js`, `styles.css`)

- Bỏ nút "Quét trang" (`#testScanBtn`), badge kết nối extension, nhóm nút
  `#submitPrompt`/`#postSubmitActions`/`#retryBtn`.
- Giữ nguyên: card giới thiệu tính năng ở màn chờ (`#idleCard`), nút "Bắt đầu
  hỗ trợ" → mic → `#chatCard` với transcript, sóng âm, push-to-talk.
- Thêm 2 hàm render card mới trong `app.js`:
  - `renderRequiredDocumentsCard(data)` — tái dùng gần như nguyên bản hàm cũ
    cùng tên (đã có sẵn, chỉ đổi field nguồn nếu cần).
  - `renderSubmissionStepsCard(data)` — card mới liệt kê từng bước (số thứ
    tự + mô tả ngắn) dạng timeline dọc đơn giản (không cần thư viện), cuối
    card có nút/link "Mở nơi nộp hồ sơ thủ tục" nếu có `href` (mở
    `target="_blank"`), nếu không có href thì hiện ghi chú "Chưa tra được
    link chính thức, vui lòng tìm trên dichvucong.gov.vn".
- `handleWsMessage` thêm xử lý `type: 'procedure_info'` →
  `renderRequiredDocumentsCard`, `type: 'submission_steps'` →
  `renderSubmissionStepsCard`.
- Trang `static/required-documents.html`/`.js` (tra cứu độc lập không qua
  voice) — giữ nguyên, vẫn hữu ích như một trang tra cứu nhanh bằng tay,
  không liên quan tới extension.

### 3. Auth

- Xóa `app/auth.py`, `data/allowed_users.json`, `/auth/login`,
  `static/admin.js` phần liên quan JWT users (nếu admin.html có quản lý user
  thường thì bỏ luôn phần đó, chỉ giữ phần liên quan PDF/manage nếu có).
- `/ws` không còn check token — mở public hoàn toàn.
- `ADMIN_PASSWORD` cho `/admin.html`, `/manage.html` (X-Admin-Password
  header) — GIỮ NGUYÊN, không đổi (đây là quản trị dữ liệu PDF/thủ tục RAG,
  khác phạm vi việc này).
- `.env` bỏ `JWT_SECRET`; giữ `ADMIN_PASSWORD`, `GEMINI_API_KEY`,
  `GEMINI_VOICE_MODEL`, `GEMINI_VOICE_NAME`, `GEMINI_TEXT_MODEL`,
  `MAX_CONCURRENT_SESSIONS`, `FRONTEND_ORIGIN`.

### 4. Làm mới dữ liệu tĩnh — script chạy tay, không chạy nền

Quyết định lại sau khi hỏi người dùng: KHÔNG tích hợp scheduler tự động vào
server (server không cần Playwright/Docker cho việc này). Thay vào đó:

- `scripts/refresh_all.py` — script mới, gộp tuần tự 3 bước đã có sẵn:
  `build_procedure_index.py` → `flatten_procedure_index.py` →
  `survey_required_documents.py`. Chạy tay (`uv run scripts/refresh_all.py`)
  khi muốn làm mới `procedure_flat_index.json` và
  `required_documents_cache.json`.
- `procedure_index.reload()`/`required_documents.reload()` (module-level,
  giống `reload_index()` của `rag.py`) — cho phép nạp lại cache mà không cần
  restart server nếu ai đó chạy script trong lúc server đang sống; không có
  cơ chế tự gọi 2 hàm này, chỉ để dùng thủ công (vd qua REPL) nếu cần.
- Không đổi Dockerfile/compose.yaml theo hướng cần Playwright ở production —
  giữ nguyên image nhẹ hiện tại (`--no-dev`, không copy `scripts/`).

### 5. Checklist.MD

Viết lại toàn bộ theo cấu trúc mới sau khi code xong — bỏ hết phần extension/
DOM/submit-flow, thêm phần 2 tool tra cứu mới + scheduler. Giữ nguyên 4 quy
tắc AI ở đầu file.

## Thứ tự thực hiện

1. Backend: viết lại `voice_provider.py` (tool mới + system_instruction),
   `main.py` (bỏ auth/extension endpoints, thêm handler 2 tool mới, lifespan
   khởi động scheduler), sửa `required_documents.py` (bỏ nhánh extension).
2. Xóa các file/thư mục không dùng (extension/, dom_ai.py, submit_flow.py,
   extension_bridge.py, auth.py, data/allowed_users.json, data/form_inspect/,
   data/eform_2056_apiid_scan.*, scripts/inspect_form_live.py,
   scripts/brute_force_eform_apiid.py).
3. Viết `app/scheduler.py`, nối vào lifespan `main.py`.
4. Frontend: sửa `index.html`, `app.js`, `styles.css` — bỏ UI cũ, thêm card
   bước nộp hồ sơ.
5. `.env`/`pyproject.toml`: bỏ biến JWT, gỡ dependency `pyjwt` nếu còn sót
   (không đụng tới playwright).
6. Viết lại `Checklist.MD`.
7. Đọc lại toàn bộ diff 1 lượt cho nhất quán (không chạy syntax-check theo
   quy tắc dự án, không gọi API Gemini thật).
