# Checklist — Trợ lý giọng nói AI (Dịch vụ công)

- Quy tắc AI:
+ Không viết comment hay docstring vào code vì không cần thiết
+ Không tự call API để test vì tốn token
+ Không tự viết thêm log vào trong checklist vì không cần thiết
+ Không cần phải check syntax code python, html, css hay js đâu vì hầu hết bạn làm đúng

## Cấu trúc dự án

```
app/                        Backend (FastAPI)
  main.py                   /ws (voice), /extension (bridge), /extension/status, REST quản lý PDF/thủ tục
  voice_provider.py         Toàn bộ logic Gemini Live (session, system_instruction, function calling, inject_text)
  submit_flow.py            SUBMIT_PROVINCE/SUBMIT_WARD (hằng số), build_search_url()
  procedure_index.py        Tra cứu thủ tục qua index tĩnh (IDF-weighted keyword overlap)
  dom_ai.py                 Các hàm nhờ AI đọc HTML: pick_search_result, analyze_form
  text_model.py             Lớp trừu tượng gọi text model (Gemini/Ollama/OpenAI-compatible)
  extension_bridge.py       ExtensionManager — cầu nối request/response qua WebSocket /extension
  conversation_log.py       Ghi log JSONL từng phiên vào data/logs/
  rag.py                    RAG keyword 2 tầng cho trang quản lý (không liên quan voice)
extension/                  Chrome extension (Manifest V3)
  background.js             Service worker: giữ kết nối WebSocket tới backend, điều khiển tab, route lệnh
  content_script.js         Chạy trong tab dichvucong.gov.vn: scan_page, click_selector, run_fixed_submit_flow, fill_field
  popup.html/options.html   UI hiện trạng thái kết nối, sửa port
scripts/                    Công cụ one-off (Playwright, không phải runtime app)
  procedure_keywords.py     87 từ khóa cốt lõi để khảo sát
  build_procedure_index.py  Khảo sát Playwright → data/procedure_index.json (grouped, tạm)
  flatten_procedure_index.py  Gộp phẳng → data/procedure_flat_index.json (dùng thật)
static/                     Frontend (vanilla JS, không framework)
  index.html/app.js/styles.css   Trang trợ lý giọng nói chính
  manage.html/manage.js/manage.css  Trang quản lý PDF/thủ tục (RAG)
  worklet.js                AudioWorklet xử lý mic 16kHz PCM
data/
  procedure_flat_index.json  319 thủ tục {name, href} — index tĩnh dùng runtime
  logs/*.jsonl               Log từng phiên (gitignore)
  pdfs/, index.json, procedures/*.json   Dữ liệu RAG trang quản lý
```

## Công nghệ dùng

- **Backend**: Python, FastAPI (WebSocket + REST), `uv` quản lý dependency.
- **Giọng nói**: Google Gemini Live API (`google-genai` SDK) — model `gemini-2.5-flash-native-audio-latest`, audio 2 chiều qua `session.receive()`/`send_realtime_input()`, transcript qua `AudioTranscriptionConfig`, function calling qua `types.Tool`.
- **Text/reasoning thuần**: trừu tượng qua `text_model.py`, provider chọn bằng `.env` (`TEXT_MODEL_PROVIDER`): Gemini SDK trực tiếp, hoặc nhánh OpenAI-compatible (`httpx`) cho Ollama/OpenRouter.
- **Tự động hóa trình duyệt**: Chrome extension (Manifest V3) — `background.js` giữ WebSocket riêng tới backend (`/extension`), `content_script.js` thao tác DOM bằng `simulateClick` (giả lập pointerdown/mousedown/click, vì `.click()` thuần không kích hoạt đúng React) và native setter cho input.
- **Khảo sát dữ liệu 1 lần**: Playwright (dev-dependency) để dựng `procedure_flat_index.json`.
- **Frontend**: vanilla JS, AudioWorklet resample/encode PCM 16kHz gửi lên, giải mã PCM 24kHz nhận về bằng Web Audio API thuần.
- **Không dùng**: embedding/vector DB (RAG chỉ keyword-match), không session/auth (chạy local).

## Trợ lý giọng nói

