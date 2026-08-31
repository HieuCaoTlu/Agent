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
- **Text/reasoning thuần**: trừu tượng qua `text_model.py`, `TEXT_MODEL_PROVIDER=gemini` cố định (Gemini SDK trực tiếp) — code vẫn còn nhánh OpenAI-compatible (`httpx`) cho Ollama/OpenRouter nhưng không dùng, `.env` đã bỏ các biến `TEXT_MODEL_BASE_URL/NAME/API_KEY`, `OLLAMA_*` liên quan.
- **Tự động hóa trình duyệt**: Chrome extension (Manifest V3) — `background.js` giữ WebSocket riêng tới backend (`/extension`), `content_script.js` thao tác DOM bằng `simulateClick` (giả lập pointerdown/mousedown/click, vì `.click()` thuần không kích hoạt đúng React) và native setter cho input.
- **Khảo sát dữ liệu 1 lần**: Playwright (dev-dependency) để dựng `procedure_flat_index.json`.
- **Frontend**: vanilla JS, AudioWorklet resample/encode PCM 16kHz gửi lên, giải mã PCM 24kHz nhận về bằng Web Audio API thuần. Orb ở màn hình chờ (`static/orb.js`) dùng Three.js (CDN, r0.158) — icosahedron + custom GLSL shader (simplex noise displacement + fresnel glow xoay), không audio-reactive (màn chờ chưa có audio thật); tự dừng render qua `MutationObserver` khi `#idleCard` bị ẩn để không tốn GPU lúc đang chat.
- **Không dùng**: embedding/vector DB (RAG chỉ keyword-match), không session/auth (chạy local).

## Trợ lý giọng nói

`/ws` (`app/main.py`) là lớp mỏng: nhận kết nối, giới hạn 1 phiên hoạt động cùng lúc, giao hết việc cho `voice_provider.py`.

Push-to-talk: nút "Nhấn để nói" hoặc phím Enter/Space để bắt đầu, bấm/phím lại để kết thúc (`e.repeat` guard). `automatic_activity_detection` tắt hẳn, client tự gửi `activity_start`/`activity_end`; audio chỉ gửi khi đang ở trạng thái "đang nói".

Gemini Live không tự khởi phát turn đầu nếu không có input — `run_voice_session` tự bơm 1 turn giả silent (`inject_text(..., silent=True)`) ngay khi mở session để AI tự nói câu chào theo `system_instruction`.

Cờ `suppress_show_submit`: mọi turn do hệ thống tự inject (`inject_text` — câu chào, `cancel_submit`, thông báo hoàn tất) đều suppress, chỉ turn hội thoại thật mới được kích hoạt `show_submit_button`.

Frontend hiện transcript dạng chat real-time, sóng âm theo trạng thái nói/nghe, bong bóng "đang gõ" khi AI xử lý. Audio phát theo chunk, buffer đệm 120ms đầu mỗi lượt.

## Tách "làm việc" khỏi "nói chuyện"

Tác vụ text thuần (trích tên thủ tục, chọn CSS selector, phân tích form) đi qua `app/text_model.py`, tách khỏi Gemini Live nhưng vẫn cùng dùng `GEMINI_API_KEY`/`GEMINI_TEXT_MODEL`. `TEXT_MODEL_PROVIDER=gemini` cố định — nhánh OpenAI-compatible (`httpx`, dùng cho Ollama/OpenRouter trước đây) vẫn còn trong code nhưng không còn biến `.env` tương ứng, coi như tắt.

## Tra cứu thủ tục qua RAG (trang quản lý)

`app/rag.py` tìm keyword 2 tầng (chọn thủ tục → chọn mục nội dung) trên `data/index.json`/`data/procedures/*.json`, không dùng embedding. `build_index.py` dựng lại index từ PDF. `static/manage.html` quản lý upload/xóa PDF, tự rebuild index. Không nối vào hội thoại giọng nói.

## Màn hình: chờ (`#idleCard`)

