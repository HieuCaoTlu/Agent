# Checklist — Trợ lý giọng nói AI (MVP siêu gọn)
- Quy cho tắc AI:
+ Không viết comment hay docstring vào code vì không cần thiết
+ Không tự call API để test vì tốn token
+ Không tự viết thêm log vào trong checklist vì không cần thiết
+ KHông cần phải check syntax code python, html, css hay js đâu vì hầu hết bạn làm đúng

- [x] Khởi tạo `pyproject.toml` (uv) — FastAPI, uvicorn, google-genai, python-dotenv
- [x] Backend: `app/main.py` — WebSocket proxy `/ws` nối Gemini Live API
- [x] Frontend: HTML/CSS/JS tĩnh — nút "Bắt đầu hỗ trợ" / "Kết thúc hỗ trợ"
- [x] Nút bắt đầu: xin quyền micro, mở WebSocket, stream audio
- [x] Backend chuyển tiếp audio hai chiều với Gemini Live API
- [x] Frontend phát audio trả lời của AI streaming
- [x] Nút kết thúc: đóng kết nối, dừng micro, AI ngừng nói
- [x] Chạy thử thực tế qua trình duyệt (cần bạn tự thử)

## Phần J: RAG (đã tắt khỏi luồng voice, giữ lại cho trang quản lý)

- [x] `app/rag.py`, `build_index.py` — RAG keyword-based 2 tầng
- [x] `static/manage.html/.js/.css` — trang quản lý PDF nguồn riêng
- [x] Revert tool-calling khỏi Gemini Live (giữ RAG chỉ cho trang quản lý)
- [x] `app/conversation_log.py` — log JSONL, session_id 6 ký tự, timestamp gọn
- [x] VAD (`RealtimeInputConfig`) nới sensitivity

## Phần K: Tự động nộp hồ sơ qua Chrome extension

- [x] `app/extension_bridge.py` — quản lý kết nối WebSocket extension
- [x] `app/dom_ai.py` — Gemini text-model + structured output tìm selector
- [x] `app/main.py`: endpoint `/extension`, `_extract_procedure_name`, `_handle_submit_procedure`
- [x] `static/index.html`/`app.js`: nút `#submitBtn`
- [x] `extension/` — Chrome Manifest V3 (background/content_script/options)
- [x] Verify import + server + endpoint `/extension` chạy được
- [ ] Test full flow thật qua trình duyệt (chưa test end-to-end)
- [ ] Theo dõi rủi ro Gemini chọn nhầm "Nộp trực tuyến" thay vì "Nộp hồ sơ"

## Phần L: Dọn dẹp

- [x] Xóa toàn bộ comment trong code (Python/JS/HTML/CSS)

## Phần M: Sửa nút nộp hiện chậm + kiểm tra kết nối extension

- [x] `app/main.py`: bắt từ khóa "nộp" ngay khi có transcript (không đợi `turn_complete`), tránh nút hiện chậm sau khi AI nói xong cả câu — thêm cờ `submit_hint_shown` reset mỗi turn để không gửi lặp `show_submit_button`
- [x] `extension/background.js`: theo dõi `connectionState`/`lastError`, phát broadcast `connection_state` khi socket đổi trạng thái; thêm handler `get_status` và `test_connection` (kết nối thử 1 URL trong 5s, không ảnh hưởng socket chính đang dùng)
- [x] `extension/options.html`/`options.js`: thêm khối trạng thái kết nối trực tiếp (chấm màu + nhãn + chi tiết lỗi) và nút "Kiểm tra kết nối" test URL đang gõ trước khi lưu; validate URL phải `ws://`/`wss://` trước khi lưu hoặc test
- Quyết định tự động (theo quy tắc autonomous-decision): không thêm endpoint HTTP backend để check trạng thái vì `background.js` đã tự biết trạng thái socket của chính nó — đủ để hiển thị, không cần round-trip qua server
- [x] `extension/popup.html` + `manifest.json` (`action.default_popup`): bấm icon extension trên toolbar giờ hiện popup trạng thái kết nối + sửa port ngay, không cần vào Tùy chọn (`options.html` giữ nguyên, dùng chung `options.js` vì cùng id phần tử)
- [ ] Test thật qua trình duyệt: xác nhận nút nộp hiện ngay khi nói "nộp", và popup icon báo đúng lỗi khi sai port