`/ws` (`app/main.py`) là lớp mỏng: nhận kết nối, giới hạn 1 phiên hoạt động cùng lúc, giao hết việc cho `voice_provider.py`.

Push-to-talk: nút "Nhấn để nói" hoặc phím Enter/Space để bắt đầu, bấm/phím lại để kết thúc (`e.repeat` guard). `automatic_activity_detection` tắt hẳn, client tự gửi `activity_start`/`activity_end`; audio chỉ gửi khi đang ở trạng thái "đang nói".

Gemini Live không tự khởi phát turn đầu nếu không có input — `run_voice_session` tự bơm 1 turn giả silent (`inject_text(..., silent=True)`) ngay khi mở session để AI tự nói câu chào theo `system_instruction`.

Cờ `suppress_show_submit`: mọi turn do hệ thống tự inject (`inject_text` — câu chào, `cancel_submit`, thông báo hoàn tất) đều suppress, chỉ turn hội thoại thật mới được kích hoạt `show_submit_button`.

Frontend hiện transcript dạng chat real-time, sóng âm theo trạng thái nói/nghe, bong bóng "đang gõ" khi AI xử lý. Audio phát theo chunk, buffer đệm 120ms đầu mỗi lượt.

## Tách "làm việc" khỏi "nói chuyện"

Tác vụ text thuần (trích tên thủ tục, chọn CSS selector, phân tích form) đi qua `app/text_model.py`, tách khỏi Gemini Live. Provider chọn qua `.env` (`TEXT_MODEL_PROVIDER`): `gemini`, `ollama`, hoặc khác (nhánh OpenAI-compatible qua `httpx`, đang cấu hình OpenRouter). Nhánh OpenAI-compat không ép `response_format: json_schema` mà nhúng schema vào prompt rồi tự trích JSON. Gặp `429` thì đọc `retry_after_seconds`/`Retry-After`, thử lại tối đa 3 lần.

`.env` không dùng comment để bật/tắt — mọi giá trị (Gemini, OpenRouter, Ollama) để thật sẵn, chỉ `TEXT_MODEL_PROVIDER` quyết định (voice luôn cố định Gemini Live).

## Tra cứu thủ tục qua RAG (trang quản lý)

`app/rag.py` tìm keyword 2 tầng (chọn thủ tục → chọn mục nội dung) trên `data/index.json`/`data/procedures/*.json`, không dùng embedding. `build_index.py` dựng lại index từ PDF. `static/manage.html` quản lý upload/xóa PDF, tự rebuild index. Không nối vào hội thoại giọng nói.

## Màn hình: chờ (`#idleCard`)

Nút "Bắt đầu hỗ trợ" (`#startBtn`) → mở `/ws`, chuyển sang màn hình chat. Nút "Test nộp: Đăng ký khai sinh" (`#testSubmitBtn`) → mở `/ws` và gửi thẳng `submit_procedure` với tên cố định, để test nhanh không cần nói qua giọng nói. Badge trạng thái kết nối extension (`#extensionStatus`, xem mục "Giao diện extension" bên dưới).

## Màn hình: chat (`#chatCard`)

Luôn có: sóng âm + dòng trạng thái (`#status`), khung transcript (`#chatLog`), nút "Nhấn để nói"/"Đang nói..." (`#talkBtn`, push-to-talk — phím Enter/Space cũng bật/tắt được, có `e.repeat` guard), nút "Kết thúc hỗ trợ" (`#stopBtn`). Mọi `submit_procedure_status`/`submit_procedure_done` từ backend vừa cập nhật `#status` vừa thêm 1 bubble `.bubble.system` (viền nét đứt, căn trái) vào `#chatLog` để thấy tiến trình theo dõi được ("Đang quét trang...", "Đang điền \"...\"...").

**Nhóm nút nộp hồ sơ** (`#submitPrompt`, ẩn mặc định): hiện khi AI nói có ý "nộp hồ sơ" (turn chứa từ "nộp", không phải turn hệ thống tự bơm) — 2 nút [Tự động nộp (đếm ngược 3s)] [Hủy nộp]. Hết 3s hoặc bấm [Tự động nộp] → gọi `submit_procedure`; bấm [Hủy nộp] → dừng đếm, gửi turn giả "chưa muốn nộp" để AI tự hỏi lại. Nút "Thử lại" (`#retryBtn`, ẩn mặc định) hiện khi nộp lỗi hẳn (hết 3 lần tự động retry) — gửi lại đúng request cuối trên cùng WebSocket nếu còn sống.

