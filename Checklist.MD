# Checklist — Trợ lý giọng nói AI (Dịch vụ công)

- Quy tắc AI:
+ Không viết comment hay docstring vào code vì không cần thiết
+ Không tự call API để test vì tốn token
+ Không tự viết thêm log vào trong checklist vì không cần thiết
+ Không cần phải check syntax code python, html, css hay js đâu vì hầu hết bạn làm đúng

## Cấu trúc dự án

```
app/                        Backend (FastAPI)
  main.py                   /ws (voice), REST tra cứu/quản lý PDF/thủ tục
  voice_provider.py         Toàn bộ logic Gemini Live (session, system_instruction, 2 tool function calling)
  procedure_index.py        Tra cứu thủ tục qua index tĩnh (IDF-weighted keyword overlap)
  required_documents.py     Đọc/tóm tắt thành phần hồ sơ từ cache tĩnh (không quét DOM runtime)
  text_model.py             Lớp trừu tượng gọi text model (Gemini/Ollama/OpenAI-compatible)
  conversation_log.py       Ghi log JSONL từng phiên vào data/logs/
  rag.py                    RAG keyword 2 tầng cho trang quản lý (không liên quan voice)
scripts/                    Công cụ one-off (Playwright, không phải runtime app)
  procedure_keywords.py     87 từ khóa cốt lõi để khảo sát
  build_procedure_index.py  Khảo sát Playwright → data/procedure_index.json (grouped, tạm)
  flatten_procedure_index.py  Gộp phẳng → data/procedure_flat_index.json (dùng thật)
  survey_required_documents.py  Khảo sát Playwright thành phần hồ sơ → required_documents_cache.json
  refresh_all.py            Chạy tay gộp cả 3 script trên theo đúng thứ tự, dùng khi muốn làm mới dữ liệu
static/                     Frontend (vanilla JS, không framework)
  index.html/app.js/styles.css   Trang trợ lý giọng nói chính (public, không cần đăng nhập)
  admin.html/admin.js       Xác nhận mật khẩu quản trị (ADMIN_PASSWORD), dẫn sang manage.html
  manage.html/manage.js/manage.css  Trang quản lý PDF/thủ tục (RAG)
  required-documents.html/js  Trang tra cứu thành phần hồ sơ bằng tay (không qua voice)
  worklet.js                AudioWorklet xử lý mic 16kHz PCM
data/
  procedure_flat_index.json  319 thủ tục {name, href} — index tĩnh dùng runtime
  required_documents_cache.json  Thành phần hồ sơ theo tên thủ tục — cache tĩnh dùng runtime
  logs/*.jsonl               Log từng phiên (gitignore)
  pdfs/, index.json, procedures/*.json   Dữ liệu RAG trang quản lý
```

## Công nghệ dùng

- **Backend**: Python, FastAPI (WebSocket + REST), `uv` quản lý dependency.
- **Giọng nói**: Google Gemini Live API (`google-genai` SDK) — model `gemini-2.5-flash-native-audio-latest`, audio 2 chiều qua `session.receive()`/`send_realtime_input()`, transcript qua `AudioTranscriptionConfig`, function calling qua `types.Tool` (2 tool: `show_required_documents`, `show_submission_steps`).
- **Text/reasoning thuần**: trừu tượng qua `text_model.py`, `TEXT_MODEL_PROVIDER=gemini` cố định (Gemini SDK trực tiếp) — code vẫn còn nhánh OpenAI-compatible (`httpx`) cho Ollama/OpenRouter nhưng không dùng, `.env` đã bỏ các biến `TEXT_MODEL_BASE_URL/NAME/API_KEY`, `OLLAMA_*` liên quan.
- **Tra cứu dữ liệu**: hoàn toàn tĩnh — `data/procedure_flat_index.json` (319 thủ tục + href) và `data/required_documents_cache.json` (thành phần hồ sơ), khảo sát trước bằng Playwright (dev-dependency, `scripts/refresh_all.py` chạy tay để làm mới). Không có bất kỳ điều khiển trình duyệt/extension nào ở runtime.
- **Frontend**: vanilla JS, AudioWorklet resample/encode PCM 16kHz gửi lên, giải mã PCM 24kHz nhận về bằng Web Audio API thuần. Không có bước tự mở/tự điều khiển tab nào — mọi liên kết ra trang ngoài (nộp hồ sơ) đều là `<a target="_blank">` để người dùng tự bấm.
- **Không dùng**: embedding/vector DB (RAG chỉ keyword-match), JWT/đăng nhập người dùng thường (trang chính public hoàn toàn), Chrome extension.