## Phần N: Sửa treo im lặng khi thao tác nộp hồ sơ lỗi + thêm log thao tác

- [x] Bug tìm ra: sau khi search xong, flow "treo" vì content script trả `{error: ...}` (vd không tìm thấy selector kết quả) nhưng `extension_bridge.send_command` trả nguyên dict đó thay vì raise, code sau đó `KeyError` không bắt được → task chết âm thầm, không có gì gửi về UI
- [x] `app/extension_bridge.py`: thêm `ExtensionCommandError`, `send_command` giờ raise khi response chứa `error`
- [x] `app/main.py`: `_handle_submit_procedure` bắt thêm `ExtensionCommandError` và `Exception` catch-all, luôn gửi `submit_procedure_error` về UI thay vì treo im lặng
- [x] `app/conversation_log.py`: thêm `submit_action`/`submit_error` — log từng bước (extract tên thủ tục, tìm ô search, chọn kết quả, tìm tỉnh/phường/nút nộp...) vào cùng file JSONL để debug được chỗ treo
- [x] `static/styles.css`: `#submitBtn` thêm `margin-top: 12px`
- [x] Test thật: log xác nhận đúng luồng trên — `find_search_box` + `fill_and_search_done` chạy được, nhưng `pick_search_result` trả `result_selector: null`

## Phần O: Sửa pick_search_result trả null do scan quá sớm

- [x] Nguyên nhân: search trên dichvucong.gov.vn là AJAX/SPA (không phải full page navigation), nên `chrome.tabs.onUpdated` không bắn `status: complete` sau `fill_and_search` — `scan_current_page` chạy ngay lập tức, HTML gửi cho Gemini chưa có danh sách kết quả (chưa kịp render) → Gemini trả null đúng logic
- [x] `app/main.py`: thêm `asyncio.sleep(2.0)` trước lần scan đầu sau `fill_and_search`; nếu vẫn null thì đợi thêm `2.5s` rồi scan+pick lại lần 2 (log `pick_search_result_retry`/`pick_search_result_retry_result`)
- [x] Test thật lại: log xác nhận `pick_search_result` trả đúng selector, `click_search_result_done` thành công

## Phần P: Viết lại chọn tỉnh/phường cho custom combobox (không phải <select> thật)

- [x] Bug tìm ra qua log: `find_location_and_submit` coi tỉnh/phường là `<select>` gốc (`selectEl.options`), nhưng dichvucong.gov.vn dùng combobox tùy chỉnh — bấm `button` mới mở `ul[role="listbox"] > li[role="option"]`, không có `.options` → `TypeError: selectEl.options is not iterable`
- [x] Phường phụ thuộc tỉnh (chỉ render sau khi chọn tỉnh xong) nên tách thành 2 bước tuần tự, không thể tìm cả hai cùng lúc như trước
- [x] `extension/content_script.js`: bỏ `selectOptionByText`/`fillLocationAndSubmit` (dead code cho `<select>` gốc); thêm `waitForOptions` (poll `ul[role="listbox"] li[role="option"]` tối đa 4s) + `selectComboboxOption` (click button mở dropdown → đợi option render → click li khớp text, ưu tiên khớp chính xác rồi tới includes); listener đổi thành IIFE async để hỗ trợ action bất đồng bộ
- [x] `extension/background.js`: đổi command `fill_location_and_submit` thành `select_combobox_option` (button_selector, text)
- [x] `app/dom_ai.py`: tách `find_location_and_submit` thành `find_province_button` (chỉ tìm nút mở tỉnh) và `find_ward_button_and_submit` (tìm nút mở phường + nút "Nộp hồ sơ", chạy sau khi tỉnh đã chọn và trang đã re-render)
- [x] `app/main.py`: flow mới — chọn tỉnh → sleep 1.5s → scan lại → tìm nút phường+nộp → chọn phường → sleep 0.5s → click nút nộp; mỗi bước đều log qua `submit_action`/`submit_error`
- [x] Test thật lại: xác nhận chọn được đúng tỉnh "Hà Nội", phường "Yên Sở" hiện ra sau đó, và bấm được nút "Nộp hồ sơ" cuối cùng — nhưng đã bị thay hoàn toàn bởi Phần Q vì gặp quota Gemini free-tier (20 request/ngày/model) và người dùng yêu cầu bỏ hẳn cách "quét HTML bằng Gemini mỗi lần" cho bước này

