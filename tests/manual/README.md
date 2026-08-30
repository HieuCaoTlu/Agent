# Test thủ công — Mục P của Checklist

Hai kịch bản dưới đây cố ý **không tự động hóa** (Checklist.MD mục P) — đòi
hỏi tương tác trình duyệt thật (micro, audio, giao diện) mà việc dựng bộ giả
lập tự động không tương xứng với giá trị mang lại ở quy mô MVP này. Người
thực hiện: bất kỳ ai trong nhóm phát triển hoặc cán bộ thử nghiệm, chạy trước
mỗi lần release hoặc sau khi đổi các phần liên quan (I, J, K, M, N, O).

## Chuẩn bị

```bash
# Backend (một cửa sổ terminal)
docker compose up -d          # PostgreSQL + Redis
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# Frontend (cửa sổ khác)
cd frontend && npm run dev
```

Mở `http://localhost:5173`. Trình duyệt cần hỗ trợ `AudioWorklet` (Chrome/Edge/Firefox bản mới).

---

## Kịch bản 1 — Luồng chính đầu-cuối (UC1)

**Mục tiêu:** xác nhận toàn bộ luồng nghiệp vụ chạy được liền mạch qua giao diện thật, không chỉ qua test tự động ở tầng service/API.

| # | Bước | Kết quả mong đợi |
|---|---|---|
| 1 | Vào `/`, bấm "Tạo phiên mới" | Chuyển tới `/sessions/new` |
| 2 | Nhập tên cán bộ, chọn "Có trợ lý AI", tích ô đồng ý, bấm "Bắt đầu phiên" | Chuyển tới `/sessions/:id`, hiện màn hình chọn thủ tục |
| 3 | Chọn một thủ tục (ví dụ "Đăng ký khai sinh") | Hiện màn hình làm việc 2 cột, các trường còn trống |
| 4 | Bấm nút ghi âm (🎙), đọc to một câu chứa vài trường (ví dụ "Tôi muốn đăng ký khai sinh cho con tôi tên Nguyễn Văn An, sinh ngày 10 tháng 5 năm 2026") | Trình duyệt xin quyền micro (nếu lần đầu); khi cấp quyền, nút chuyển trạng thái "Đang ghi âm", đồng hồ chạy, transcript từng phần (in nghiêng) xuất hiện dần |
| 5 | Bấm nút dừng (⏹) | Lượt thoại chốt lại trong danh sách; các trường liên quan tự điền giá trị gợi ý (nền xanh nhạt, nhãn "Gợi ý AI — chưa xác nhận") kèm đoạn transcript làm căn cứ |
| 6 | Với từng trường có giá trị, kiểm tra rồi bấm "Đã đối chiếu ✓" | Nền xanh biến mất, nhãn gợi ý biến mất, thanh tiến độ tăng |
| 7 | Với trường còn thiếu (viền đỏ, nhãn "BẮT BUỘC"), ghi âm bổ sung hoặc gõ tay rồi xác nhận | Trường không còn viền đỏ sau khi xác nhận |
| 8 | Khi đủ mọi trường bắt buộc | Nút "🔊 Đọc lại cho người dân" chuyển từ khóa (mờ) sang bấm được |
| 9 | Bấm nút đọc lại | Chuyển `/sessions/:id/readback`, nghe được audio (hoặc thấy text nếu môi trường không có audio thật) |
| 10 | Bấm "✓ Người dân xác nhận đúng" | Chuyển `/sessions/:id/complete` |
| 11 | Nhập một mã hồ sơ bất kỳ, bấm "Kết thúc phiên" | Quay về `/`, phiên xuất hiện trong danh sách với trạng thái "Hoàn tất" |

**Đạt:** cả 11 bước hoàn thành không có lỗi console/network chặn luồng, không cần can thiệp thủ công vào DB.

---

## Kịch bản 2 — Mọi provider AI lỗi, vẫn hoàn tất bằng nhập tay (UC6, NT-8)

**Mục tiêu:** xác nhận nguyên tắc suy giảm mềm (L1) hoạt động thật trên giao diện, không chỉ ở test đơn vị của từng service.

**Chuẩn bị:** đặt trong `.env` (hoặc biến môi trường khi chạy uvicorn):

```
LLM_PROVIDER=mock
STT_PROVIDER=mock
TTS_PROVIDER=mock
```

rồi giả lập lỗi bằng một trong hai cách:
- **(a)** Tạm sửa `MockLLMProvider`/`MockSTTProvider`/`MockTTSProvider` (`app/llm/mock_provider.py`, `app/stt/mock_provider.py`, `app/tts/mock_provider.py`) để `raise` lỗi tương ứng (`LLMConnectionError`, `STTError`, `TTSError`) thay vì trả kết quả giả — nhớ revert sau khi test xong.
- **(b)** Nếu đã cấu hình provider thật (Claude/Blaze), tạm đổi `ANTHROPIC_API_KEY`/`BLAZE_API_TOKEN` thành giá trị sai để provider thật tự nhiên trả lỗi xác thực.

| # | Bước | Kết quả mong đợi |
|---|---|---|
| 1 | Tạo phiên, chọn thủ tục như Kịch bản 1 | Bình thường |
| 2 | Ghi âm một câu, dừng lại | Backend gọi LLM trích xuất → gặp lỗi (`api_error`) |
| 3 | Kiểm tra giao diện | `session.state` chuyển `AI_UNAVAILABLE` (L1); banner vàng "⚠ Chế độ nhập tay" xuất hiện ở đầu màn hình làm việc |
| 4 | Với STT lỗi: bấm ghi âm | Nhận thông báo lỗi `STT_UNAVAILABLE` qua WebSocket, kết nối không bị đóng |
| 5 | Sửa transcript trực tiếp bằng nút "Sửa" trên lượt thoại (không cần AI nhận diện đúng) | Lưu thành công qua `PATCH /turns/{id}` |
| 6 | Gõ tay từng giá trị trường còn thiếu trực tiếp vào ô nhập, bấm "Đã đối chiếu ✓" cho từng trường | Mọi trường xác nhận được bình thường dù không có gợi ý AI |
| 7 | Khi đủ trường bắt buộc, bấm "Đọc lại cho người dân" | Nếu TTS lỗi: hiện cảnh báo "Không tạo được giọng đọc (TTS lỗi)" và vẫn hiện đầy đủ văn bản đọc lại để cán bộ đọc trực tiếp — không có audio nhưng luồng không bị chặn |
| 8 | Tiếp tục xác nhận của người dân, hoàn tất phiên như Kịch bản 1 bước 10-11 | Phiên hoàn tất bình thường dù cả 3 provider AI đều lỗi trong suốt phiên |

**Đạt:** phiên hoàn tất được từ đầu đến cuối chỉ bằng nhập tay, không có bước nào bị khóa cứng bởi lỗi AI, không có lỗi 500 không xử lý được hiển thị cho cán bộ.