Nút "Bắt đầu hỗ trợ" (`#startBtn`) → mở `/ws`, chuyển sang màn hình chat. Nút "Quét trang" (`#testScanBtn`, `startScanTest()`) → mở `/ws` như bình thường (mic hoạt động, có thể nói tiếp ngay trong phiên), tự động gửi `trigger_scan_form` ngay khi kết nối xong và hiện sẵn `#postSubmitActions` — dùng để quét form trên bất kỳ tab `*.gov.vn` đang mở sẵn mà không cần đi qua toàn bộ luồng nộp hồ sơ trước. Link "Quản trị"/"Quản lý dữ liệu thủ tục" hiện ở footer (công khai, xem mục "Bảo mật khi expose ra ngoài"). Badge trạng thái kết nối extension (`#extensionStatus`, xem mục "Giao diện extension" bên dưới).

## Màn hình: chat (`#chatCard`)

Luôn có: sóng âm + dòng trạng thái (`#status`), khung transcript (`#chatLog`), nút "Nhấn để nói"/"Đang nói..." (`#talkBtn`, push-to-talk — phím Enter/Space cũng bật/tắt được, có `e.repeat` guard), nút "Kết thúc hỗ trợ" (`#stopBtn`). Mọi `submit_procedure_status`/`submit_procedure_done` từ backend vừa cập nhật `#status` vừa thêm 1 bubble `.bubble.system` (viền nét đứt, căn trái) vào `#chatLog` để thấy tiến trình theo dõi được ("Đang quét trang...", "Đang điền \"...\"...").

**Nhóm nút nộp hồ sơ** (`#submitPrompt`, ẩn mặc định): hiện khi AI gọi tool-call `propose_submit_procedure` (KHÔNG còn string-match từ "nộp" trong text — từng gây bug AI tự kích hoạt luồng nộp chỉ vì nhắc tới từ "nộp" trong câu giải thích khác, ví dụ user hỏi "giới thiệu qua thành phần cần nộp" cũng vô tình bật đếm ngược) — 2 nút [Tự động nộp (đếm ngược 3s)] [Hủy nộp]. Hết 3s hoặc bấm [Tự động nộp] → gọi `submit_procedure`; bấm [Hủy nộp] → dừng đếm, gửi turn giả "chưa muốn nộp" để AI tự hỏi lại. Nút "Thử lại" (`#retryBtn`, ẩn mặc định) hiện khi nộp lỗi hẳn (hết 3 lần tự động retry) — gửi lại đúng request cuối trên cùng WebSocket nếu còn sống.

**Nhóm nút sau khi vào trang form thật** (`#postSubmitActions`, ẩn mặc định): hiện cùng lúc `submit_procedure_done` (sau khi `run_fixed_submit_flow` xong) — không tự ẩn, bấm lại được nhiều lần:
- **"Quét trang"** (`#triggerScanBtn`) → gửi `trigger_scan_form`, xử lý y hệt tool-call `scan_form_fields` của AI (xem mục quét form bên dưới) nhưng khởi phát từ UI thay vì giọng nói.
- **"Thành phần hồ sơ cần chuẩn bị"** (`#requiredDocsBtn`) → gửi `request_required_documents`, hiện list card (`renderRequiredDocumentsCard`, không viền trái nhấn màu như card thủ tục RAG) tóm tắt giấy tờ cần chuẩn bị, đồng thời bơm turn giả để AI tự đọc lại ngắn gọn danh sách bằng giọng nói.

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

Giọng đọc cố định qua `speech_config` (`GEMINI_VOICE_NAME` trong `.env`, mặc định `"Kore"`) — trước đây không set nên Gemini Live tự chọn giọng ngẫu nhiên mỗi phiên. Danh sách 30 giọng có sẵn ghi trong `.env`; tài liệu chính thức không công bố giới tính/vùng miền từng giọng, chỉ có mô tả tính cách ngắn (Kore = "Firm").

System instruction có thêm đoạn dạy AI tự giới thiệu bản thân khi người dùng hỏi "bạn làm được gì"/"giúp gì được cho tôi" — trả lời tự nhiên, không liệt kê máy móc.

## Nghiệp vụ: đề nghị nộp hồ sơ (tool `propose_submit_procedure`)