## Phần Q: Bỏ Gemini cho bước chọn tỉnh/phường/nộp — dùng bản đồ thao tác cố định đã khảo sát bằng Playwright thật

- Bối cảnh: gặp lỗi `429 RESOURCE_EXHAUSTED` (hết quota free-tier Gemini 20 request/ngày/model) khi test nhiều lần trong ngày. Người dùng chỉ ra: bước chọn tỉnh/phường/nộp hồ sơ luôn giống hệt nhau giữa mọi thủ tục hành chính (chỉ khác bước tìm tên hồ sơ) → không cần Gemini quét HTML mỗi lần cho bước này, chỉ cần khảo sát 1 lần rồi ghi cứng thao tác
- [x] Cài Playwright làm **dev-dependency tạm thời** (`uv add --dev playwright` + `playwright install chromium`), tự dùng để mở trình duyệt thật (có head, `headless=False`) khảo sát toàn bộ luồng nộp hồ sơ "Đăng ký kết hôn" trên dichvucong.gov.vn — không cần hỏi người dùng, tự test lặp lại đến khi chạy đúng
- [x] Phát hiện quan trọng qua khảo sát:
  - Tìm kiếm thủ tục dùng được thẳng URL `https://dichvucong.gov.vn/dvc-ket-qua-thu-tuc?keyword={quote_plus(tên)}` — không cần Gemini quét trang chủ + điền ô tìm kiếm nữa
  - Vẫn cần Gemini `pick_search_result` để chọn đúng kết quả khớp tên (nhiều thủ tục có tên gần giống nhau, ví dụ "Đăng ký kết hôn" vs "...có yếu tố nước ngoài" vs "...lưu động")
  - Trang chi tiết thủ tục có nút cố định "Nộp hồ sơ" → bấm vào luôn điều hướng tới `tim-kiem-thu-tuc-hanh-chinh?formalityId=...` (danh sách lọc theo cơ quan thực hiện), cấu trúc **giống hệt nhau ở mọi thủ tục**
  - Trang đó có sidebar "Chọn cơ quan thực hiện" chứa 2 combobox tùy chỉnh cố định (tỉnh rồi phường, phường chỉ có data sau khi tỉnh đã chọn) + nút "Đồng ý" để áp dụng bộ lọc — tên option tỉnh thật là "Thành phố Hà Nội" (không phải "Hà Nội" trơn)
  - Sau khi "Đồng ý", danh sách bên trái lọc theo đúng tỉnh/phường, mỗi dòng có nút riêng "Nộp trực tuyến" — cần tìm đúng dòng có text "UBND phường {ward}" khớp phường đã chọn (nhiều dòng "Nộp trực tuyến" giống hệt nhau nếu không lọc đúng)
  - Rủi ro thật: phường cố định (`SUBMIT_WARD`) có thể không tồn tại trong danh sách của một thủ tục cụ thể — hệ thống chỉ hiện cơ quan đã áp dụng DVCTT cho thủ tục đó — nhưng đã xác nhận "Yên Sở" tồn tại cho thủ tục đang dùng
  - Bug thật phát hiện khi khảo sát: gọi `.click()` bằng JS thuần trên các phần tử React (nút mở combobox, option, nút Đồng ý) không luôn kích hoạt đúng framework event handler → chọn tỉnh xong nút vẫn hiện placeholder cũ, bấm nút phường lại mở nhầm listbox tỉnh còn sót lại trong DOM