## Trợ lý giọng nói

`/ws` (`app/main.py`) là lớp mỏng: nhận kết nối, giới hạn `MAX_CONCURRENT_SESSIONS` phiên hoạt động cùng lúc (từ chối lịch sự nếu vượt), giao hết việc cho `voice_provider.py`. Không còn xác thực (public, ai vào trang cũng dùng được ngay, không cần đăng nhập).

Push-to-talk: nút "Nhấn để nói" hoặc phím Enter/Space để bắt đầu, bấm/phím lại để kết thúc (`e.repeat` guard). `automatic_activity_detection` tắt hẳn, client tự gửi `activity_start`/`activity_end`; audio chỉ gửi khi đang ở trạng thái "đang nói".

Gemini Live không tự khởi phát turn đầu nếu không có input — bật `AUTO_GREET=true` (`.env`) thì `run_voice_session` tự bơm 1 turn giả silent ngay khi mở session để AI tự nói câu chào theo `system_instruction` (mặc định tắt).

Frontend hiện transcript dạng chat real-time, sóng âm theo trạng thái nói/nghe, bong bóng "đang gõ" khi AI xử lý. Audio phát theo chunk, buffer đệm 120ms đầu mỗi lượt.

## Nghiệp vụ: 2 tool tra cứu (Gemini Live function calling)

Toàn bộ nghiệp vụ "làm việc" của AI giờ chỉ còn 2 tool tra cứu thuần — không có bất kỳ hành động điều khiển trình duyệt nào. Cả 2 đều dùng chung bước xác định thủ tục (`app/main.py::_resolve_procedure`): `procedure_index.lookup_candidates()` (so khớp overlap từ khóa IDF trên `procedure_flat_index.json`) → nếu nhiều candidate thì nhờ text model chọn đúng 1 (`procedure_index.pick_variant_href`) → suy ra `href` chi tiết thật trên dichvucong.gov.vn. Nếu không tra được thủ tục nào, trả về tên gốc và `href=None`.

**`show_required_documents(procedure_name)`** — AI gọi khi người dùng hỏi cần chuẩn bị giấy tờ gì:
```
_resolve_procedure(procedure_name) → resolved_name, known_url
required_documents.summarize(resolved_name, known_url)
  NẾU cache[resolved_name] không tồn tại → trả rỗng (chưa khảo sát tới thủ tục này)
  NẾU đã có summary → dùng luôn
  NGƯỢC LẠI → nhờ text model tóm tắt items (giữ số lượng/loại, bỏ trích dẫn luật), cache lại
→ gửi message "procedure_info" (data đầy đủ: procedure_name, href, items, summary) cho frontend render card
→ trả tool_response ngắn gọn (vài ví dụ + tổng số lượng) cho Gemini Live đọc, không phải toàn bộ danh sách
```

**`show_submission_steps(procedure_name)`** — AI gọi khi người dùng hỏi nộp hồ sơ ở đâu/nộp thế nào:
```
_resolve_procedure(procedure_name) → resolved_name, known_url
→ gửi message "submission_steps" (data: procedure_name, href, 4 bước cố định viết cứng trong
  main.py::_SUBMISSION_STEPS — xác định thủ tục, chuẩn bị hồ sơ, nộp trực tuyến tại link chính
  thức (VNeID), theo dõi kết quả) cho frontend render card kèm nút "Mở nơi nộp hồ sơ thủ tục"
  (href thật, target="_blank" — KHÔNG tự mở/điều khiển gì, người dùng tự bấm)
→ trả tool_response {ok, procedure_name, has_link, steps_count}
```

Không có khái niệm "phiên đã submit 1 thủ tục" hay guard chặn gọi lại — 2 tool này là tra cứu thuần túy, gọi lại bao nhiêu lần cũng được.