Tool riêng (3 tool tổng cộng cùng `scan_form_fields`/`fill_form_fields`) — AI gọi khi nó thực sự có ý định đề nghị mở trang nộp hồ sơ. Description/system_instruction cố tình viết KHÔNG literal kiểu "gọi công cụ X ngay lúc nói câu Y" — từng khiến model native-audio "đọc ra" cú pháp gọi hàm thành lời/transcript thay vì thực sự trigger function-calling (bug quan sát được: AI nói ra nguyên văn `propose_submit_procedure{}` trong transcript thay vì gọi tool thật). Cách diễn đạt đúng: mô tả tool làm gì (hiện nút xác nhận), dặn AI nói tự nhiên rồi gọi tool "ở phía sau, không hiển thị trong lời nói" — giống cách `fill_form_fields`/`scan_form_fields` vốn không gặp lỗi này.

Tool có tham số optional `procedure_name` (STRING) — AI tự điền nếu biết chắc đang đề nghị nộp thủ tục nào từ ngữ cảnh hội thoại, để trống nếu không chắc. Tránh được việc phải gọi lại Gemini text (`_extract_procedure_name`) mỗi lần chỉ để so sánh tên.

`to_browser()` (`voice_provider.py`) gọi `await on_propose_submit(procedure_name)` (async, `main.py`) mỗi khi nhận tool-call:
```
NẾU session_state["submitted_procedure_name"] chưa có (chưa từng submit trong phiên)
  → cho phép luôn ({"ok": true})
NGƯỢC LẠI (đã submit 1 thủ tục rồi)
  NẾU AI không truyền procedure_name → tự trích qua _extract_procedure_name(history) (fallback,
    duy nhất chỗ tốn thêm 1 lần gọi AI trong luồng này)
  NẾU tên (AI truyền hoặc tự trích) khác submitted_procedure_name (so sánh case-insensitive)
    → cho phép ({"ok": true}) — đổi sang thủ tục khác vẫn đề nghị lại được bình thường
  NGƯỢC LẠI (cùng thủ tục hoặc không xác định được tên nào khác)
    → chặn ({"ok": false, "reason": "..."}) — AI được báo lý do, tự giải thích cho người dùng
```
`ok: true` mới set cờ `submit_proposed_this_turn`, cuối turn (`turn_complete`) gửi `show_submit_button` cho frontend nếu cờ bật VÀ không bị `suppress_show_submit` (turn hệ thống tự bơm). `submitted_procedure_name` (`session_state`) được set/ghi đè trong `_attempt_submit_procedure` (`main.py`) ngay sau `run_fixed_submit_flow` thành công — guard này chỉ chặn AI tự ý lặp lại đề nghị nộp cho ĐÚNG thủ tục vừa xử lý, không chặn hành động submit thật (nút bấm) hay việc chuyển sang thủ tục khác.

Thay thế hoàn toàn cơ chế cũ (string-match từ "nộp" trong `user_buffer`/`ai_buffer`) — cơ chế cũ từng gây bug: AI chỉ đang giải thích/liệt kê ("...thành phần cần nộp...") cũng vô tình bật đếm ngược tự động nộp 3s.

## Nghiệp vụ: quét form và tự điền (Gemini Live function calling)

Chỗ duy nhất dùng function calling thật của Gemini Live (`types.Tool`, 2 hàm: `scan_form_fields`, `fill_form_fields`) — khác `submit_procedure` vốn chỉ dựa vào nút bấm + so khớp keyword. Không còn nút bấm chọn cách điền — AI tự quyết định gọi `fill_form_fields` khi người dùng nói rõ ý muốn được điền hộ (vd "bạn điền giúp tôi đi").