**Nhóm nút sau khi vào trang form thật** (`#postSubmitActions`, ẩn mặc định): hiện cùng lúc `submit_procedure_done` (sau khi `run_fixed_submit_flow` xong) — không tự ẩn, bấm lại được nhiều lần:
- **"Quét trang"** (`#triggerScanBtn`) → gửi `trigger_scan_form`, xử lý y hệt tool-call `scan_form_fields` của AI (xem mục quét form bên dưới) nhưng khởi phát từ UI thay vì giọng nói.
- **"Thành phần hồ sơ cần chuẩn bị"** (`#requiredDocsBtn`) → gửi `request_required_documents`, hiện list card (`renderRequiredDocumentsCard`) tóm tắt giấy tờ cần chuẩn bị, không qua giọng nói.

**Nhóm nút chọn cách điền** (`#scanChoicePrompt`, ẩn mặc định): hiện sau khi AI tóm tắt xong các trường đã quét được (turn_complete) — 2 nút [Nhờ AI nhập] [Tôi tự điền].

## Nghiệp vụ: luồng nộp hồ sơ

```
_handle_submit_procedure (retry tối đa 3 lần, chỉ báo lỗi ở lần cuối):
  NẾU có procedure_name truyền thẳng (nút Test) → dùng luôn
  NGƯỢC LẠI → nhờ text model trích từ lịch sử hội thoại (_extract_procedure_name)
  NẾU không trích được tên → báo lỗi, DỪNG (không retry, input sai)

  NẾU tên thủ tục có trong procedure_index (lookup_candidates)
    NẾU 1 candidate → dùng luôn href
    NẾU nhiều candidate → nhờ text model chọn 1 href (pick_variant_href)
    NẾU chọn được → mở thẳng URL chi tiết, bỏ qua bước tìm kiếm bên dưới
    NẾU không chọn được → coi như không có candidates, rơi xuống fallback

  NẾU không có candidates
    → mở URL tìm kiếm, nhờ AI đọc HTML chọn kết quả (pick_search_result)
    NẾU không chọn được lần 1 → đợi 2s, quét lại, thử lần 2
    NẾU vẫn không chọn được → báo lỗi, DỪNG (không retry, input sai)
    NẾU chọn được → bấm vào kết quả

  Ngay khi vào đúng trang chi tiết: tự quét "Thành phần hồ sơ" lưu cache
  (xem nghiệp vụ thành phần hồ sơ bên dưới) — KHÔNG gọi AI ở bước này

  Tại trang chi tiết: chọn Tỉnh/Phường cố định → bấm "Nộp hồ sơ" → "Đồng ý" →
  tìm đúng dòng khớp phường → cuộn tới, DỪNG — không tự bấm "Nộp trực tuyến"
  → báo UI xong (hiện nhóm nút #postSubmitActions) + bơm turn giả để AI tự nói xác nhận

  NẾU lỗi runtime (mất kết nối / timeout / lỗi thao tác / lỗi lạ)
    → CÓ retry (tối đa 3 lần, cách 1.5s), chỉ báo lỗi UI ở lần cuối
```

Index tĩnh: `procedure_index.py` tra `data/procedure_flat_index.json` (319 thủ tục, khảo sát bằng Playwright qua `scripts/`, so khớp bằng overlap từ khóa có trọng số IDF). Cần khảo sát lại thì `uv add --dev playwright && uv run playwright install chromium`, sửa `scripts/procedure_keywords.py`, chạy `build_procedure_index.py` rồi `flatten_procedure_index.py`.

System instruction (`voice_provider.py`): mở đầu bằng câu "Tôi là trợ lý giọng nói ảo của Phường Yên Sở, bạn muốn hỗ trợ thủ tục hành chính nào?"; biết sẵn địa chỉ Yên Sở/Hà Nội; nếu chưa rõ thủ tục thì hỏi lại trước, chưa vội gọi tool.

## Nghiệp vụ: quét form và tự điền (Gemini Live function calling)