`system_instruction` (`voice_provider.py`): mở đầu bằng câu "Tôi là trợ lý giọng nói ảo của Phường Yên Sở, bạn muốn hỗ trợ thủ tục hành chính nào?"; biết sẵn địa chỉ Yên Sở/Hà Nội (`DEFAULT_WARD`/`DEFAULT_PROVINCE`, chỉ còn ý nghĩa trả lời câu hỏi địa chỉ, không dùng để tự điền form nữa); nếu chưa rõ thủ tục thì hỏi lại trước; dạy AI tự giới thiệu bản thân khi được hỏi "bạn làm được gì"; cấm tự nhận đã nộp/đã điền hộ gì — hệ thống không tự động thao tác trên trang nộp hồ sơ.

Giọng đọc cố định qua `speech_config` (`GEMINI_VOICE_NAME` trong `.env`, mặc định `"Kore"`).

## Tách "làm việc" khỏi "nói chuyện"

Tác vụ text thuần (chọn variant thủ tục, tóm tắt thành phần hồ sơ) đi qua `app/text_model.py`, tách khỏi Gemini Live nhưng vẫn cùng dùng `GEMINI_API_KEY`/`GEMINI_TEXT_MODEL`. `TEXT_MODEL_PROVIDER=gemini` cố định — nhánh OpenAI-compatible (`httpx`, dùng cho Ollama/OpenRouter trước đây) vẫn còn trong code nhưng không còn biến `.env` tương ứng, coi như tắt.

## Tra cứu thủ tục qua RAG (trang quản lý)

`app/rag.py` tìm keyword 2 tầng (chọn thủ tục → chọn mục nội dung) trên `data/index.json`/`data/procedures/*.json`, không dùng embedding. `build_index.py` dựng lại index từ PDF. `static/manage.html` quản lý upload/xóa PDF, tự rebuild index. Không nối vào hội thoại giọng nói.

## Màn hình: chờ (`#idleCard`)

Nút "Bắt đầu hỗ trợ" (`#startBtn`) → mở `/ws`, chuyển sang màn hình chat. Link "Tra cứu thành phần hồ sơ" mở trang tra cứu bằng tay riêng (`required-documents.html`). Link "Quản trị"/"Quản lý dữ liệu thủ tục" hiện ở footer (công khai, xem mục "Bảo mật khi expose ra ngoài").

## Màn hình: chat (`#chatCard`)

Luôn có: sóng âm + dòng trạng thái (`#status`), khung transcript (`#chatLog`), nút "Nhấn để nói"/"Đang nói..." (`#talkBtn`, push-to-talk — phím Enter/Space cũng bật/tắt được, có `e.repeat` guard), nút "Kết thúc hỗ trợ" (`#stopBtn`).

Khi AI gọi tool `show_required_documents`, backend gửi message `procedure_info` → frontend render card (`renderRequiredDocumentsCard`) liệt kê danh sách giấy tờ (tóm tắt nếu có, toàn văn nếu chưa) kèm link "Xem chi tiết trên dichvucong.gov.vn" nếu có href.

Khi AI gọi tool `show_submission_steps`, backend gửi message `submission_steps` → frontend render card (`renderSubmissionStepsCard`) liệt kê 4 bước dạng danh sách có số thứ tự, kèm nút "Mở nơi nộp hồ sơ thủ tục" (`target="_blank"`, chỉ hiện nếu tra được href) hoặc ghi chú nếu chưa tra được link.

## Nghiệp vụ: thành phần hồ sơ cần chuẩn bị

Dữ liệu lấy thẳng từ `data/required_documents_cache.json` (khảo sát trước bằng Playwright, key = TÊN THỦ TỤC, giá trị `{href, items: [{name, qty}], summary}`). `app/required_documents.py`:
- `get_cached(name)` — đọc thẳng, dùng cho endpoint REST `/required-documents/{name}`.
- `summarize(name, known_url)` — nếu cache đã có `summary` thì dùng luôn; nếu chưa, nhờ text model tóm tắt `items` (giữ số lượng/loại, bỏ trích dẫn luật) rồi ghi lại cache (giữ nguyên `items` gốc song song bản tóm tắt).
- Nếu thủ tục không có trong cache (chưa từng khảo sát) → trả rỗng, không có cơ chế quét runtime nào để bù — chỉ có thể bổ sung bằng cách chạy lại `scripts/refresh_all.py`.