```
KHI người dùng nói "quét trang giúp tôi"/"giờ tôi phải làm gì" (đã đăng nhập VNeID),
hoặc bấm nút "Quét trang" (#triggerScanBtn)
  → AI gọi (hoặc backend gọi thay khi là nút bấm) scan_form_fields
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
  → NẾU 1 trong các frame là tokhaidientu.moj.gov.vn (form hộ tịch điện tử — Bộ Tư pháp,
    khác hẳn combobox custom của dichvucong.gov.vn) → background.js route riêng qua
    scan_eform_fields (xem mục "Form hộ tịch điện tử" bên dưới), field_type đã có sẵn
    (t/s/d/a/c/r), KHÔNG cần AI đoán — dom_ai.eform_field_to_scan_field() convert format,
    chỉ gọi AI (analyze_form) cho phần HTML còn lại nếu có
  → lưu fields vào session_state (theo phiên) — GỘP cả 2 nguồn (eform_fields đã convert +
    AI-analyzed fields) vào cùng 1 danh sách; kết quả trả về Gemini qua tool_response
    khi do AI tự gọi, hoặc gói gọn trong 1 turn giả ngắn (chỉ số lượng + label, KHÔNG bơm
    nguyên field list dạng Python repr vào text — từng gây lỗi 1011 Internal error từ
    Gemini Live vì payload quá dài/sai định dạng) khi do nút bấm
  → AI tóm tắt ngắn gọn các trường cần điền cho người dùng nghe

KHI người dùng yêu cầu điền/tích BẤT KỲ trường nào — chung chung ("bạn điền giúp tôi
đi") HAY chỉ rõ 1 trường cụ thể ("tích trường nơi sinh là trong nước")
  → AI PHẢI gọi fill_form_fields (system_instruction cấm tuyệt đối tự nhận đã điền/tích
    khi chưa gọi tool — vì log thật từng thấy AI hallucinate xác nhận "Đã tích..." mà
    không hề gọi tool nào)
  → callback nhận kèm user_buffer (câu nói của turn hiện tại, CHƯA kịp flush vào history
    chính thức tại thời điểm tool-call xảy ra giữa turn) nối thêm vào transcript, để
    _handle_ai_fill_fields thấy được đúng yêu cầu vừa nói
  NẾU chưa có fields đã lưu (chưa từng scan_form_fields) → trả lỗi, AI báo cần quét trước
  NGƯỢC LẠI
    → nhờ text model so khớp fields + tỉnh/phường cố định + toàn bộ transcript
    → CHỈ lấy field XÁC ĐỊNH CHẮC CHẮN giá trị (không suy đoán/bịa CCCD, ngày sinh...)
    → gọi extension fill_field cho từng field theo field_type:
      combobox → bấm mở danh sách, chọn option khớp text (dichvucong.gov.vn)
      choice_option/r → simulateClick thẳng vào selector, không mở gì
      text/t → set qua native setter + fire input/change event (t: input con nằm
        trong custom element x-input, tìm querySelector('input') trước)
      d → x-date: value "dd/mm/yyyy" hoặc "yyyy-mm-dd", tách 3 ô con input[name$="-day"/
        "-month"/"-year"] set riêng từng ô
      a/s → x-select: vẫn phải bấm mở dropdown thật rồi chọn (không có input ẩn set trực
        tiếp được) — "a" chỉ khác "s" ở chỗ đã biết trước options thật qua API lúc quét,
        không tự đổi được cách điền
    → trả tool_response {ok, filled, remaining} — AI tự nói đã điền được gì, còn thiếu gì

## Nghiệp vụ: form hộ tịch điện tử (tokhaidientu.moj.gov.vn)

Thủ tục hộ tịch (kết hôn, khai sinh, khai tử...) trên dichvucong.gov.vn/*.moj.gov.vn mở
form thật trong 1 iframe cross-origin riêng biệt hoàn toàn — `<iframe id="eform" src=
"https://tokhaidientu.moj.gov.vn/e-form/<uuid>?KeyEformID=...&HoSoKTID=...&mode=lokify">`
— đây là 1 hệ thống độc lập của Bộ Tư pháp, không liên quan gì tới React app vỏ ngoài
(dichvucongnganhtuphap.moj.gov.vn), sinh động theo từng hồ sơ đã đăng nhập (không khảo
sát tĩnh được như dichvucong.gov.vn — mỗi phiên có KeyEformID/HoSoKTID riêng).

Cấu trúc DOM dùng custom element (không phải input/select chuẩn):
- `<x-input>`/`<x-input-number>` — text/số, input thật nằm bên trong (`querySelector('input')`)
- `<x-date>` — 3 input con riêng biệt `name="<Field>-day"`/`-month`/`-year` (maxlength 2/2/4)
  nối bằng dấu "/", KHÔNG phải 1 ô text đơn — đây là dạng "../../..." đã quan sát thực tế
- `<x-select>` — dropdown custom, không có input ẩn lộ giá trị ra DOM để set trực tiếp,
  luôn phải bấm mở (`[tabindex="0"]` bên trong) rồi chọn qua `waitForOptions`/simulateClick
- `<x-radio>` — nhóm `<label for="...">` + `<input type="checkbox">` ẩn, mỗi lựa chọn 1 field
- `<x-select-area>` — vùng phụ thuộc (conditional field), hiện/ẩn theo lựa chọn cha, hiện
  chưa xử lý riêng (không có trong danh sách quét)

`content_script.js` — `scanEformFields()`: quét toàn bộ 5 loại tag trên, gán
`data-scan-field-id`, trích `name` (định danh ngữ nghĩa tiếng Việt không dấu, vd
"HoTenBenNu", "NgaySinhBenNam" — hậu tố `_BenNu`/`_BenNam` phân biệt vai trò) và `title`
(heading `<strong>` gần nhất phía trước, vd "I. Thông tin bên nữ") qua
`findEformSectionTitle()` (duyệt ngược `previousElementSibling` rồi lên `parentElement`).
`dom_ai.py` — `eform_field_to_scan_field()`: convert sang format chung, `_EFORM_NAME_HINTS`
dịch tên field tiếng Việt không dấu phổ biến (khảo sát qua thủ tục "Đăng ký kết hôn")
sang mô tả dễ đọc, ghép với `title` thành label đầy đủ (vd "I. Thông tin bên nữ: Họ và
tên") — field lạ không có trong bảng giữ nguyên tên gốc.

**Danh mục dropdown công khai (API không cần đăng nhập)**: `POST https://tokhaidientu
.moj.gov.vn/api/eform-service/api/call-api` body `{eformId, apiId}` trả về options thật
(dân tộc, quốc tịch, tỉnh/thành, giới tính, loại giấy tờ tùy thân) — khảo sát thủ công 1
lần qua Network tab (không tự động hóa được, VNeID SSO có bot-detection tầng network
chặn cứng Playwright dù đã ẩn navigator.webdriver — ERR_CONNECTION_RESET tới endpoint
dạng /TSbd/<hash>, sau đó trang tự trigger "Pause in debugger" nếu có CDP debugger
client attach). `apiId` KHÔNG lộ ra DOM/attribute nào, chỉ thấy qua network lúc bấm mở
dropdown thật — `EFORM_KNOWN_APIID` (content_script.js) gắn cứng 5 giá trị đã xác nhận
cho thủ tục kết hôn (eformId=2056: GioiTinh=6772, QuocTich=6773, TinhThanh=6770,
DanToc=6779, LoaiGiayToDinhDanh=6778) — field khác thủ tục/field lạ không có trong bảng
tự fallback về bấm-mở-dropdown-thật (field_type "s" thay vì "a"). `eformId` (số nguyên,
khác KeyEformID dạng UUID trong URL) cũng không lộ ra DOM — `getEformId()` thử đọc
`window.eformId`/`window.__EFORM_ID__` (suy đoán, chưa xác nhận đúng), trả `null` nếu
không có thì luôn fallback bấm mở thật (an toàn, chỉ mất phần tối ưu "biết trước options").

Field type dùng ký hiệu ngắn (khác dichvucong.gov.vn dùng full-word): `t`=text, `s`=select
(chưa biết options, phải bấm mở), `d`=date (3 ô con), `a`=autocomplete (select đã biết
options thật qua API), `c`=checkbox, `r`=radio/choice_option (1 lựa chọn cụ thể).

  Cơ chế phát hiện AI nói dối: nếu turn_complete mà ai_buffer chứa "đã điền"/"đã tích"/
  "đã chọn" nhưng turn đó KHÔNG có tool-call fill_form_fields nào → log submit_error
  "ai_claimed_fill_without_tool_call" để phát hiện qua log (chưa có cách chặn cứng,
  chỉ ghi nhận để theo dõi tần suất).
```

