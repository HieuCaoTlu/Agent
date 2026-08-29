# Trợ lý giọng nói AI hỗ trợ kê khai, nộp hồ sơ thủ tục hành chính trực tuyến

Công cụ nội bộ dùng tại quầy hỗ trợ dịch vụ công (phường Yên Sở): người dân trình bày
nhu cầu bằng giọng nói, hệ thống chuyển giọng nói → văn bản, dùng LLM trích xuất các
trường dữ liệu và cảnh báo thiếu sót, hiển thị dưới dạng **gợi ý** cho cán bộ. Cán bộ
đối chiếu giấy tờ gốc, tự tay xác nhận và nhập vào Cổng Dịch vụ công/VNeID.

Tài liệu tham chiếu: [Plan.MD](Plan.MD) · [Checklist.MD](Checklist.MD)

> Hướng dẫn cài đặt, biến môi trường, migration và seed catalog đầy đủ sẽ được bổ sung
> ở phần Q (Đóng gói và chạy) của checklist.

## Cài đặt nhanh (đang xây dựng)

```bash
uv sync
cp .env.example .env   # điền giá trị thật, KHÔNG commit .env
```