Trang `static/required-documents.html`/`.js` (tra cứu độc lập không qua voice, gọi thẳng `/required-documents` và `/required-documents/{name}`) không đổi — vẫn hữu ích như công cụ tra cứu nhanh bằng tay.

## Làm mới dữ liệu tĩnh (`scripts/refresh_all.py`)

Không có scheduler/tiến trình nền nào chạy tự động trong server — làm mới dữ liệu là thao tác chạy tay lúc dev, khi cần thì gọi `uv run scripts/refresh_all.py`, gộp tuần tự 3 bước có sẵn:
1. `build_procedure_index.py` — khảo sát lại theo `scripts/procedure_keywords.py` (87 từ khóa) → `data/procedure_index.json` (grouped, tạm).
2. `flatten_procedure_index.py` — gộp phẳng, khử trùng href → `data/procedure_flat_index.json` (dùng thật ở runtime).
3. `survey_required_documents.py` — khảo sát thành phần hồ sơ theo index vừa cập nhật → `data/required_documents_cache.json` (hỗ trợ resume, bỏ qua thủ tục đã có cache).

Sau khi chạy xong cần khởi động lại backend để `procedure_index`/`required_documents` nạp lại dữ liệu mới (module cache trong RAM, không tự đọc lại đĩa mỗi request — trừ `required_documents.list_all()` dùng cho REST list luôn đọc lại đĩa). Playwright là dev-dependency thường trực của dự án (không gỡ sau khi dùng).

## Rủi ro / giới hạn đã biết

- Dữ liệu thành phần hồ sơ/href hoàn toàn tĩnh — nếu dichvucong.gov.vn đổi cấu trúc trang hoặc thêm thủ tục mới, cần chạy lại `scripts/refresh_all.py` thủ công mới cập nhật được, không có cơ chế tự phát hiện thay đổi.
- Model free tier (Gemini) có rate-limit.
- Không có cơ chế nào đảm bảo href trong `procedure_flat_index.json` còn hợp lệ (thủ tục có thể bị gỡ/đổi id trên dichvucong.gov.vn) — nút "Mở nơi nộp hồ sơ thủ tục" có thể dẫn tới trang lỗi nếu dữ liệu đã cũ.

## Bảo mật khi expose ra ngoài (ngrok/LAN)

Trang chính (`/`, `/ws`) hoàn toàn public — không cần đăng nhập, ai truy cập link cũng dùng được ngay (đúng yêu cầu "không cần đăng nhập, không cài extension phức tạp").

**Auth admin** (`ADMIN_PASSWORD`, `.env`, để rỗng = khóa hẳn, không thao tác được) bảo vệ:
- `static/admin.html`/`admin.js` — chỉ còn xác nhận mật khẩu (`POST /admin/login`), không lưu session, dẫn link sang `manage.html`.
- `static/manage.html`/`manage.js` — quản lý dữ liệu PDF/thủ tục (`/upload-pdf`, `DELETE /procedures/{slug}`), yêu cầu header `X-Admin-Password`. Trang tự `prompt()` hỏi mật khẩu lần đầu, giữ trong `sessionStorage` (mất khi đóng tab) — sai thì tự xóa để hỏi lại ở thao tác kế tiếp.

Cả 2 trang admin có link công khai ở footer trang chính (`static/index.html`, class `.footer-admin-links`) — chấp nhận được vì cả 2 vẫn yêu cầu `ADMIN_PASSWORD` mới thao tác được.

Khác:
- `MAX_CONCURRENT_SESSIONS` (`.env`) — giới hạn số phiên `/ws` (giọng nói) đồng thời, mặc định 1. Phiên vượt giới hạn bị từ chối lịch sự (message `session_error`, không đóng đột ngột).
- Không có rate-limit theo IP/thời gian, không JWT — trang public hoàn toàn theo đúng yêu cầu đơn giản hóa.
- `FRONTEND_ORIGIN` (`.env`) dùng cho CORS — chỉ chặn domain lạ gọi API từ trình duyệt khác, không ảnh hưởng trang chính (cùng origin luôn gọi được dù giá trị đúng/sai).
- Deploy qua ngrok/reverse proxy cần chạy uvicorn kèm `--proxy-headers` (vd `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`) để `/admin/login` đọc đúng `https://`/domain thật từ header thay vì `http://0.0.0.0`.