Log chi tiết vào `data/logs/*.jsonl` cho từng bước, cả lúc bắt đầu lẫn khi xong (`scan_form_with_comboboxes_start/result`, `analyze_form_start`, `ai_fill_fields_start/decided`, `fill_field_start/done`).

`background.js` tự nhận diện tab để quét/điền qua `ensureControlledTab()` (không bắt buộc phải đi qua `open_url_and_scan`/`findOrCreateTab` trước) — nếu `controlledTabId` chưa có hoặc tab đó đã đóng, tự tìm tab đang active thuộc `*.gov.vn`, rồi tới tab bất kỳ thuộc `*.gov.vn`, mới báo lỗi nếu không có tab nào cả. Cần thiết cho nút "Quét trang" (không đi qua luồng nộp hồ sơ trước) hoạt động trên bất kỳ tab `*.gov.vn` nào đang mở sẵn.

**Bug đã biết, chưa fix**: combobox "Phường/Xã" là cascading dropdown, rỗng cho tới khi "Tỉnh/Thành phố" đã chọn — `scanFormWithComboboxes()` quét độc lập từng combobox nên dễ bỏ sót field Phường.

## Nghiệp vụ: thành phần hồ sơ cần chuẩn bị

`content_script.js` (`scanRequiredDocuments`) quét DOM thuần (không dùng AI) bảng dưới heading "Thành phần hồ sơ", gộp mọi bảng `<table>` con, mỗi dòng lấy `{name, qty}` giữ nguyên số lượng/loại thật (không lọc theo số lượng).

