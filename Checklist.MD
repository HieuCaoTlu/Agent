# Checklist — Trợ lý giọng nói AI (Dịch vụ công)

- Quy tắc AI:
+ Không viết comment hay docstring vào code vì không cần thiết
+ Không tự call API để test vì tốn token
+ Không tự viết thêm log vào trong checklist vì không cần thiết
+ Không cần phải check syntax code python, html, css hay js đâu vì hầu hết bạn làm đúng

## Trợ lý giọng nói

`/ws` (`app/main.py`) chỉ còn là lớp mỏng: nhận kết nối, giới hạn 1 phiên hoạt động cùng lúc, rồi giao hết việc cho `app/voice_provider.py`. Chỉ dùng Gemini Live API (`gemini-2.5-flash-native-audio-latest`) — đã thử ghép thêm Blaze (STT/TTS realtime riêng, không có LLM) làm provider thay thế nhưng bỏ hẳn vì kiến trúc ghép thủ công kém ổn định hơn nhiều so với 1 SDK chính thức, hay chết âm thầm giữa chừng.

Kích hoạt nói theo kiểu **push-to-talk** (bấm nút "Nhấn để nói" hoặc phím Enter để bắt đầu, bấm/Enter lại để kết thúc) thay vì để Gemini tự VAD phát hiện khi nào người dùng nói — tắt hẳn `automatic_activity_detection` (`disabled=True`), client tự gửi `activity_start`/`activity_end` theo đúng lúc bấm nút. Chỉ gửi audio chunk khi đang ở trạng thái "đang nói" (cờ `isTalking`), không gửi liên tục 24/7 như trước — giảm hẳn lượng dữ liệu gửi đi và bỏ được toàn bộ logic đoán khoảng lặng (RMS) không cần thiết nữa.

Frontend hiện transcript dạng chat theo thời gian thực, sóng âm động theo trạng thái nói/nghe, bong bóng "đang gõ" (3 chấm nhảy) khi AI đang xử lý câu trả lời. Audio phát theo chunk có buffer đệm 120ms ở đầu mỗi lượt để giảm vấp khi mạng chậm.

## Tách "làm việc" khỏi "nói chuyện"

Mọi tác vụ text thuần (trích tên thủ tục từ transcript, chọn CSS selector từ HTML) đi qua `app/text_model.py`, tách hẳn khỏi Gemini Live (chỉ lo phần thoại). Chọn provider qua `TEXT_MODEL_PROVIDER`: `gemini`, `ollama` (đọc bộ biến `OLLAMA_*`), hoặc bất kỳ giá trị khác (đọc bộ biến `TEXT_MODEL_*`, dùng chung nhánh OpenAI-compatible qua `httpx` — đang cấu hình cho OpenRouter). Nhánh OpenAI-compat không ép `response_format: json_schema` (nhiều model mã nguồn mở không hỗ trợ, trả rỗng) mà nhúng mô tả schema vào prompt rồi tự trích JSON từ text trả về. Gặp `429` (rất hay xảy ra với model free OpenRouter do nghẽn shared pool upstream, không phải lỗi tài khoản) thì tự đọc `retry_after_seconds`/header `Retry-After` rồi đợi và thử lại tối đa 3 lần trước khi báo lỗi thật.

`.env` không dùng comment để bật/tắt provider — mọi giá trị (Gemini, OpenRouter, Ollama) đều để thật sẵn, chỉ 1 dòng đầu file (`TEXT_MODEL_PROVIDER`) quyết định cái nào đang chạy cho phần "làm việc" (voice luôn cố định dùng Gemini Live).

## Tra cứu thủ tục qua RAG (trang quản lý)

`app/rag.py` tìm keyword 2 tầng (chọn thủ tục → chọn mục nội dung) trên `data/index.json`/`data/procedures/*.json`, không dùng embedding. `build_index.py` dựng lại index từ PDF trong `data/pdfs/`. Trang `static/manage.html` quản lý upload/xóa PDF riêng, tự rebuild index. RAG không nối vào hội thoại giọng nói, chỉ phục vụ trang quản lý.

