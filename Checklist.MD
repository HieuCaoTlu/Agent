# Checklist — Trợ lý giọng nói AI (MVP siêu gọn)

- [x] Khởi tạo `pyproject.toml` (uv) — FastAPI, uvicorn, google-genai, python-dotenv
- [x] Backend: 1 file (`app/main.py`) — phục vụ trang HTML tĩnh + WebSocket proxy `/ws` nối Gemini Live API, giữ `GEMINI_API_KEY` phía server
- [x] Frontend: 1 file HTML/CSS/JS tĩnh — hiển thị avatar/trạng thái AI, nút "Bắt đầu hỗ trợ" / "Kết thúc hỗ trợ"
- [x] Nút bắt đầu: xin quyền micro, mở WebSocket, stream audio micro lên backend liên tục
- [x] Backend chuyển tiếp audio hai chiều với Gemini Live API (nghe + trả lời bằng giọng nói)
- [x] Frontend phát audio trả lời của AI ngay khi nhận được (streaming)
- [x] Nút kết thúc: đóng kết nối, dừng micro, AI ngừng nói, nút bắt đầu hiện lại
- [ ] Chạy thử thực tế bằng `uv run uvicorn app.main:app --reload`, xác nhận đối thoại được bằng giọng nói qua trình duyệt (cần bạn tự thử qua trình duyệt — không tự động gọi Gemini Live thật để tránh tốn phí)