```
Tự động, ngay khi vào đúng trang chi tiết thủ tục (trước khi chọn Tỉnh/Phường):
  → required_documents.scan_raw(procedure_name, known_url)
    NẾU cache[procedure_name] đã có đầy đủ items → dùng luôn, KHÔNG gọi extension
    NGƯỢC LẠI → extension scan_required_documents, lưu vào cache
      (data/required_documents_cache.json, KEY = TÊN THỦ TỤC, không phải URL)
      dạng {"href": known_url, "items": [...], "summary": None} — KHÔNG gọi AI
      ở bước này

KHI người dùng bấm nút [Thành phần hồ sơ cần chuẩn bị] (#requiredDocsBtn):
  → required_documents.summarize(...) — gọi lại scan_raw() trước (tận dụng cache)
  NẾU cache đã có summary → trả thẳng, KHÔNG gọi AI lại
  NGƯỢC LẠI
    → nhờ text model tóm tắt items dài dòng (giữ rõ số lượng/loại, bỏ trích dẫn luật)
    → cập nhật cache[procedure_name]["summary"] = [...] — GIỮ NGUYÊN "items"
      (không xóa bản đầy đủ sau khi có tóm tắt — cần cho trang "Thành phần hồ sơ"
      liệt kê toàn văn, xem mục bên dưới)
  → hiện list card (renderRequiredDocumentsCard) + bơm turn giả để AI tự đọc lại
    ngắn gọn danh sách bằng giọng nói
```

Key đổi từ URL sang tên thủ tục (`scripts/migrate_required_documents_cache.py`, chạy 1 lần, join qua `procedure_flat_index.json`) để 2 file `procedure_flat_index.json`/`required_documents_cache.json` cùng định danh 1 thủ tục theo tên — trước đây khác kiểu key (name vs URL) gây khó tra cứu chéo. `app/required_documents.py`: `fallback_key` (chính là `procedure_name`) giờ luôn là cache key thật, `known_url` chỉ lưu vào field `href` bên trong entry.

Đã khảo sát trước toàn bộ 319 thủ tục bằng Playwright (`scripts/survey_required_documents.py`, chạy ngoại tuyến, hỗ trợ `SURVEY_LIMIT` để test nhỏ) để cache có sẵn raw cho hầu hết thủ tục, tránh phải quét DOM qua extension mỗi lần. Script này vẫn key theo URL khi ghi — cần chạy `migrate_required_documents_cache.py` lại nếu khảo sát lại từ đầu.

Playwright là dev-dependency thường trực của dự án (không gỡ sau khi dùng — dùng lại để khảo sát cấu trúc trang thật trước khi code).

## Giao diện extension (Chrome, Manifest V3)

Popup và Options hiện trạng thái kết nối backend, cho sửa port, nút test kết nối. `background.js` tự reconnect khi mất kết nối.