Chỗ duy nhất dùng function calling thật của Gemini Live (`types.Tool`) — khác `submit_procedure` vốn chỉ dựa vào nút bấm + so khớp keyword. Kích hoạt bằng giọng nói ("quét trang giúp tôi"/"giờ tôi phải làm gì", đã đăng nhập VNeID) hoặc bấm nút "Quét trang" (`#triggerScanBtn`).

```
KHI kích hoạt (Gemini Live tự gọi function scan_form_fields, hoặc nút Quét trang)
  → backend lệnh extension scan_form_with_comboboxes (timeout 60s, không phải 20s mặc định):
      tìm mọi nút combobox custom (button.custom-input-typography), với MỖI nút:
      gán data-scan-field-id tạm → bấm mở → đọc options thật (li[role="option"]) →
      bấm đóng lại → giữ nguyên attribute khi serialize HTML
      (options combobox KHÔNG có sẵn trong HTML tĩnh, phải bấm mở mới thấy)
      + hỗ trợ đa frame/đa domain: manifest.json khớp https://*.gov.vn/* (thủ tục có thể
      điều hướng sang domain con khác, vd dichvucongnganhtuphap.moj.gov.vn) và bật
      all_frames: true (form thật thường nằm trong iframe cross-origin domain khác hẳn,
      vd tokhaidientu.moj.gov.vn — same-origin policy chặn đọc DOM xuyên iframe nên content
      script phải tự inject bên trong iframe); background.js dùng
      chrome.webNavigation.getAllFrames + chrome.tabs.sendMessage(tabId, msg, {frameId})
      để quét/điền đúng frame, data-scan-field-id thêm prefix ngẫu nhiên theo frame để
      không trùng khi gộp
  → dom_ai.analyze_form(html, combobox_options) trích {label, selector, field_type,
    current_value, options} — field_type là "text" (gõ chữ), "combobox" (bấm mở dropdown,
    PHẢI dùng selector [data-scan-field-id="..."] và options đúng danh sách thật đã bấm
    mở, không tự bịa), hoặc "choice_option" (MỘT lựa chọn cụ thể trong nhóm radio/checkbox
    đã hiển thị sẵn, vd <x-radio> — selector trỏ thẳng vào lựa chọn con, không phải cả nhóm)
  → lưu fields vào session_state (theo phiên), trả kết quả cho Gemini qua tool_response
    (nếu do nút bấm thì bơm turn giả để AI tự tóm tắt)
  → AI tóm tắt các trường, hỏi "muốn nhờ AI tự điền hay tự điền lấy"

  KHI AI nói xong câu hỏi đó (turn_complete) → hiện nhóm nút #scanChoicePrompt

  NẾU bấm [Tôi tự điền]
    → chỉ gửi turn giả bảo AI giới thiệu qua trường quan trọng rồi dừng, KHÔNG tự điền

  NẾU bấm [Nhờ AI nhập]
    NẾU chưa có fields đã lưu → báo AI nói người dùng quét lại, DỪNG
    NGƯỢC LẠI
      → nhờ text model so khớp fields + tỉnh/phường cố định + toàn bộ transcript
      → CHỈ lấy field XÁC ĐỊNH CHẮC CHẮN giá trị (không suy đoán/bịa CCCD, ngày sinh...)
      → gọi extension fill_field cho từng field theo field_type:
        combobox → bấm mở danh sách, chọn option khớp text
        choice_option → simulateClick thẳng vào selector, không mở gì
        text → set qua native setter + fire input/change event
      → báo lại qua turn giả: đã điền được gì, còn thiếu gì
```

Log chi tiết vào `data/logs/*.jsonl` cho từng bước, cả lúc bắt đầu lẫn khi xong (`scan_form_with_comboboxes_start/result`, `analyze_form_start`, `ai_fill_fields_start/decided`, `fill_field_start/done`).

**Bug đã biết, chưa fix**: combobox "Phường/Xã" là cascading dropdown, rỗng cho tới khi "Tỉnh/Thành phố" đã chọn — `scanFormWithComboboxes()` quét độc lập từng combobox nên dễ bỏ sót field Phường.

## Nghiệp vụ: thành phần hồ sơ cần chuẩn bị