## Tự động điền hồ sơ trên dichvucong.gov.vn (qua Chrome extension)

Sau khi AI nói xong hết câu (`turn_complete`) mà transcript (người dùng hoặc AI) có chứa từ "nộp", hiện cặp nút **"Tự động nộp (đếm ngược 3s)"** / **"Hủy nộp"** — hết 3 giây tự động gọi nộp hồ sơ nếu không ai bấm gì; bấm "Tự động nộp" bất kỳ lúc nào trong lúc đếm sẽ nộp ngay; bấm "Hủy nộp" sẽ dừng đếm và gửi 1 turn giả vào Gemini Live (`cancel_submit`, qua `session.send_client_content`) để AI biết người dùng chưa muốn nộp và tự hỏi lại "cần hỗ trợ gì thêm". Có thêm nút "Test nộp: Đăng ký khai sinh" ở màn hình chờ để test nhanh không cần nói qua giọng nói.

Luồng nộp (`_handle_submit_procedure`, `app/main.py`) tự động **retry tối đa 3 lần** khi gặp lỗi runtime (extension mất kết nối, timeout, lỗi thao tác trang, lỗi không rõ) trước khi báo `submit_procedure_error` thật — mỗi lần thử gửi `submit_procedure_status` báo "Đang thử lại lần X/3". Lỗi do input sai (không xác định được tên thủ tục, không tìm thấy kết quả trên trang) không retry vì thử lại vô ích. Nút "Thử lại" thủ công vẫn còn cho trường hợp hết cả 3 lần tự động vẫn lỗi — gửi lại đúng request cuối cùng (`lastSubmitRequest`) trên **cùng WebSocket đang mở** nếu còn sống, chỉ mở lại kết nối mới (về màn hình chờ) khi WebSocket đã thực sự đóng.

Từng bước của luồng: trích tên thủ tục → điều hướng thẳng URL tìm kiếm (`dvc-ket-qua-thu-tuc?keyword=...`, không cần AI quét trang chủ) → AI chọn đúng kết quả khớp tên (`dom_ai.pick_search_result`, có retry nếu HTML chưa render) → `run_fixed_submit_flow` chạy cố định không cần AI (đã khảo sát 1 lần bằng Playwright): bấm "Nộp hồ sơ" → chọn tỉnh/phường cố định ("Thành phố Hà Nội"/"Yên Sở") → "Đồng ý" → tìm đúng dòng khớp. **Dừng lại ở đó, không tự bấm "Nộp trực tuyến"** — để người dùng tự bấm và đăng nhập VNeID.

`app/extension_bridge.py` cầu nối lệnh/phản hồi qua WebSocket `/extension`, timeout 20s, raise lỗi rõ ràng thay vì treo. `content_script.js` dùng `simulateClick` (giả lập chuỗi pointerdown/mousedown/click thật) vì `.click()` thuần không kích hoạt đúng React. Mọi bước log vào `data/logs/{ngày}.jsonl`.

## Giao diện extension (Chrome, Manifest V3)

Popup (bấm icon) và Options (chuột phải) đều hiện trạng thái kết nối backend, cho sửa port, nút test kết nối. `background.js` tự reconnect khi mất kết nối.

## Rủi ro / giới hạn đã biết

- `/ws` và `/extension` không có xác thực — chấp nhận được vì chỉ chạy local, cần vá nếu mở ra ngoài localhost/LAN.
- `run_fixed_submit_flow` dùng bản đồ thao tác cố định, không tự dò lại — nếu dichvucong.gov.vn đổi giao diện sẽ hỏng, cần khảo sát lại thủ công.
- Tỉnh/phường nộp hồ sơ cố định trong code (`SUBMIT_PROVINCE`/`SUBMIT_WARD`, `app/main.py`) — phường có thể không tồn tại cho một số thủ tục hiếm, khi đó báo lỗi rõ ràng thay vì treo.
- Model free tier (Gemini, OpenRouter `:free`) đều có rate-limit — dội nhiều lần liên tiếp khi debug dễ dính giới hạn.