Trang chính (`static/index.html`) cũng tự hiện trạng thái kết nối extension bằng 1 div trong `#idleCard` (chấm tròn + nhãn "Kết nối: OK"/"Kết nối: Fail") — gọi `GET /extension/status` khi load và poll lại mỗi 5 giây.

**Ping/pong 2 chiều để tránh kết nối "chết âm thầm"**: `background.js` là MV3 service worker, bị Chrome tự unload sau ~30s không hoạt động — làm mất biến `socket` module-level dù WebSocket TCP có thể chưa kịp báo đóng, khiến `/extension/status` (REST, luôn trả lời được) báo `connected: true` trong khi `send_command` thật lại `ExtensionNotConnected` vì socket đã chết. Khắc phục 2 lớp: `chrome.alarms` chu kỳ 0.5 phút (mức tối thiểu Chrome cho phép) để tự đánh thức worker và tự `connect()` lại nếu socket mất; đồng thời ping/pong qua chính WebSocket mỗi 15s (`background.js` gửi `{type: ping}`, backend `/extension` trả `{type: pong}`) — nếu backend không nhận được gì (kể cả ping) trong 40s (`_EXTENSION_PING_TIMEOUT`, `app/main.py`) thì tự coi socket chết và `unregister()`, để `is_connected` phản ánh đúng trạng thái thay vì báo OK giả.

## Rủi ro / giới hạn đã biết

- `run_fixed_submit_flow` dùng bản đồ thao tác cố định — nếu dichvucong.gov.vn đổi giao diện sẽ hỏng, cần khảo sát lại thủ công.
- Tỉnh/phường nộp hồ sơ cố định trong code (`SUBMIT_PROVINCE`/`SUBMIT_WARD`) — phường có thể không tồn tại cho một số thủ tục hiếm.
- Model free tier (Gemini, OpenRouter `:free`) đều có rate-limit.
- `ExtensionManager` (`app/extension_bridge.py`) chỉ giữ 1 socket `/extension` duy nhất — nhiều người dùng chung 1 backend qua ngrok mà mỗi người tự cài extension riêng sẽ ghi đè lẫn nhau (người sau connect làm mất kết nối người trước). Đúng model hiện tại: 1 backend điều khiển 1 trình duyệt/extension tại 1 thời điểm; `/ws` (giọng nói) thì hỗ trợ nhiều phiên đồng thời qua `MAX_CONCURRENT_SESSIONS` nhưng vẫn dùng chung 1 extension đó.

## Bảo mật khi expose ra ngoài (ngrok/LAN)

**Auth người dùng thường (JWT theo username)**: `app/auth.py` quản lý danh sách username hợp lệ (`data/allowed_users.json`, gitignore — key `usernames: [...]`, admin thêm/xóa qua `/admin/users`) và JWT (`PyJWT`, thuật toán HS256, ký bằng `JWT_SECRET` trong `.env`). Token **không có `exp`** (không tự hết hạn theo thời gian — đăng nhập 1 lần là xong); `verify_token` luôn đối chiếu lại `is_valid_username()` trên danh sách hiện tại chứ không chỉ tin chữ ký, nên admin xóa username khỏi `/admin.html` là thu hồi được token cũ ngay lập tức, không cần cơ chế blacklist riêng. `JWT_SECRET` để rỗng thì tự sinh ngẫu nhiên lúc khởi động — **PHẢI set cố định trong `.env`** (không để rỗng lúc dev) vì mỗi lần backend restart (kể cả `--reload` tự động khi sửa code Python) sẽ sinh secret mới, làm mọi token cũ mất hiệu lực ngay — từng gây bug "hết token liên tục" khi dev.

Luồng đăng nhập:
```
Extension (popup.html/popup.js): nhập "Địa chỉ backend" (http/https, gõ tay 1 lần,
lưu chrome.storage.local key backendHttpUrl) + "Username" → bấm Đăng nhập
  → POST {backendHttpUrl}/auth/login {username}
  → backend check auth.is_valid_username() → không hợp lệ: 401
  → hợp lệ: trả {token (JWT), web_link, extension_url}
    (web_link/extension_url tự ghép host+scheme từ chính header request tới —
    không cần cấu hình domain ngrok thủ công)
  → popup lưu extension_url + username vào chrome.storage.local (key backendUrl,
    username — dùng luôn cho kết nối /extension của chính extension này), báo
    background.js reconnect
  → popup hiện web_link kèm nút Sao chép — người dùng bấm/copy để mở trang web
```
Popup tự đọc lại `username`/`webLink` đã lưu mỗi lần mở (không cần đăng nhập lại để thấy đang là ai) — ô Username tự điền sẵn, `#loginStatus` hiện "Đang đăng nhập: <username>" nếu đã có link lưu sẵn.