`content_script.js` (`scanRequiredDocuments`) quét DOM thuần (không dùng AI) bảng dưới heading "Thành phần hồ sơ", gộp mọi bảng `<table>` con, mỗi dòng lấy `{name, qty}` giữ nguyên số lượng/loại thật (không lọc theo số lượng).

```
Tự động, ngay khi vào đúng trang chi tiết thủ tục (trước khi chọn Tỉnh/Phường):
  → required_documents.scan_raw(procedure_name, known_url)
    NẾU known_url đã có cache đầy đủ items → dùng luôn, KHÔNG gọi extension
    NGƯỢC LẠI → extension scan_required_documents, lưu raw vào cache
      (data/required_documents_cache.json, key = URL) dạng {"items": [...], "summary": None}
      — KHÔNG gọi AI ở bước này

KHI người dùng bấm nút [Thành phần hồ sơ cần chuẩn bị] (#requiredDocsBtn):
  → required_documents.summarize(...) — gọi lại scan_raw() trước (tận dụng cache)
  NẾU cache đã có summary → trả thẳng, KHÔNG gọi AI lại
  NGƯỢC LẠI
    → nhờ text model tóm tắt items dài dòng (giữ rõ số lượng/loại, bỏ trích dẫn luật)
    → ghi đè cache thành {"items": [], "summary": [...]} — xóa raw, chỉ giữ bản tóm tắt
  → hiện list card (renderRequiredDocumentsCard, tái dùng .procedure-card)
```

Đã khảo sát trước toàn bộ 319 thủ tục bằng Playwright (`scripts/survey_required_documents.py`, chạy ngoại tuyến, hỗ trợ `SURVEY_LIMIT` để test nhỏ) để cache có sẵn raw cho hầu hết thủ tục, tránh phải quét DOM qua extension mỗi lần.

Playwright là dev-dependency thường trực của dự án (không gỡ sau khi dùng — dùng lại để khảo sát cấu trúc trang thật trước khi code).

## Giao diện extension (Chrome, Manifest V3)

Popup và Options hiện trạng thái kết nối backend, cho sửa port, nút test kết nối. `background.js` tự reconnect khi mất kết nối.

Trang chính (`static/index.html`) cũng tự hiện trạng thái kết nối extension bằng 1 div trong `#idleCard` (chấm tròn + nhãn "Kết nối: OK"/"Kết nối: Fail") — gọi `GET /extension/status` khi load và poll lại mỗi 5 giây.

**Ping/pong 2 chiều để tránh kết nối "chết âm thầm"**: `background.js` là MV3 service worker, bị Chrome tự unload sau ~30s không hoạt động — làm mất biến `socket` module-level dù WebSocket TCP có thể chưa kịp báo đóng, khiến `/extension/status` (REST, luôn trả lời được) báo `connected: true` trong khi `send_command` thật lại `ExtensionNotConnected` vì socket đã chết. Khắc phục 2 lớp: `chrome.alarms` chu kỳ 0.5 phút (mức tối thiểu Chrome cho phép) để tự đánh thức worker và tự `connect()` lại nếu socket mất; đồng thời ping/pong qua chính WebSocket mỗi 15s (`background.js` gửi `{type: ping}`, backend `/extension` trả `{type: pong}`) — nếu backend không nhận được gì (kể cả ping) trong 40s (`_EXTENSION_PING_TIMEOUT`, `app/main.py`) thì tự coi socket chết và `unregister()`, để `is_connected` phản ánh đúng trạng thái thay vì báo OK giả.

## Rủi ro / giới hạn đã biết

- `/ws` và `/extension` không có xác thực — chấp nhận được vì chỉ chạy local, cần vá nếu mở ra ngoài localhost/LAN.
- `run_fixed_submit_flow` dùng bản đồ thao tác cố định — nếu dichvucong.gov.vn đổi giao diện sẽ hỏng, cần khảo sát lại thủ công.
- Tỉnh/phường nộp hồ sơ cố định trong code (`SUBMIT_PROVINCE`/`SUBMIT_WARD`) — phường có thể không tồn tại cho một số thủ tục hiếm.
- Model free tier (Gemini, OpenRouter `:free`) đều có rate-limit.