- [x] `app/submit_flow.py` (mới): chỉ còn 1 hàm `build_search_url(procedure_name)` dựng URL tìm kiếm bằng `urllib.parse.quote_plus`
- [x] `app/dom_ai.py`: xóa hẳn `find_search_box`, `find_province_button`, `find_ward_button_and_submit` (không dùng Gemini cho các bước này nữa); chỉ giữ `pick_search_result` (vẫn cần AI vì phụ thuộc tên thủ tục)
- [x] `extension/content_script.js`: thêm `simulateClick(el)` (dispatch chuỗi `pointerdown/mousedown/pointerup/mouseup/click` thật thay vì `.click()` thuần, để tương thích framework React) — áp dụng cho mọi thao tác click trong flow mới, kể cả `clickSelector` cũ; thêm `waitForNoListbox`, `chooseComboboxByPlaceholder` (tự retry click tối đa 3 lần nếu dropdown không mở), `findComboboxButtonByPlaceholder`, `findButtonByText`; thêm `runFixedSubmitFlow({province, ward})` chạy trọn luồng: bấm "Nộp hồ sơ" → chọn tỉnh → chọn phường → bấm "Đồng ý" → tìm đúng card khớp `UBND phường {ward}` → **dừng lại, chỉ cuộn tới nút "Nộp trực tuyến" của card đó, KHÔNG tự bấm** (trả `{ok: true, ready_to_submit: true}`) — theo yêu cầu rõ ràng của người dùng "đừng ấn nộp trực tuyến", vì đây là ranh giới nộp hồ sơ thật + cần đăng nhập tài khoản định danh quốc gia (VNeID) mà không thể/không nên tự động hoá thay người dùng
- [x] Bỏ hẳn `fillAndSearch`, `setNativeValue`, `selectComboboxOption` (dead code, không còn command nào gọi tới)
- [x] `extension/background.js`: đổi `open_home_and_scan` thành `open_url_and_scan` (nhận `url` tùy ý thay vì luôn mở trang chủ); bỏ `fill_and_search`, `select_combobox_option`; thêm `run_fixed_submit_flow` (forward `province`/`ward` cho content script)
- [x] `app/main.py`: flow rút gọn còn 3 bước Gemini/extension chính — điều hướng URL tìm kiếm (không Gemini) → `pick_search_result` (có Gemini, có retry nếu null) → click kết quả → `run_fixed_submit_flow` (không Gemini, chạy cố định) — giảm từ 4 lệnh gọi Gemini/lần nộp xuống còn 1 (chỉ `pick_search_result`, có thể gọi 2 lần nếu cần retry); đổi `submit_procedure_done` để gửi kèm `message` rõ ràng "đã điền sẵn tỉnh/phường, vui lòng tự bấm Nộp trực tuyến" thay vì ngầm hiểu đã nộp xong
- [x] `SUBMIT_PROVINCE` sửa từ `"Hà Nội"` thành `"Thành phố Hà Nội"` cho khớp đúng text option thật (vẫn khớp được qua "includes" trước đây, nhưng để chính xác/rõ ràng)
- [x] `static/app.js`: `submit_procedure_done` hiển thị `msg.message` từ server (có fallback text cũ) thay vì hardcode cứng, để nhất quán với message mới
- [x] Test thật bằng Playwright headed (`headless=False`) chạy đúng `content_script.js` thật (đọc trực tiếp file, không copy tay) qua toàn bộ luồng: tìm kiếm bằng URL → chọn đúng kết quả "Thủ tục đăng ký kết hôn" → bấm "Nộp hồ sơ" → chọn "Thành phố Hà Nội" → chọn "Phường Yên Sở" → bấm "Đồng ý" → xác nhận danh sách lọc còn đúng 1 dòng "UBND phường Yên Sở" → dừng lại đúng chỗ, không bấm "Nộp trực tuyến" — kết quả `{ok: true, ready_to_submit: true}`, có ảnh chụp màn hình xác nhận
- [x] Gỡ Playwright khỏi dự án sau khi khảo sát xong (`uv remove --dev playwright`) — người dùng chọn không giữ lại vì đã có đủ bản đồ cố định trong code, cần khảo sát lại thì cài lại sau
- [ ] Rủi ro còn tồn: nếu dichvucong.gov.vn đổi giao diện (đổi class Tailwind, đổi text nút, đổi cấu trúc card kết quả), toàn bộ `runFixedSubmitFlow` sẽ hỏng vì không còn tự dò lại bằng Gemini nữa — cần theo dõi qua `submit_error` log nếu xảy ra
- [ ] Rủi ro còn tồn: `SUBMIT_WARD` cố định "Yên Sở" có thể không tồn tại cho một số thủ tục khác (đã thấy hệ thống chỉ hiện cơ quan đã áp dụng DVCTT) — nếu vậy `runFixedSubmitFlow` sẽ throw lỗi rõ ràng ("Không tìm thấy lựa chọn khớp") thay vì treo im lặng, nhờ cơ chế log/error đã có từ Phần N