`static/app.js` đọc JWT từ query param `?token=...` trên URL khi mở lần đầu (khớp `web_link`), lưu `localStorage` (key `authToken`, per-origin), tự gắn vào `/ws`.

`/ws` và `/extension` verify JWT qua query param `?token=...` (`auth.verify_token`, đóng kết nối code 4401 nếu thiếu/sai/username đã bị admin xóa) — **luôn bắt buộc**, không có cờ tắt như cơ chế token tĩnh trước đây (khác `ADMIN_PASSWORD`, không để rỗng được vì JWT_SECRET luôn có giá trị dù không set trong `.env`). Dev localhost vẫn cần đăng nhập qua popup extension (trỏ `backendHttpUrl` về `http://localhost:8000`) trước khi mở được trang web hoặc dùng extension — nhưng chỉ cần làm 1 lần, danh sách username mặc định rỗng nên phải tự thêm ít nhất 1 username qua `/admin/users` trước khi đăng nhập được lần đầu.

**Auth admin (tách riêng, không liên quan JWT)**: `ADMIN_PASSWORD` (`.env`, để rỗng = khóa hẳn, không thao tác được) bảo vệ:
- `static/admin.html`/`admin.js` — quản lý danh sách username (`POST /admin/login` xem danh sách, `POST /admin/users` thêm, `DELETE /admin/users/{username}` xóa). Không lưu session, chỉ giữ password tạm trong biến JS của trang (mất khi tải lại).
- `static/manage.html`/`manage.js` — quản lý dữ liệu PDF/thủ tục (`/upload-pdf`, `DELETE /procedures/{slug}`), yêu cầu header `X-Admin-Password`. Trang tự `prompt()` hỏi mật khẩu lần đầu, giữ trong `sessionStorage` (mất khi đóng tab) — sai thì tự xóa để hỏi lại ở thao tác kế tiếp.

Cả 2 trang admin có link công khai ở footer trang chính (`static/index.html`, class `.footer-admin-links`) — chấp nhận được vì cả 2 vẫn yêu cầu `ADMIN_PASSWORD` mới thao tác được, hiện link chỉ lộ sự tồn tại của trang chứ không lộ quyền truy cập.

Khác:
- `MAX_CONCURRENT_SESSIONS` (`.env`) — giới hạn số phiên `/ws` (giọng nói) đồng thời, mặc định 1. Phiên vượt giới hạn bị từ chối lịch sự (không đóng đột ngột).
- Không có rate-limit theo IP/thời gian (cân nhắc rồi bỏ — nhóm dùng nhỏ, tin cậy, và IP qua NAT/ngrok dễ trùng nhau gây chặn nhầm chính chủ). Nếu mở rộng cho nhóm lớn hơn hoặc công khai, cần bổ sung lại.
- `FRONTEND_ORIGIN` (`.env`) dùng cho CORS — chỉ chặn domain lạ gọi API từ trình duyệt khác, không ảnh hưởng trang chính (cùng origin luôn gọi được dù giá trị đúng/sai).
- Deploy qua ngrok/reverse proxy cần chạy uvicorn kèm `--proxy-headers` (đã set trong `Dockerfile`) để `/auth/login` đọc đúng `https://`/`wss://` + domain ngrok thật từ `X-Forwarded-Proto`/`Host` thay vì `http://0.0.0.0`.
- `manifest.json` `host_permissions` thêm `http://*/*`, `https://*/*` (ngoài `https://*.gov.vn/*` sẵn có) — popup cần `fetch()` tới `backendHttpUrl` là domain bất kỳ (ngrok đổi mỗi lần restart nếu dùng free tier), không khai báo trước được.
