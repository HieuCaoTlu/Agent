# KẾ HOẠCH TRIỂN KHAI KỸ THUẬT

## Trợ lý giọng nói AI hỗ trợ người dân kê khai, nộp hồ sơ thủ tục hành chính trực tuyến

**Đơn vị:** Tổ chuyển đổi số cộng đồng phường Yên Sở — Phòng Văn hóa – Xã hội
**Phạm vi áp dụng:** Điểm hỗ trợ dịch vụ công phường Yên Sở; Chi nhánh số 4 – Trung tâm Phục vụ hành chính công TP Hà Nội
**Thời gian áp dụng (theo Báo cáo sáng kiến):** 01/7/2026 – 15/12/2026
**Phiên bản tài liệu:** 1.0 — ngày lập: 30/8/2026
**Trạng thái:** Bản kế hoạch kỹ thuật để bắt đầu triển khai code

---

## MỤC LỤC

1. [Bối cảnh và mục tiêu](#1-bối-cảnh-và-mục-tiêu)
2. [Nguyên tắc thiết kế bắt buộc](#2-nguyên-tắc-thiết-kế-bắt-buộc)
3. [Phạm vi phiên bản 1 (MVP)](#3-phạm-vi-phiên-bản-1-mvp)
4. [Kiến trúc hệ thống](#4-kiến-trúc-hệ-thống)
5. [Mô hình nghiệp vụ và state machine](#5-mô-hình-nghiệp-vụ-và-state-machine)
6. [Danh mục thủ tục (Procedure Catalog)](#6-danh-mục-thủ-tục-procedure-catalog)
7. [Đặc tả Use Case đầy đủ](#7-đặc-tả-use-case-đầy-đủ)
8. [Thiết kế dữ liệu](#8-thiết-kế-dữ-liệu)
9. [Đặc tả API](#9-đặc-tả-api)
10. [Thiết kế tầng AI](#10-thiết-kế-tầng-ai)
11. [Thiết kế Frontend cán bộ](#11-thiết-kế-frontend-cán-bộ)
12. [Bảo mật, quyền riêng tư và tuân thủ](#12-bảo-mật-quyền-riêng-tư-và-tuân-thủ)
13. [Xử lý lỗi và độ tin cậy](#13-xử-lý-lỗi-và-độ-tin-cậy)
14. [Quan sát hệ thống và chỉ số](#14-quan-sát-hệ-thống-và-chỉ-số)
15. [Chiến lược kiểm thử](#15-chiến-lược-kiểm-thử)
16. [Cấu trúc mã nguồn và môi trường](#16-cấu-trúc-mã-nguồn-và-môi-trường)
17. [Triển khai và vận hành](#17-triển-khai-và-vận-hành)
18. [Kế hoạch thực hiện theo giai đoạn](#18-kế-hoạch-thực-hiện-theo-giai-đoạn)
19. [Rủi ro và phương án giảm thiểu](#19-rủi-ro-và-phương-án-giảm-thiểu)
20. [Vấn đề cần chốt trước khi code](#20-vấn-đề-cần-chốt-trước-khi-code)
21. [Phụ lục](#21-phụ-lục)

---

## 1. Bối cảnh và mục tiêu

### 1.1. Bài toán thực tiễn

Theo đánh giá thực trạng trong Báo cáo sáng kiến, người dân — đặc biệt là người cao tuổi, người lao động phổ thông, người yếu thế và người hạn chế kỹ năng số — gặp khó khăn khi:

- Đăng nhập tài khoản định danh điện tử.
- Nhập liệu bằng bàn phím (chậm, dễ sai chính tả, dễ sai định dạng).
- Kê khai thiếu trường thông tin dẫn tới hồ sơ phải bổ sung nhiều lần.

Hệ quả: thành viên Tổ chuyển đổi số cộng đồng phải hỗ trợ trực tiếp từng trường hợp, tăng áp lực công việc khi số lượt sử dụng dịch vụ công trực tuyến tăng.

### 1.2. Giải pháp

Xây dựng một **công cụ hỗ trợ nội bộ** dùng tại quầy: người dân trình bày nhu cầu bằng giọng nói, hệ thống chuyển giọng nói thành văn bản, dùng LLM trích xuất các trường dữ liệu và cảnh báo thiếu sót, hiển thị dưới dạng **gợi ý** cho cán bộ. Cán bộ đối chiếu giấy tờ gốc và tự tay nhập vào Cổng Dịch vụ công/VNeID. Người dân nghe đọc lại và xác nhận trước khi nộp.

### 1.3. Mục tiêu đo lường được (KPI từ Báo cáo sáng kiến)

| # | Chỉ tiêu | Mục tiêu | Cách đo trong hệ thống |
|---|---|---|---|
| KPI-1 | Rút ngắn thời gian hỗ trợ nhập thông tin ban đầu | **60%** với biểu mẫu đơn giản | So sánh `duration_ms` phiên có AI với baseline nhập tay đo thủ công ở Giai đoạn 0 |
| KPI-2 | Số lượt hỗ trợ | **45–50 lượt/ngày** | `COUNT(sessions)` theo ngày |
| KPI-3 | Giảm hồ sơ phải chỉnh sửa do thiếu/sai định dạng | **30%** | Đối chiếu `warnings` đã được xử lý trước khi nộp vs. tỷ lệ hồ sơ trả lại thực tế |
| KPI-4 | Giảm lượt tiếp công dân tại trung tâm hành chính công | **20%** | Số liệu ngoài hệ thống, đối chiếu thủ công |
| KPI-5 | Mức độ hài lòng của người dân | **93%** | Phiếu khảo sát nhanh (100 phiếu) — ngoài hệ thống |
| KPI-6 | Bộ dữ liệu thống kê nhu cầu, nhóm thủ tục phát sinh nhiều, lỗi kê khai thường gặp | Có báo cáo | Dashboard thống kê từ bảng `sessions`, `extractions`, `warnings` |

> **Lưu ý về KPI:** các con số trên là **chỉ tiêu đặt ra**, không phải kết quả đã đo. Hệ thống phải sinh được số liệu thực để đối chiếu. Muốn đo KPI-1 và KPI-3 một cách trung thực thì **cần đo baseline (nhập tay thuần túy) trước khi bật AI** — xem Giai đoạn 0 ở Mục 18.

---

## 2. Nguyên tắc thiết kế bắt buộc

Các nguyên tắc này là **ràng buộc cứng**, không được vi phạm khi hiện thực. Mọi pull request đều phải được kiểm tra theo checklist này.

| # | Nguyên tắc | Hệ quả kỹ thuật |
|---|---|---|
| **NT-1** | AI **không** tự gửi, xác nhận, hoàn tất bất kỳ giao dịch nào với hệ thống chính phủ | Backend **không có** bất kỳ client/integration nào tới Cổng DVC hoặc VNeID trong phạm vi V1 |
| **NT-2** | Mọi output AI là **gợi ý**, chưa phải dữ liệu chính thức | Bảng `extractions` tách biệt hoàn toàn với `field_confirmations`; UI hiển thị badge "Gợi ý AI — chưa xác nhận" |
| **NT-3** | Cán bộ xác nhận **từng trường**, không có nút "đồng ý tất cả" | API chỉ có endpoint confirm theo `field_name`; **không** có endpoint bulk confirm. Frontend không có nút "Xác nhận tất cả" |
| **NT-4** | AI không tự sinh quy định pháp luật | `procedure_schema` và danh sách thành phần hồ sơ lấy 100% từ catalog tĩnh do phòng chuyên môn duyệt; prompt cấm mô hình bổ sung yêu cầu ngoài schema |
| **NT-5** | Không suy đoán giá trị dữ liệu | Prompt bắt buộc trả `MISSING`/`UNCLEAR`; hậu kiểm bằng validator, mọi giá trị không truy vết được về transcript sẽ bị loại |
| **NT-6** | Data minimization | Không gửi CCCD đầy đủ tới LLM (xem Mục 12.3 — cơ chế masking); không lưu bản ghi âm sau khi có transcript |
| **NT-7** | Ghi log đầy đủ, truy xuất được | Mọi hành động vào `audit_log` với actor/action/timestamp; log bất biến (append-only) |
| **NT-8** | Luôn có luồng dự phòng không phụ thuộc AI | Mọi thành phần AI hỏng → hệ thống vẫn cho cán bộ nhập tay và hoàn tất phiên |
| **NT-9** | AI không tư vấn pháp lý | Prompt cấm; output chỉ là observation, không phải kết luận về tính hợp lệ hồ sơ |
| **NT-10** | Không dữ liệu cá nhân lên nền tảng chưa được cơ quan có thẩm quyền cho phép | Danh sách nhà cung cấp được duyệt cấu hình trong `config`; gọi ra ngoài danh sách này bị chặn ở tầng code |

---

## 3. Phạm vi phiên bản 1 (MVP)

### 3.1. Trong phạm vi

- Ghi âm tại quầy, chuyển giọng nói → văn bản (STT tiếng Việt).
- Trích xuất trường dữ liệu bằng LLM theo schema tĩnh của từng thủ tục.
- Cảnh báo trường thiếu / không rõ / sai định dạng.
- Hiển thị danh sách thành phần hồ sơ cần chuẩn bị (từ catalog tĩnh).
- Giao diện cán bộ: xem gợi ý, sửa, xác nhận từng trường, sao chép sang Cổng DVC.
- Đọc lại nội dung bằng TTS cho người dân xác nhận.
- Ghi nhận xác nhận của người dân, đóng phiên, lưu mã hồ sơ do cán bộ nhập.
- Audit log đầy đủ + màn hình tra cứu log theo phiên.
- Dashboard thống kê phục vụ KPI-2, KPI-3, KPI-6.

### 3.2. Ngoài phạm vi (V1)

| Hạng mục | Lý do |
|---|---|
| Tự động điền form trên Cổng DVC / VNeID | Cần chấp thuận của đơn vị chủ quản hệ thống; vi phạm NT-1 nếu làm ở V1 |
| Tra cứu chéo cơ sở dữ liệu dân cư | Ngoài thẩm quyền truy cập của công cụ hỗ trợ tại quầy |
| Người dân tự sử dụng không có cán bộ | Mô hình V1 là công cụ hỗ trợ cán bộ, cán bộ luôn có mặt |
| Xác thực/đăng nhập hộ người dân bằng AI | Là thao tác thủ công của cán bộ theo quy trình hiện hành |
| Ứng dụng di động cho người dân | Giai đoạn sau |
| Đa ngôn ngữ / tiếng dân tộc | Giai đoạn sau |

> **Cần làm rõ với đơn vị chủ trì:** Báo cáo sáng kiến ở phần "tính mới" có nêu hệ thống *"tự động điền vào các trường dữ liệu tương ứng trên biểu mẫu điện tử"* và *"có khả năng tích hợp với Cổng dịch vụ công, VNeID, cơ sở dữ liệu dân cư"*. Điều này **mâu thuẫn với nguyên tắc NT-1** và với phần "Mô tả tóm tắt sáng kiến" (Bước 5: *"cán bộ … nhập dữ liệu vào Cổng Dịch vụ công"*). Kế hoạch này chọn phương án **cán bộ nhập tay** cho V1 vì đó là phương án khả thi pháp lý và đúng với quy trình 7 bước đã mô tả trong báo cáo. Việc tự động điền được đưa vào lộ trình giai đoạn 2 (Mục 21.3), cần văn bản chấp thuận trước khi làm.

---

## 4. Kiến trúc hệ thống

### 4.1. Vì sao chọn kiến trúc cascaded

Sử dụng kiến trúc **cascaded** (STT riêng → LLM riêng → TTS riêng) thay vì mô hình speech-to-speech hợp nhất, vì:

1. **Kiểm toán được từng bước:** lưu được transcript thô, prompt gửi đi, response nhận về — điều kiện bắt buộc để "truy xuất khi cần thiết" theo yêu cầu trong báo cáo.
2. **Kiểm soát dữ liệu:** có thể masking dữ liệu nhạy cảm giữa bước STT và bước LLM.
3. **Chèn được chốt kiểm soát của con người:** cán bộ can thiệp được ở giữa pipeline.
4. **Suy giảm mềm:** một thành phần hỏng vẫn dùng được các thành phần còn lại.

Đánh đổi: độ trễ cao hơn speech-to-speech. Chấp nhận được vì đây là quầy hỗ trợ có cán bộ, không phải hội thoại thời gian thực.

### 4.2. Sơ đồ thành phần

```
┌──────────────────────────────────────────────────────────────────────┐
│                     ĐIỂM HỖ TRỢ (mạng nội bộ phường)                 │
│                                                                       │
│   Người dân ──(giọng nói)──▶ Micro ──▶ ┌────────────────────┐        │
│                                          │  Frontend cán bộ   │        │
│   Loa ◀──(giọng nói đọc lại)──────────── │  (React SPA)       │        │
│                                          └─────────┬──────────┘        │
│                                                     │ HTTPS / WSS      │
│   Cán bộ ──(thao tác thủ công)──▶ Trình duyệt tab 2 │                  │
│                    │                                │                  │
└────────────────────┼────────────────────────────────┼──────────────────┘
                     │                                │
                     ▼                                ▼
        ┌────────────────────────┐      ┌─────────────────────────────┐
        │  Cổng DVC / VNeID      │      │   FastAPI Backend            │
        │  (hệ thống bên ngoài,  │      │  ┌────────────────────────┐ │
        │   KHÔNG tích hợp)      │      │  │ Session Orchestrator   │ │
        └────────────────────────┘      │  │ (state machine)        │ │
                                         │  ├────────────────────────┤ │
                                         │  │ STT Service Adapter    │ │
                                         │  │ TTS Service Adapter    │ │
                                         │  │ Extraction Service     │ │
                                         │  │ Validation Engine      │ │
                                         │  │ Catalog Service        │ │
                                         │  │ Audit Logger           │ │
                                         │  │ PII Redactor           │ │
                                         │  └────────────────────────┘ │
                                         └──────┬──────────────┬───────┘
                                                │              │
                          ┌─────────────────────┘              └──────────────┐
                          ▼                                                    ▼
                 ┌──────────────────┐                            ┌────────────────────┐
                 │  PostgreSQL      │                            │  Nhà cung cấp AI    │
                 │  - sessions      │                            │  ┌───────────────┐ │
                 │  - transcripts   │                            │  │ STT (BlazeAI  │ │
                 │  - extractions   │                            │  │  hoặc tương   │ │
                 │  - confirmations │                            │  │  đương)       │ │
                 │  - audit_log     │                            │  ├───────────────┤ │
                 └──────────────────┘                            │  │ TTS           │ │
                          ▲                                       │  ├───────────────┤ │
                 ┌──────────────────┐                            │  │ LLM (Claude   │ │
                 │  Redis           │                            │  │  API)         │ │
                 │  - session state │                            │  └───────────────┘ │
                 │  - audio buffer  │                            └────────────────────┘
                 │    (TTL ngắn)    │
                 │  - rate limit    │
                 └──────────────────┘
```

### 4.3. Stack công nghệ

| Lớp | Công nghệ | Phiên bản | Ghi chú |
|---|---|---|---|
| Ngôn ngữ | Python | 3.12 | Đã cài qua `uv` |
| Quản lý gói | uv | mới nhất | Nhanh, lockfile tất định |
| Web framework | FastAPI | ≥0.115 | Async, hỗ trợ WebSocket, tự sinh OpenAPI |
| ASGI server | Uvicorn | ≥0.30 | |
| ORM | SQLAlchemy 2.x + Alembic | | Style async |
| Validation | Pydantic | v2 | Dùng chung cho schema API và schema output AI |
| Database | PostgreSQL | ≥16 | JSONB cho payload trích xuất |
| Cache / state | Redis | ≥7 | Trạng thái phiên, audio buffer TTL ngắn |
| LLM | Claude API (`claude-sonnet-5`) | | Trích xuất trường dữ liệu |
| SDK LLM | `anthropic` | mới nhất | |
| STT / TTS | BlazeAI (**cần thẩm định**) | | Xem Mục 20 |
| HTTP client | httpx | | Async, có timeout + retry |
| Frontend | React 18 + TypeScript + Vite | | |
| UI | Tailwind CSS | | Ưu tiên font lớn, tương phản cao |
| Kiểm thử | pytest, pytest-asyncio, respx | | |
| Chất lượng mã | ruff, mypy | | Bắt buộc trong CI |
| Log | structlog (JSON) | | |

---

## 5. Mô hình nghiệp vụ và state machine

### 5.1. Ánh xạ quy trình 7 bước sang hệ thống

| Bước (Báo cáo sáng kiến) | Ai thực hiện | Hệ thống làm gì | Trạng thái phiên |
|---|---|---|---|
| **B1.** Người dân trình bày nhu cầu bằng lời nói | Người dân | Ghi âm → STT → transcript | `CREATED` → `LISTENING` |
| **B2.** Cán bộ hỗ trợ đăng nhập, chọn nhóm thủ tục | **Cán bộ (thủ công)** | Chỉ ghi nhận lựa chọn thủ tục từ catalog | `PROCEDURE_SELECTED` |
| **B3.** AI trích xuất thông tin cần kê khai | Hệ thống | Gọi LLM với schema tĩnh → JSON gợi ý | `EXTRACTING` → `SUGGESTED` |
| **B4.** AI gợi ý biểu mẫu, cảnh báo thiếu sót | Hệ thống | Tra catalog + validator sinh cảnh báo | `SUGGESTED` |
| **B5.** Cán bộ kiểm tra, đối chiếu giấy tờ, nhập liệu | **Cán bộ (thủ công)** | Ghi nhận xác nhận từng trường | `REVIEWING` → `FIELDS_CONFIRMED` |
| **B6.** Người dân nghe/đọc lại, xác nhận | Người dân | TTS đọc lại → ghi nhận xác nhận | `READBACK` → `CITIZEN_CONFIRMED` |
| **B7.** Nộp hồ sơ, thông báo mã hồ sơ | **Cán bộ (thủ công)** | Ghi nhận mã hồ sơ, đóng phiên | `COMPLETED` |

### 5.2. State machine của phiên

```
                      ┌─────────┐
                      │ CREATED │
                      └────┬────┘
                           │ start_listening
                           ▼
    ┌────────────────▶┌───────────┐
    │                 │ LISTENING │◀──────────────┐
    │                 └─────┬─────┘               │
    │                       │ stop + transcript   │ ask_again
    │                       ▼                     │ (UC2/UC5)
    │           ┌──────────────────────┐          │
    │           │ PROCEDURE_SELECTED   │          │
    │           └──────────┬───────────┘          │
    │                      │ request_extraction   │
    │                      ▼                      │
    │              ┌──────────────┐               │
    │              │  EXTRACTING  │               │
    │              └──────┬───────┘               │
    │            success  │  failure              │
    │        ┌────────────┴──────────┐            │
    │        ▼                       ▼            │
    │  ┌───────────┐         ┌──────────────┐    │
    │  │ SUGGESTED │         │ AI_UNAVAILABLE│───┼──▶ (nhập tay hoàn toàn)
    │  └─────┬─────┘         └──────┬────────┘   │
    │        │ staff opens review   │            │
    │        ▼                      │            │
    │  ┌───────────┐                │            │
    │  │ REVIEWING │────────────────┼────────────┘
    │  └─────┬─────┘                │
    │        │ all required fields confirmed
    │        ▼                      │
    │ ┌──────────────────┐          │
    │ │ FIELDS_CONFIRMED │◀─────────┘
    │ └────────┬─────────┘
    │          │ trigger_readback
    │          ▼
    │    ┌───────────┐
    │    │ READBACK  │
    │    └─────┬─────┘
    │          │
    │   ┌──────┴────────┐
    │   │ citizen says  │
    │   │ "cần sửa"     │ (UC4)
    └───┴───────────────┘
              │ citizen says "đúng rồi"
              ▼
    ┌────────────────────┐
    │ CITIZEN_CONFIRMED  │
    └─────────┬──────────┘
              │ staff submits on Cổng DVC (ngoài hệ thống)
              │ + nhập mã hồ sơ
              ▼
        ┌───────────┐         ┌───────────┐
        │ COMPLETED │         │ CANCELLED │ (có thể tới từ mọi trạng thái)
        └───────────┘         └───────────┘
```

### 5.3. Bảng chuyển trạng thái hợp lệ

| Từ | Sự kiện | Tới | Điều kiện |
|---|---|---|---|
| `CREATED` | `start_listening` | `LISTENING` | — |
| `LISTENING` | `select_procedure` | `PROCEDURE_SELECTED` | `procedure_code` có trong catalog đang hiệu lực |
| `PROCEDURE_SELECTED` | `request_extraction` | `EXTRACTING` | Có ít nhất 1 transcript trong phiên (cán bộ tự quyết định transcript đã đủ dùng chưa, không có ngưỡng tự động) |
| `EXTRACTING` | `extraction_success` | `SUGGESTED` | JSON hợp lệ theo schema |
| `EXTRACTING` | `extraction_failed` | `AI_UNAVAILABLE` | Sau khi hết số lần retry |
| `SUGGESTED` | `open_review` | `REVIEWING` | — |
| `AI_UNAVAILABLE` | `manual_entry` | `REVIEWING` | Cán bộ chọn nhập tay |
| `REVIEWING` | `ask_again` | `LISTENING` | UC2 — thiếu thông tin, hỏi lại |
| `REVIEWING` | `all_required_confirmed` | `FIELDS_CONFIRMED` | Mọi trường `required=true` đã có `field_confirmations` |
| `FIELDS_CONFIRMED` | `trigger_readback` | `READBACK` | — |
| `READBACK` | `citizen_rejected` | `REVIEWING` | UC4 |
| `READBACK` | `citizen_confirmed` | `CITIZEN_CONFIRMED` | — |
| `CITIZEN_CONFIRMED` | `complete` | `COMPLETED` | Có `dossier_code` do cán bộ nhập |
| *(bất kỳ)* | `cancel` | `CANCELLED` | Có lý do hủy |

**Quy tắc hiện thực:** state machine đặt ở `app/domain/state_machine.py`, là hàm thuần (pure function) `transition(current_state, event, context) -> new_state`, ném `InvalidTransitionError` với chuyển đổi không hợp lệ. Mọi chuyển trạng thái đều ghi vào `audit_log`.

---

## 6. Danh mục thủ tục (Procedure Catalog)

### 6.1. Vai trò

Catalog là **nguồn chân lý duy nhất** về: thủ tục nào được hỗ trợ, mỗi thủ tục cần trường dữ liệu nào, thành phần hồ sơ gì. LLM **không bao giờ** được tự quyết định những điều này (NT-4).

### 6.2. Quy trình quản trị catalog

1. Phòng chuyên môn soạn nội dung dựa trên quy định hiện hành.
2. Lưu dưới dạng file JSON trong repo, có version.
3. **Bắt buộc có người duyệt** — file ghi rõ `approved_by`, `approved_at`, `legal_basis`.
4. Thay đổi catalog phải qua pull request, không sửa trực tiếp trên production.
5. Mỗi phiên ghi lại `catalog_version` đang dùng để truy vết về sau.

### 6.3. Cấu trúc file

`app/static_data/procedures/dang_ky_khai_sinh.json`:

```json
{
  "code": "dang_ky_khai_sinh",
  "name": "Đăng ký khai sinh",
  "catalog_version": "2026.08.1",
  "approved_by": "Phòng Văn hóa - Xã hội phường Yên Sở",
  "approved_at": "2026-08-15",
  "legal_basis": "Luật Hộ tịch 2014; Nghị định 123/2015/NĐ-CP",
  "effective_from": "2026-09-01",
  "effective_to": null,
  "fields": [
    {
      "name": "ho_ten_nguoi_duoc_khai_sinh",
      "label": "Họ và tên người được khai sinh",
      "type": "person_name",
      "required": true,
      "sensitive": false,
      "spoken_hint": "Họ tên đầy đủ của cháu bé",
      "validators": ["vietnamese_name"]
    },
    {
      "name": "ngay_sinh",
      "label": "Ngày, tháng, năm sinh",
      "type": "date",
      "required": true,
      "sensitive": false,
      "validators": ["date_not_future", "date_reasonable_birth"]
    },
    {
      "name": "gioi_tinh",
      "label": "Giới tính",
      "type": "enum",
      "required": true,
      "options": ["Nam", "Nữ"],
      "validators": ["in_options"]
    },
    {
      "name": "noi_sinh",
      "label": "Nơi sinh",
      "type": "text",
      "required": true,
      "sensitive": false
    },
    {
      "name": "ho_ten_cha",
      "label": "Họ và tên cha",
      "type": "person_name",
      "required": false,
      "validators": ["vietnamese_name"]
    },
    {
      "name": "ho_ten_me",
      "label": "Họ và tên mẹ",
      "type": "person_name",
      "required": true,
      "validators": ["vietnamese_name"]
    },
    {
      "name": "so_cccd_nguoi_yeu_cau",
      "label": "Số CCCD người yêu cầu",
      "type": "national_id",
      "required": true,
      "sensitive": true,
      "redact_to_llm": true,
      "validators": ["cccd_12_digits"]
    },
    {
      "name": "so_dien_thoai",
      "label": "Số điện thoại liên hệ",
      "type": "phone",
      "required": true,
      "sensitive": true,
      "redact_to_llm": false,
      "validators": ["vn_phone_10_digits"]
    },
    {
      "name": "dia_chi_thuong_tru",
      "label": "Địa chỉ thường trú",
      "type": "address",
      "required": true,
      "sensitive": true
    }
  ],
  "required_documents": [
    {
      "name": "Giấy chứng sinh",
      "note": "Bản chính do cơ sở y tế cấp. Nếu sinh tại nhà, thay bằng văn bản xác nhận của người làm chứng."
    },
    {
      "name": "Giấy tờ tùy thân của người đi đăng ký",
      "note": "CCCD hoặc hộ chiếu còn hạn"
    },
    {
      "name": "Giấy chứng nhận kết hôn của cha mẹ",
      "note": "Nếu cha mẹ đã đăng ký kết hôn"
    }
  ],
  "readback_template": "Tôi xin đọc lại thông tin đã kê khai. Thủ tục: đăng ký khai sinh. Họ tên người được khai sinh: {ho_ten_nguoi_duoc_khai_sinh}. Ngày sinh: {ngay_sinh}. Giới tính: {gioi_tinh}. Nơi sinh: {noi_sinh}. Họ tên mẹ: {ho_ten_me}. Họ tên cha: {ho_ten_cha}. Số điện thoại: {so_dien_thoai}. Địa chỉ thường trú: {dia_chi_thuong_tru}. Xin ông bà cho biết thông tin trên đã chính xác chưa ạ?"
}
```

### 6.4. Danh mục thủ tục cho V1

Theo Báo cáo sáng kiến, ba nhóm được nhắc tên trực tiếp — ưu tiên làm trước:

| # | Mã | Tên thủ tục | Ưu tiên |
|---|---|---|---|
| 1 | `dang_ky_khai_sinh` | Đăng ký khai sinh | Cao |
| 2 | `dang_ky_ket_hon` | Đăng ký kết hôn | Cao |
| 3 | `chung_thuc_dien_tu` | Chứng thực bản sao điện tử từ bản chính | Cao |
| 4 | `xac_nhan_cu_tru` | Xác nhận thông tin về cư trú | Trung bình |
| 5 | `dang_ky_khai_tu` | Đăng ký khai tử | Trung bình |

> Danh sách chính thức cần Phòng Văn hóa – Xã hội chốt (Mục 20).

### 6.5. Catalog Service

```python
# app/services/catalog.py — mô tả hành vi
class CatalogService:
    def list_active(self, at: date) -> list[ProcedureSummary]: ...
    def get(self, code: str, at: date) -> Procedure: ...        # raise ProcedureNotFound
    def get_field_schema(self, code: str) -> list[FieldSpec]: ...
    def get_required_documents(self, code: str) -> list[Document]: ...
    def current_version(self) -> str: ...
```

Catalog nạp vào bộ nhớ lúc khởi động, kèm checksum. Đổi catalog → tăng `catalog_version` → ghi vào audit log.

---

## 7. Đặc tả Use Case đầy đủ

### UC1 — Kê khai đủ thông tin trong một lượt nói

| Mục | Nội dung |
|---|---|
| **Tác nhân** | Người dân, Cán bộ hỗ trợ |
| **Tiền điều kiện** | Cán bộ đã đăng nhập hệ thống nội bộ; người dân có mặt tại quầy với giấy tờ gốc |
| **Kích hoạt** | Người dân trình bày nhu cầu bằng lời nói |

**Luồng chính:**

1. Cán bộ tạo phiên mới trên giao diện (`POST /sessions`).
2. Cán bộ bấm "Bắt đầu ghi âm"; frontend mở WebSocket, gửi audio chunk.
3. Backend chuyển tiếp tới STT, nhận transcript từng phần, đẩy về frontend theo thời gian thực.
4. Người dân nói xong; cán bộ bấm "Dừng". Transcript cuối được lưu.
5. Cán bộ chọn thủ tục "Đăng ký khai sinh" từ dropdown catalog (`POST /sessions/{id}/procedure`).
6. Cán bộ bấm "Trích xuất thông tin" (`POST /sessions/{id}/extract`).
7. Backend: lấy field schema từ catalog → che dữ liệu nhạy cảm → gọi LLM → validate JSON → chạy validator từng trường → lưu `extractions`.
8. Frontend hiển thị bảng gợi ý: mỗi trường có giá trị + mức tin cậy + nguồn trích dẫn trong transcript, kèm nhãn "Gợi ý AI — chưa xác nhận".
9. Cán bộ đối chiếu với giấy tờ gốc; với từng trường bấm "Đã đối chiếu ✓" (`POST /sessions/{id}/fields/{name}/confirm`), sửa giá trị nếu cần.
10. Cán bộ dùng nút "Sao chép" từng trường, dán vào form thật trên Cổng DVC ở tab khác.
11. Khi đủ trường bắt buộc, hệ thống chuyển `FIELDS_CONFIRMED`, mở nút "Đọc lại cho người dân".
12. Cán bộ bấm đọc lại (`POST /sessions/{id}/readback`); TTS phát bản tổng hợp.
13. Người dân nói "đúng rồi"; cán bộ bấm "Người dân đã xác nhận" (`POST /sessions/{id}/citizen-confirm`).
14. Cán bộ bấm nộp trên Cổng DVC (ngoài hệ thống), nhận mã hồ sơ.
15. Cán bộ nhập mã hồ sơ và đóng phiên (`POST /sessions/{id}/complete`).

**Hậu điều kiện:** Phiên ở trạng thái `COMPLETED`; audit log đầy đủ; audio buffer đã bị xóa.

**Luồng thay thế:** Không xác định được thủ tục từ transcript → cán bộ hỏi lại người dân bằng lời, chọn thủ tục thủ công. AI **không** tự chọn thủ tục.

---

### UC2 — Thiếu thông tin, phải hỏi lại (multi-turn)

| Mục | Nội dung |
|---|---|
| **Tác nhân** | Người dân, Cán bộ |
| **Tiền điều kiện** | Đang ở `SUGGESTED` hoặc `REVIEWING` |

**Luồng chính:**

1. Sau lần trích xuất đầu, một số trường bắt buộc trả về `MISSING` hoặc `UNCLEAR`.
2. Frontend làm nổi bật (viền đỏ) các trường thiếu, kèm gợi ý câu hỏi lấy từ `spoken_hint` trong catalog — ví dụ *"Xin ông bà cho biết ngày tháng năm sinh của cháu ạ?"*.
3. Cán bộ bấm "Hỏi lại"; phiên quay về `LISTENING`, `turn_number` tăng.
4. Người dân trả lời bổ sung; STT sinh transcript lượt mới.
5. Cán bộ bấm "Trích xuất tiếp"; backend gọi LLM với **transcript tích lũy + trạng thái trường hiện tại** (`known_fields`) và yêu cầu **chỉ điền các trường còn thiếu**.
6. Merge kết quả theo quy tắc ở Mục 7.1 bên dưới.
7. Lặp lại đến khi đủ trường bắt buộc, hoặc cán bộ nhập tay phần còn lại.

**Giới hạn:** tối đa 5 lượt trích xuất mỗi phiên (cấu hình được). Vượt ngưỡng → gợi ý cán bộ chuyển sang nhập tay hoàn toàn.

#### 7.1. Quy tắc gộp dữ liệu qua nhiều lượt

| Trạng thái hiện tại | Giá trị mới từ LLM | Kết quả |
|---|---|---|
| Trống / `MISSING` | Có giá trị | Nhận giá trị mới |
| Có giá trị, **chưa** được cán bộ xác nhận | Giá trị mới khác | Nhận giá trị mới, đánh dấu `changed_from_previous=true` để UI làm nổi bật |
| Có giá trị, **đã** được cán bộ xác nhận | Giá trị mới khác | **Giữ giá trị đã xác nhận**, sinh cảnh báo `conflict_with_confirmed` để cán bộ tự quyết |
| Có giá trị | `MISSING` ở lượt mới | Giữ giá trị cũ (không xóa dữ liệu) |

Quy tắc này ở `app/domain/merge.py`, là hàm thuần, có unit test riêng.

---

### UC3 — Nhiều thủ tục trong một lượt tiếp

| Mục | Nội dung |
|---|---|
| **Tác nhân** | Người dân, Cán bộ |
| **Ví dụ** | Người dân vừa muốn đăng ký kết hôn, vừa xin xác nhận cư trú |

**Luồng chính:**

1. Cán bộ tạo **phiên cha** (`parent_session`), chỉ chứa dữ liệu định danh cơ bản dùng chung.
2. Với mỗi thủ tục, cán bộ tạo **phiên con** trỏ tới `parent_session_id`.
3. Khi trích xuất phiên con, backend tự động điền sẵn các trường dùng chung đã được xác nhận ở phiên cha (họ tên, CCCD, số điện thoại, địa chỉ) — đánh dấu nguồn `source="parent_session"`.
4. Cán bộ **vẫn phải xác nhận lại** từng trường ở phiên con (NT-3 không có ngoại lệ) — nhưng không phải hỏi lại người dân.
5. Mỗi phiên con chạy độc lập theo UC1/UC2, có mã hồ sơ riêng.

**Trường được phép chia sẻ giữa các phiên** — danh sách trắng cố định trong code, không cấu hình động:
`ho_ten_nguoi_yeu_cau`, `ngay_sinh_nguoi_yeu_cau`, `so_cccd_nguoi_yeu_cau`, `so_dien_thoai`, `dia_chi_thuong_tru`.

---

### UC4 — Người dân không xác nhận, yêu cầu sửa

| Mục | Nội dung |
|---|---|
| **Tiền điều kiện** | Phiên ở trạng thái `READBACK` |

**Luồng chính:**

1. TTS đọc lại toàn bộ nội dung.
2. Người dân nói: *"Sai, tôi sinh năm 1991 chứ không phải 1990"*.
3. Cán bộ bấm "Người dân yêu cầu sửa"; phiên về `REVIEWING`.
4. Hai phương án cho cán bộ:
   - **Sửa nhanh (khuyến nghị):** cán bộ gõ trực tiếp giá trị đúng vào trường tương ứng và xác nhận lại. Không gọi AI.
   - **Sửa bằng giọng nói:** ghi âm câu sửa → gọi `POST /sessions/{id}/fields/{name}/amend` — endpoint riêng chỉ trích xuất **một trường**, không chạy lại toàn bộ pipeline.
5. Trường đã sửa bị đặt lại trạng thái xác nhận (`confirmed=false`), cán bộ phải xác nhận lại.
6. TTS đọc lại lần nữa (đánh dấu `readback_round=2`).
7. Lặp đến khi người dân xác nhận đúng.

**Ghi log:** mọi vòng đọc lại đều lưu — số vòng đọc lại là chỉ số chất lượng quan trọng (KPI-3).

---

### UC5 — STT nhận diện sai hoặc không rõ

| Mục | Nội dung |
|---|---|
| **Nguyên nhân** | Giọng địa phương, người cao tuổi nói không rõ, tiếng ồn tại quầy |

**Luồng chính:**

> **Quyết định thiết kế:** không dùng ngưỡng `confidence` tự động từ STT. Nhà cung cấp Blaze không cam kết trả field này trong response, nên hệ thống không xây cơ chế nghiệp vụ phụ thuộc vào một giá trị có thể không tồn tại. Việc phát hiện "câu nói chưa rõ" chuyển hoàn toàn sang **con người** — đúng tinh thần "AI gợi ý, con người quyết định" đã đặt ra ở Mục 2.

1. Transcript được hiển thị nguyên trạng cho cán bộ, không có bước lọc hay gắn nhãn tự động theo chất lượng.
2. Cán bộ đọc transcript (và có thể nghe lại đoạn ghi âm gốc nếu còn trong phiên) để tự đánh giá độ rõ ràng.
3. Nếu nghi ngờ sai/thiếu, cán bộ chọn một trong ba:
   - Hỏi lại người dân (quay về `LISTENING`).
   - Tự sửa transcript (`PATCH /sessions/{id}/turns/{turn_id}` — ghi log rõ là cán bộ sửa).
   - Gắn cờ "chưa rõ" trên lượt đó (`transcript_flagged_by_staff`) để phục vụ thống kê, rồi bỏ qua và nhập thẳng giá trị trường.
4. Mọi lượt thoại đều có sẵn nút "Sửa" và "Hỏi lại" — không có sự phân biệt hiển thị nào giữa lượt "rõ" và "chưa rõ" vì hệ thống không tự phán đoán được điều đó.

**Xử lý bổ sung:**
- Không có cơ chế tự động chặn gọi extraction theo chất lượng STT — cán bộ luôn là người quyết định transcript nào đủ dùng.
- Theo dõi số lần cán bộ gắn cờ "chưa rõ" theo cán bộ/theo ca để phát hiện sớm khu vực có vấn đề chất lượng STT (ồn, giọng địa phương) mà không cần một ngưỡng số cứng nhắc.

---

### UC6 — Lỗi dịch vụ AI (LLM / STT / TTS)

| Loại lỗi | Hành vi hệ thống | Trải nghiệm cán bộ |
|---|---|---|
| LLM timeout | Retry 2 lần với exponential backoff (1s, 3s), tổng timeout 30s | Hiện spinner kèm "Đang xử lý…"; sau khi hết retry → thông báo lỗi |
| LLM trả JSON sai định dạng | Thử sửa 1 lần (yêu cầu mô hình trả lại đúng JSON); vẫn hỏng → coi như thất bại | "AI tạm thời không hỗ trợ được, vui lòng nhập tay" |
| LLM trả trường không có trong schema | Loại bỏ trường lạ, ghi log `schema_violation` | Trường lạ không hiển thị |
| LLM trả giá trị không truy vết được về transcript | Hạ mức tin cậy xuống `low`, gắn cờ `unverifiable` | Hiển thị viền cam + cảnh báo "Không tìm thấy trong lời nói — cần kiểm tra kỹ" |
| STT lỗi | Không retry (audio đã trôi qua) | "Không ghi âm được, vui lòng thử lại hoặc nhập tay" |
| TTS lỗi | Fallback sang hiển thị văn bản cỡ chữ lớn để người dân tự đọc | "Không phát được âm thanh — mời người dân đọc trên màn hình" |
| Mất kết nối mạng ra ngoài | Circuit breaker mở sau 5 lỗi liên tiếp, đóng lại sau 60s | Banner "Chế độ nhập tay" trên toàn giao diện |
| PostgreSQL lỗi | Trả 503, **không** cho tạo phiên mới | "Hệ thống tạm thời gián đoạn" |
| Redis lỗi | Suy giảm mềm: dùng PostgreSQL làm nơi lưu trạng thái | Người dùng không thấy khác biệt (chậm hơn chút) |

**Nguyên tắc bao trùm (NT-8):** trong mọi tình huống lỗi, cán bộ vẫn phải hoàn tất được phiên bằng cách nhập tay. Không có lỗi AI nào được phép chặn nghiệp vụ.

---

### UC7 — Tra cứu audit log (mới bổ sung)

| Mục | Nội dung |
|---|---|
| **Tác nhân** | Cán bộ quản lý / cán bộ kiểm tra |
| **Mục đích** | Đáp ứng yêu cầu "ghi nhận đầy đủ để phục vụ thống kê, kiểm tra, truy xuất khi cần thiết" |

**Luồng:** Đăng nhập với vai trò `supervisor` → tra cứu phiên theo ngày / cán bộ / thủ tục / mã hồ sơ → xem dòng thời gian đầy đủ: transcript, prompt gửi AI, response nhận về, từng lần cán bộ xác nhận, xác nhận của người dân → xuất PDF/CSV khi cần.

**Kiểm soát:** chỉ vai trò `supervisor` và `auditor` truy cập được; **mỗi lần xem cũng được ghi log** (`action=audit_viewed`).

---

### UC8 — Người dân từ chối sử dụng AI (mới bổ sung)

| Mục | Nội dung |
|---|---|
| **Cơ sở** | Báo cáo sáng kiến nêu "người dân cần đồng thuận, tin tưởng"; xử lý dữ liệu cá nhân cần có sự đồng ý |

**Luồng:**

1. Trước khi ghi âm, cán bộ đọc thông báo ngắn: *"Chúng tôi sẽ dùng công cụ AI ghi lại lời nói để hỗ trợ điền hồ sơ. Bản ghi âm sẽ được xóa ngay sau khi chuyển thành văn bản. Ông/bà có đồng ý không ạ?"*
2. Cán bộ tích ô "Người dân đã đồng ý" — **bắt buộc** trước khi mở được WebSocket ghi âm.
3. Nếu người dân từ chối → cán bộ tạo phiên chế độ `manual_only`, không có thành phần AI nào được kích hoạt, nhưng vẫn dùng được checklist thành phần hồ sơ từ catalog.
4. Ghi log lựa chọn của người dân.

---

## 8. Thiết kế dữ liệu

### 8.1. Sơ đồ quan hệ

```
staff_users ──┐
              │
              ▼
       ┌─────────────┐
       │  sessions   │──┐ (parent_session_id, tự tham chiếu — UC3)
       └──────┬──────┘◀─┘
              │
    ┌─────────┼─────────┬──────────────┬────────────────┐
    ▼         ▼         ▼              ▼                ▼
voice_turns  extractions  field_states  citizen_confirmations  audit_log
    │            │            │
    │            ▼            │
    └───▶ extraction_fields ◀─┘
```

### 8.2. Định nghĩa bảng

```sql
-- ============ Người dùng nội bộ ============
CREATE TABLE staff_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64) UNIQUE NOT NULL,
    full_name       VARCHAR(200) NOT NULL,
    role            VARCHAR(20) NOT NULL,     -- staff | supervisor | auditor | admin
    unit            VARCHAR(200),             -- ví dụ: Tổ CĐS cộng đồng phường Yên Sở
    is_active       BOOLEAN NOT NULL DEFAULT true,
    password_hash   TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

-- ============ Phiên làm việc ============
CREATE TABLE sessions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_session_id   UUID REFERENCES sessions(id),   -- UC3
    staff_id            UUID NOT NULL REFERENCES staff_users(id),
    procedure_code      VARCHAR(100),                   -- NULL cho phiên cha
    catalog_version     VARCHAR(20),                    -- truy vết catalog đã dùng
    state               VARCHAR(30) NOT NULL DEFAULT 'CREATED',
    mode                VARCHAR(20) NOT NULL DEFAULT 'ai_assisted', -- ai_assisted | manual_only
    citizen_consent     BOOLEAN NOT NULL DEFAULT false, -- UC8
    consent_recorded_at TIMESTAMPTZ,
    citizen_ref         VARCHAR(64),                    -- mã tham chiếu nội bộ, KHÔNG phải CCCD
    dossier_code        VARCHAR(100),                   -- mã hồ sơ trên Cổng DVC, cán bộ nhập
    cancel_reason       TEXT,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    duration_ms         INTEGER GENERATED ALWAYS AS (
                            EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000
                        ) STORED,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_state CHECK (state IN (
        'CREATED','LISTENING','PROCEDURE_SELECTED','EXTRACTING','SUGGESTED',
        'AI_UNAVAILABLE','REVIEWING','FIELDS_CONFIRMED','READBACK',
        'CITIZEN_CONFIRMED','COMPLETED','CANCELLED'))
);
CREATE INDEX idx_sessions_staff_date ON sessions(staff_id, started_at DESC);
CREATE INDEX idx_sessions_procedure  ON sessions(procedure_code, started_at DESC);
CREATE INDEX idx_sessions_state      ON sessions(state) WHERE state NOT IN ('COMPLETED','CANCELLED');
CREATE INDEX idx_sessions_parent     ON sessions(parent_session_id) WHERE parent_session_id IS NOT NULL;

-- ============ Lượt thoại ============
CREATE TABLE voice_turns (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn_number         INTEGER NOT NULL,
    raw_transcript      TEXT,                   -- văn bản gốc từ STT
    edited_transcript   TEXT,                   -- bản cán bộ sửa (UC5), NULL nếu không sửa
    flagged_by_staff    BOOLEAN NOT NULL DEFAULT false,  -- cán bộ chủ động đánh dấu "chưa rõ" (thay cho ngưỡng confidence tự động — Blaze không cam kết trả field này)
    audio_duration_ms   INTEGER,
    audio_deleted_at    TIMESTAMPTZ,            -- bằng chứng đã xóa bản ghi âm
    stt_provider        VARCHAR(50),
    stt_latency_ms      INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, turn_number)
);
CREATE INDEX idx_turns_session ON voice_turns(session_id, turn_number);

-- ============ Lần gọi LLM ============
CREATE TABLE extractions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    voice_turn_id       UUID REFERENCES voice_turns(id),
    attempt_number      INTEGER NOT NULL DEFAULT 1,
    model_name          VARCHAR(100),
    prompt_hash         VARCHAR(64),            -- SHA-256 của prompt (không lưu nguyên văn PII)
    prompt_redacted     TEXT,                   -- prompt ĐÃ che dữ liệu nhạy cảm, phục vụ kiểm tra
    raw_response        TEXT,                   -- phản hồi thô của mô hình
    parsed_json         JSONB,                  -- sau khi parse và validate
    warnings            JSONB,                  -- mảng cảnh báo
    status              VARCHAR(20) NOT NULL,   -- success | parse_failed | schema_violation | api_error | timeout
    error_detail        TEXT,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    latency_ms          INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_extractions_session ON extractions(session_id, created_at);
CREATE INDEX idx_extractions_status  ON extractions(status) WHERE status <> 'success';

-- ============ Trạng thái hiện tại của từng trường ============
-- Bảng này là "sổ cái" trạng thái, một dòng cho mỗi trường của mỗi phiên
CREATE TABLE field_states (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    field_name          VARCHAR(100) NOT NULL,
    suggested_value     TEXT,                   -- giá trị AI gợi ý (mới nhất)
    suggested_by        VARCHAR(30),            -- llm | parent_session | manual
    ai_confidence       VARCHAR(10),            -- high | medium | low | null
    evidence_span       TEXT,                   -- đoạn transcript làm căn cứ (NT-5)
    confirmed_value     TEXT,                   -- giá trị cán bộ chốt (có thể khác gợi ý)
    is_confirmed        BOOLEAN NOT NULL DEFAULT false,
    confirmed_by        UUID REFERENCES staff_users(id),
    confirmed_at        TIMESTAMPTZ,
    was_edited          BOOLEAN NOT NULL DEFAULT false,  -- cán bộ có sửa khác gợi ý không
    validation_status   VARCHAR(20),            -- ok | missing | unclear | format_error | conflict
    validation_message  TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, field_name)
);
CREATE INDEX idx_field_states_session ON field_states(session_id);

-- ============ Lịch sử thay đổi trường (append-only) ============
CREATE TABLE field_history (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL,
    field_name      VARCHAR(100) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    change_source   VARCHAR(30) NOT NULL,   -- llm_extraction | staff_edit | staff_confirm | parent_session | amend
    changed_by      UUID,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_field_history_session ON field_history(session_id, changed_at);

-- ============ Xác nhận của người dân ============
CREATE TABLE citizen_confirmations (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    readback_round      INTEGER NOT NULL DEFAULT 1,
    readback_text       TEXT NOT NULL,      -- chính xác nội dung đã đọc cho người dân
    readback_method     VARCHAR(20),        -- tts_audio | screen_text
    confirmed           BOOLEAN NOT NULL,
    confirmation_note   TEXT,               -- transcript lời xác nhận, hoặc lý do từ chối
    recorded_by         UUID NOT NULL REFERENCES staff_users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_citizen_conf_session ON citizen_confirmations(session_id, readback_round);

-- ============ Audit log tổng (append-only, KHÔNG cho UPDATE/DELETE) ============
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID,
    actor_type      VARCHAR(20) NOT NULL,   -- system | staff | citizen
    actor_id        VARCHAR(64),
    action          VARCHAR(100) NOT NULL,
    detail          JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_session ON audit_log(session_id, created_at);
CREATE INDEX idx_audit_action  ON audit_log(action, created_at DESC);
CREATE INDEX idx_audit_actor   ON audit_log(actor_id, created_at DESC);

-- Chặn sửa/xóa audit log ở tầng database
REVOKE UPDATE, DELETE ON audit_log FROM app_user;
REVOKE UPDATE, DELETE ON field_history FROM app_user;
```

### 8.3. Danh mục hành động ghi audit

| Nhóm | `action` |
|---|---|
| Phiên | `session_created`, `session_state_changed`, `session_completed`, `session_cancelled` |
| Đồng ý | `citizen_consent_recorded`, `citizen_consent_declined` |
| Giọng nói | `recording_started`, `recording_stopped`, `transcript_received`, `transcript_flagged_by_staff`, `transcript_edited_by_staff`, `audio_buffer_deleted` |
| AI | `extraction_requested`, `extraction_succeeded`, `extraction_failed`, `schema_violation_detected`, `unverifiable_value_flagged` |
| Cán bộ | `field_confirmed`, `field_edited`, `field_unconfirmed`, `manual_mode_selected` |
| Người dân | `readback_played`, `citizen_confirmed`, `citizen_rejected` |
| Hồ sơ | `dossier_code_recorded` |
| Kiểm tra | `audit_viewed`, `audit_exported` |
| Bảo mật | `login_succeeded`, `login_failed`, `permission_denied` |

### 8.4. Vòng đời và thời hạn lưu dữ liệu

| Loại dữ liệu | Nơi lưu | Thời hạn | Cơ chế |
|---|---|---|---|
| Audio thô | Redis (chỉ trong RAM) | **TTL 120 giây**, xóa ngay khi có transcript | Redis TTL + xóa tường minh, ghi `audio_deleted_at` |
| Transcript | PostgreSQL | Theo thời hạn lưu trữ do phường quyết định (**cần chốt** — Mục 20) | Job dọn dẹp định kỳ |
| Giá trị trường (`field_states`) | PostgreSQL | Như transcript | Job dọn dẹp |
| Prompt/response LLM | PostgreSQL (đã che PII) | Như transcript | Job dọn dẹp |
| Audit log | PostgreSQL | **Dài hơn dữ liệu nghiệp vụ** (đề xuất tối thiểu 2 năm) | Không xóa tự động |
| Thống kê tổng hợp | Bảng riêng, đã ẩn danh | Không giới hạn | Job tổng hợp hằng ngày |

**Nguyên tắc:** khi hết hạn, dữ liệu cá nhân bị xóa nhưng audit log giữ lại **dạng đã ẩn danh** (thay giá trị bằng `[đã xóa theo thời hạn lưu trữ]`) để vẫn chứng minh được quy trình đã diễn ra đúng.

---

## 9. Đặc tả API

### 9.1. Quy ước chung

- Đường dẫn gốc: `/api/v1`
- Xác thực: JWT trong header `Authorization: Bearer <token>`, hạn 8 giờ (một ca làm việc)
- Mọi request có `X-Request-ID`; nếu thiếu, server tự sinh
- Lỗi trả theo định dạng thống nhất:

```json
{
  "error": {
    "code": "EXTRACTION_FAILED",
    "message": "AI tạm thời không hỗ trợ được, vui lòng nhập tay",
    "detail": "LLM timeout after 3 attempts",
    "request_id": "req_01J...",
    "fallback_available": true
  }
}
```

### 9.2. Bảng endpoint

| Method | Đường dẫn | Vai trò | Mô tả |
|---|---|---|---|
| **Xác thực** |
| POST | `/auth/login` | — | Đăng nhập cán bộ |
| POST | `/auth/logout` | mọi vai trò | Đăng xuất |
| GET | `/auth/me` | mọi vai trò | Thông tin người đang đăng nhập |
| **Danh mục** |
| GET | `/procedures` | staff | Danh sách thủ tục đang hiệu lực |
| GET | `/procedures/{code}` | staff | Chi tiết: field schema + thành phần hồ sơ |
| **Phiên** |
| POST | `/sessions` | staff | Tạo phiên mới. Body: `{parent_session_id?, mode}` |
| GET | `/sessions/{id}` | staff | Trạng thái đầy đủ của phiên |
| POST | `/sessions/{id}/consent` | staff | Ghi nhận đồng ý của người dân (UC8) |
| POST | `/sessions/{id}/procedure` | staff | Chọn thủ tục (B2). Body: `{procedure_code}` |
| POST | `/sessions/{id}/cancel` | staff | Hủy phiên. Body: `{reason}` |
| POST | `/sessions/{id}/complete` | staff | Đóng phiên. Body: `{dossier_code}` |
| **Giọng nói** |
| WS | `/sessions/{id}/voice` | staff | WebSocket streaming audio → transcript |
| GET | `/sessions/{id}/turns` | staff | Danh sách lượt thoại |
| PATCH | `/sessions/{id}/turns/{turn_id}` | staff | Cán bộ sửa transcript (UC5) |
| **Trích xuất** |
| POST | `/sessions/{id}/extract` | staff | Gọi LLM trích xuất (B3+B4) |
| GET | `/sessions/{id}/extractions` | staff | Lịch sử các lần trích xuất |
| **Trường dữ liệu** |
| GET | `/sessions/{id}/fields` | staff | Trạng thái hiện tại của mọi trường |
| POST | `/sessions/{id}/fields/{name}/confirm` | staff | Xác nhận **một** trường. Body: `{value}` |
| POST | `/sessions/{id}/fields/{name}/unconfirm` | staff | Bỏ xác nhận một trường |
| POST | `/sessions/{id}/fields/{name}/amend` | staff | Sửa một trường bằng giọng nói (UC4) |
| **Đọc lại và xác nhận** |
| POST | `/sessions/{id}/readback` | staff | Sinh nội dung + audio TTS |
| GET | `/sessions/{id}/readback/audio` | staff | Tải file audio TTS |
| POST | `/sessions/{id}/citizen-confirm` | staff | Ghi nhận xác nhận/từ chối của người dân |
| **Kiểm tra & thống kê** |
| GET | `/sessions/{id}/audit` | supervisor, auditor | Dòng thời gian đầy đủ của phiên (UC7) |
| GET | `/audit/sessions` | supervisor, auditor | Tra cứu phiên theo bộ lọc |
| GET | `/audit/export` | auditor | Xuất CSV/PDF |
| GET | `/stats/daily` | supervisor | Thống kê ngày (KPI-2) |
| GET | `/stats/procedures` | supervisor | Phân bố theo thủ tục (KPI-6) |
| GET | `/stats/warnings` | supervisor | Lỗi kê khai thường gặp (KPI-6) |
| **Vận hành** |
| GET | `/health` | — | Liveness |
| GET | `/health/ready` | — | Readiness (DB, Redis, các dịch vụ AI) |

### 9.3. Chi tiết các endpoint quan trọng

#### `POST /api/v1/sessions/{id}/extract`

**Request:**
```json
{
  "include_turns": [1, 2, 3],
  "only_missing_fields": true
}
```

**Response 200:**
```json
{
  "extraction_id": "8f3a...",
  "procedure_code": "dang_ky_khai_sinh",
  "catalog_version": "2026.08.1",
  "fields": [
    {
      "name": "ho_ten_nguoi_duoc_khai_sinh",
      "label": "Họ và tên người được khai sinh",
      "suggested_value": "Nguyễn Văn An",
      "confidence": "high",
      "evidence_span": "đăng ký khai sinh cho con tôi tên Nguyễn Văn An",
      "validation_status": "ok",
      "required": true,
      "is_confirmed": false
    },
    {
      "name": "ngay_sinh",
      "label": "Ngày, tháng, năm sinh",
      "suggested_value": null,
      "confidence": null,
      "evidence_span": null,
      "validation_status": "missing",
      "validation_message": "Người dân chưa nói ngày sinh",
      "required": true,
      "is_confirmed": false
    },
    {
      "name": "dia_chi_thuong_tru",
      "label": "Địa chỉ thường trú",
      "suggested_value": "Yên Sở",
      "confidence": "low",
      "evidence_span": "nhà tôi ở Yên Sở",
      "validation_status": "unclear",
      "validation_message": "Địa chỉ chưa đầy đủ số nhà, tên đường — cần hỏi lại",
      "required": true,
      "is_confirmed": false
    }
  ],
  "warnings": [
    {"severity": "error",   "field": "ngay_sinh",          "message": "Thiếu ngày sinh — bắt buộc"},
    {"severity": "warning", "field": "dia_chi_thuong_tru", "message": "Địa chỉ chưa rõ ràng, cần xác nhận"}
  ],
  "required_documents": [
    {"name": "Giấy chứng sinh", "note": "Bản chính do cơ sở y tế cấp..."},
    {"name": "Giấy tờ tùy thân của người đi đăng ký", "note": "CCCD hoặc hộ chiếu còn hạn"}
  ],
  "suggested_questions": [
    "Xin ông/bà cho biết cháu sinh ngày tháng năm nào ạ?",
    "Xin ông/bà cho biết địa chỉ thường trú đầy đủ gồm số nhà, tên đường ạ?"
  ],
  "meta": {"model": "claude-sonnet-5", "latency_ms": 1840, "attempt": 1}
}
```

**Response 503 (UC6):**
```json
{
  "error": {
    "code": "AI_UNAVAILABLE",
    "message": "AI tạm thời không hỗ trợ được, vui lòng nhập tay",
    "request_id": "req_01J...",
    "fallback_available": true
  }
}
```

#### `WS /api/v1/sessions/{id}/voice`

**Client → Server:**
```json
{"type": "start", "sample_rate": 16000, "encoding": "pcm_s16le"}
{"type": "audio", "seq": 1, "data": "<base64>"}
{"type": "stop"}
```

**Server → Client:**
```json
{"type": "partial",  "text": "tôi muốn đăng ký khai"}
{"type": "final",    "turn_id": "...", "turn_number": 1, "text": "Tôi muốn đăng ký khai sinh cho con tôi"}
{"type": "error",    "code": "STT_UNAVAILABLE", "message": "Không ghi âm được, vui lòng nhập tay"}
{"type": "audio_deleted", "turn_id": "..."}
```

> Không có message `confidence`/`low_confidence`/`warning` tự động — Blaze không cam kết trả độ tin cậy trong response STT. Cán bộ tự đánh giá transcript qua giao diện (xem UC5).

#### `POST /api/v1/sessions/{id}/fields/{name}/confirm`

```json
// Request
{"value": "Nguyễn Văn An", "note": "Đã đối chiếu Giấy chứng sinh"}

// Response 200
{
  "field_name": "ho_ten_nguoi_duoc_khai_sinh",
  "confirmed_value": "Nguyễn Văn An",
  "was_edited": false,
  "confirmed_by": "Phạm Thị Hà",
  "confirmed_at": "2026-09-15T09:12:33+07:00",
  "session_state": "REVIEWING",
  "remaining_required_fields": ["ngay_sinh", "dia_chi_thuong_tru"]
}
```

> **Không có endpoint bulk confirm.** Đây là ràng buộc thiết kế theo NT-3, không phải thiếu sót.

---

## 10. Thiết kế tầng AI

### 10.1. Kiến trúc chống ảo giác (hallucination)

Bốn lớp bảo vệ, xếp chồng:

```
┌────────────────────────────────────────────────────────┐
│ Lớp 1 — Ràng buộc trong prompt                          │
│  • Field schema truyền vào từ catalog tĩnh              │
│  • Cấm suy đoán, bắt buộc trả MISSING/UNCLEAR           │
│  • Bắt buộc trích dẫn đoạn transcript làm căn cứ        │
└────────────────────┬───────────────────────────────────┘
                     ▼
┌────────────────────────────────────────────────────────┐
│ Lớp 2 — Ràng buộc cấu trúc output                       │
│  • Validate bằng Pydantic theo schema chặt              │
│  • Loại bỏ trường không có trong catalog                │
│  • Ép kiểu dữ liệu đúng định dạng                       │
└────────────────────┬───────────────────────────────────┘
                     ▼
┌────────────────────────────────────────────────────────┐
│ Lớp 3 — Kiểm chứng nguồn gốc (grounding check)          │
│  • Mỗi giá trị phải truy vết được về transcript         │
│  • Không tìm thấy → hạ confidence + gắn cờ              │
└────────────────────┬───────────────────────────────────┘
                     ▼
┌────────────────────────────────────────────────────────┐
│ Lớp 4 — Con người kiểm soát (quyết định cuối)           │
│  • Cán bộ đối chiếu giấy tờ gốc, xác nhận từng trường   │
│  • Người dân nghe đọc lại và xác nhận                   │
└────────────────────────────────────────────────────────┘
```

### 10.2. System prompt

```
Bạn là công cụ trích xuất thông tin hành chính, hỗ trợ cán bộ tại Tổ chuyển
đổi số cộng đồng phường Yên Sở. Bạn KHÔNG phải là người ra quyết định.

NHIỆM VỤ DUY NHẤT: đọc lời nói của người dân đã được chuyển thành văn bản,
và điền các trường dữ liệu được liệt kê trong danh sách cho sẵn.

QUY TẮC BẮT BUỘC:
1. CHỈ trích xuất thông tin người dân đã nói rõ ràng trong đoạn văn bản.
2. TUYỆT ĐỐI KHÔNG suy đoán, không điền giá trị mặc định, không dùng kiến
   thức bên ngoài để bổ sung thông tin.
3. Nếu một trường không có thông tin → "MISSING".
   Nếu có nhắc tới nhưng không đủ rõ để dùng → "UNCLEAR" kèm lý do.
4. Với MỖI giá trị trích xuất được, phải trích dẫn nguyên văn đoạn trong
   văn bản làm căn cứ (trường "evidence"). Không có căn cứ thì không được
   điền giá trị.
5. CHỈ điền các trường có trong danh sách được cung cấp. KHÔNG tự thêm
   trường mới.
6. KHÔNG đưa ra tư vấn pháp lý, KHÔNG kết luận hồ sơ hợp lệ hay không,
   KHÔNG nêu quy định pháp luật. Đó là việc của cán bộ.
7. KHÔNG tự quyết định thủ tục cần giấy tờ gì — danh sách giấy tờ do hệ
   thống cung cấp, không phải do bạn sinh ra.
8. Chỉ trả lời bằng JSON hợp lệ, không thêm bất kỳ văn bản giải thích nào.

VỀ ĐỘ TIN CẬY (confidence):
- "high": người dân nói rõ ràng, trực tiếp, không mơ hồ.
- "medium": suy ra được từ ngữ cảnh nhưng chắc chắn hợp lý.
- "low": có dấu hiệu nhưng mơ hồ, cần cán bộ kiểm tra kỹ.

LƯU Ý: đây là dữ liệu của người dân thật, dùng cho hồ sơ hành chính có giá
trị pháp lý. Một giá trị bịa ra có thể khiến người dân phải đi lại nhiều lần.
Thà để MISSING còn hơn đoán sai.
```

### 10.3. Cấu trúc user message

```
### Loại thủ tục
Đăng ký khai sinh (mã: dang_ky_khai_sinh)

### Các trường cần trích xuất
[
  {"name": "ho_ten_nguoi_duoc_khai_sinh", "label": "Họ và tên người được khai sinh", "type": "person_name", "required": true},
  {"name": "ngay_sinh", "label": "Ngày, tháng, năm sinh", "type": "date", "required": true},
  ...
]

### Các trường đã có giá trị (đã được cán bộ xác nhận — KHÔNG thay đổi)
{"ho_ten_me": "Trần Thị Bình"}

### Lời nói của người dân (đã chuyển thành văn bản)
---
[Lượt 1] Tôi muốn đăng ký khai sinh cho con tôi.
[Lượt 2] Cháu tên là Nguyễn Văn An, sinh ngày mùng 5 tháng 3 năm nay, là con trai.
---

### Yêu cầu
Trả về JSON đúng định dạng schema đã cho.
```

### 10.4. Schema output (Pydantic)

```python
# app/domain/extraction_schema.py
from typing import Literal
from pydantic import BaseModel, Field

Confidence = Literal["high", "medium", "low"]
FieldStatus = Literal["extracted", "missing", "unclear"]

class ExtractedField(BaseModel):
    name: str
    status: FieldStatus
    value: str | None = None
    confidence: Confidence | None = None
    evidence: str | None = Field(
        default=None,
        description="Đoạn nguyên văn trong transcript làm căn cứ",
    )
    reason: str | None = Field(
        default=None,
        description="Lý do khi status là unclear",
    )

class ExtractionResult(BaseModel):
    fields: list[ExtractedField]
    observations: list[str] = Field(
        default_factory=list,
        description="Ghi nhận trung lập, KHÔNG phải kết luận pháp lý",
    )
```

**Hậu kiểm bắt buộc sau khi parse** (`app/services/grounding.py`):

```python
def verify_grounding(result: ExtractionResult, transcript: str,
                     schema: list[FieldSpec]) -> ExtractionResult:
    """
    1. Loại bỏ mọi trường không có trong `schema` (NT-4).
    2. Với trường status='extracted': nếu `evidence` rỗng HOẶC không xuất hiện
       trong transcript (so khớp mờ, ngưỡng 0.85) → hạ confidence xuống 'low'
       và gắn cờ unverifiable.
    3. Ghi log 'schema_violation_detected' / 'unverifiable_value_flagged'.
    """
```

### 10.5. Tầng validator (độc lập với AI)

Chạy **sau** khi có kết quả AI, và cũng chạy khi cán bộ nhập tay:

| Validator | Áp dụng cho | Quy tắc |
|---|---|---|
| `cccd_12_digits` | `national_id` | Đúng 12 chữ số |
| `vn_phone_10_digits` | `phone` | 10 chữ số, đầu số hợp lệ (03/05/07/08/09) |
| `date_not_future` | `date` | Không được là ngày tương lai |
| `date_reasonable_birth` | `date` | Trong khoảng 130 năm trở lại |
| `vietnamese_name` | `person_name` | Chỉ chữ cái tiếng Việt và khoảng trắng, 2–50 ký tự |
| `in_options` | `enum` | Thuộc danh sách `options` |
| `address_completeness` | `address` | Cảnh báo (không chặn) nếu thiếu số nhà/đường/phường |
| `required_present` | mọi trường | Trường `required=true` phải có giá trị mới cho qua `FIELDS_CONFIRMED` |

Validator ở `app/domain/validators.py`, là hàm thuần, có unit test đầy đủ. **Đây là nơi kiểm tra định dạng, không phải LLM** — LLM không đáng tin cho việc này.

### 10.6. Cấu hình gọi LLM

```python
EXTRACTION_CONFIG = {
    "model": "claude-sonnet-5",
    "max_tokens": 2000,
    "temperature": 0,          # tất định — không sáng tạo với dữ liệu công dân
    "timeout_seconds": 30,
    "max_retries": 2,
    "retry_backoff": [1.0, 3.0],
}
```

**Ghi chú kỹ thuật:** dùng tính năng structured output / tool-use của Claude API để ép định dạng JSON thay vì chỉ dựa vào chỉ dẫn trong prompt — giảm đáng kể lỗi parse. Chi tiết cú pháp tra tài liệu Claude API khi hiện thực.

### 10.7. Che dữ liệu nhạy cảm trước khi gửi LLM

```python
# app/services/redactor.py
class PIIRedactor:
    """
    Che dữ liệu nhạy cảm trong transcript trước khi gửi ra dịch vụ bên ngoài,
    theo cấu hình `redact_to_llm` của từng trường trong catalog (NT-6).

    Chiến lược cho số CCCD:
      - Nhận diện chuỗi 12 chữ số liên tiếp trong transcript.
      - Thay bằng placeholder: [CCCD_1], [CCCD_2], ...
      - Giữ bảng ánh xạ trong RAM của phiên (KHÔNG lưu DB).
      - Sau khi có kết quả, thay placeholder về giá trị thật ở phía backend.

    Kết quả: LLM vẫn "thấy" có một số CCCD ở vị trí đó để trích xuất đúng
    trường, nhưng không nhận được con số thật.
    """
```

> **Cần quyết định (Mục 20):** áp dụng masking cho những trường nào. Che CCCD là hợp lý và ít ảnh hưởng độ chính xác. Che họ tên và địa chỉ sẽ làm giảm chất lượng trích xuất đáng kể — cần cân nhắc giữa quyền riêng tư và tính hữu dụng, và cần ý kiến của bộ phận pháp chế.

---

## 11. Thiết kế Frontend cán bộ

### 11.1. Bố cục màn hình làm việc

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Trợ lý giọng nói AI — Phường Yên Sở       Cán bộ: Phạm Thị Hà   [Thoát] │
├──────────────────────────────────────────────────────────────────────────┤
│  Phiên #a3f8  •  Đăng ký khai sinh  •  Trạng thái: Đang rà soát          │
├────────────────────────────────┬─────────────────────────────────────────┤
│  LỜI NÓI CỦA NGƯỜI DÂN         │  THÔNG TIN GỢI Ý  ⚠ Chưa xác nhận       │
│                                 │                                         │
│  ┌───────────────────────────┐ │  ┌────────────────────────────────────┐│
│  │ [Lượt 1]                  │ │  │ Họ tên người được khai sinh        ││
│  │ Tôi muốn đăng ký khai     │ │  │ ┌────────────────────────┐ ✓ Cao   ││
│  │ sinh cho con tôi tên      │ │  │ │ Nguyễn Văn An          │ [Chép]  ││
│  │ Nguyễn Văn An             │ │  │ └────────────────────────┘         ││
│  │                    ✓ 0.91 │ │  │ 📎 "...con tôi tên Nguyễn Văn An"  ││
│  ├───────────────────────────┤ │  │           [ ✓ Đã đối chiếu ]       ││
│  │ [Lượt 2]  ⚠ Chưa rõ       │ │  ├────────────────────────────────────┤│
│  │ ...nhà tôi ở Yên Sở...    │ │  │ Ngày, tháng, năm sinh   ❗ BẮT BUỘC ││
│  │                    ⚠ 0.52 │ │  │ ┌────────────────────────┐         ││
│  │        [Sửa] [Hỏi lại]    │ │  │ │ (chưa có thông tin)    │         ││
│  └───────────────────────────┘ │  │ └────────────────────────┘         ││
│                                 │  │ 💬 "Xin ông/bà cho biết cháu sinh  ││
│  ┌───────────────────────────┐ │  │    ngày tháng năm nào ạ?"          ││
│  │   🎤  BẮT ĐẦU GHI ÂM      │ │  │           [ 🎤 Hỏi lại ]           ││
│  └───────────────────────────┘ │  ├────────────────────────────────────┤│
│                                 │  │ Địa chỉ thường trú      ⚠ Chưa rõ  ││
│  ── THÀNH PHẦN HỒ SƠ ──        │  │ ┌────────────────────────┐         ││
│  ☐ Giấy chứng sinh (bản chính) │  │ │ Yên Sở                 │ [Chép]  ││
│  ☐ CCCD người đi đăng ký       │  │ └────────────────────────┘         ││
│  ☐ Giấy đăng ký kết hôn        │  │ ⚠ Thiếu số nhà, tên đường          ││
│                                 │  │           [ ✓ Đã đối chiếu ]       ││
│                                 │  └────────────────────────────────────┘│
│                                 │  Đã xác nhận: 3/7 trường bắt buộc      │
│                                 │  ┌────────────────────────────────────┐│
│                                 │  │ 🔊 ĐỌC LẠI CHO NGƯỜI DÂN (khóa)    ││
│                                 │  └────────────────────────────────────┘│
├────────────────────────────────┴─────────────────────────────────────────┤
│  ⚠ Đây là GỢI Ý của AI. Cán bộ phải đối chiếu giấy tờ gốc trước khi dùng.│
└──────────────────────────────────────────────────────────────────────────┘
```

### 11.2. Quy tắc giao diện bắt buộc

| # | Quy tắc | Lý do |
|---|---|---|
| GD-1 | Mọi giá trị AI gợi ý hiển thị trên **nền màu khác** kèm nhãn "Gợi ý AI — chưa xác nhận" | NT-2 — phân biệt rõ gợi ý và dữ liệu chính thức |
| GD-2 | **Không có** nút "Xác nhận tất cả" | NT-3 |
| GD-3 | Nút "Đọc lại cho người dân" bị khóa cho tới khi đủ trường bắt buộc | Ngăn bỏ sót bước |
| GD-4 | Mỗi trường có nút "Chép" riêng, sao chép vào clipboard để dán sang Cổng DVC | Đúng luồng cán bộ nhập tay |
| GD-5 | Hiển thị đoạn transcript làm căn cứ (`evidence_span`) ngay dưới mỗi trường | Cán bộ kiểm chứng được nguồn gốc giá trị |
| GD-6 | Mọi lượt transcript đều có sẵn nút "Sửa"/"Hỏi lại"/"Gắn cờ chưa rõ" — không có phân loại tự động vì không dùng ngưỡng confidence | UC5 |
| GD-7 | Banner cố định ở chân màn hình nhắc trách nhiệm đối chiếu | Nguyên tắc "AI không thay thế cán bộ" |
| GD-8 | Khi AI lỗi, hiện banner "Chế độ nhập tay" và mọi trường vẫn nhập được | NT-8, UC6 |
| GD-9 | Cỡ chữ tối thiểu 16px, tương phản đạt WCAG AA | Cán bộ dùng liên tục cả ngày |
| GD-10 | Toàn bộ nhãn tiếng Việt có dấu, không viết tắt kỹ thuật | Người dùng là cán bộ hành chính, không phải kỹ sư |

### 11.3. Danh sách màn hình

| Màn hình | Đường dẫn | Vai trò |
|---|---|---|
| Đăng nhập | `/login` | — |
| Bảng điều khiển (danh sách phiên trong ngày) | `/` | staff |
| Tạo phiên mới + ghi nhận đồng ý | `/sessions/new` | staff |
| Màn hình làm việc chính | `/sessions/:id` | staff |
| Đọc lại & xác nhận | `/sessions/:id/readback` | staff |
| Hoàn tất phiên (nhập mã hồ sơ) | `/sessions/:id/complete` | staff |
| Tra cứu audit | `/audit` | supervisor, auditor |
| Chi tiết audit một phiên | `/audit/:sessionId` | supervisor, auditor |
| Thống kê KPI | `/stats` | supervisor |
| Quản lý người dùng | `/admin/users` | admin |

---

## 12. Bảo mật, quyền riêng tư và tuân thủ

### 12.1. Cơ sở pháp lý và chính sách

Từ Báo cáo sáng kiến, các văn bản làm cơ sở:

- Nghị quyết 57-NQ/TW ngày 22/12/2024 — đột phá phát triển KHCN, đổi mới sáng tạo, chuyển đổi số quốc gia
- Quyết định 749/QĐ-TTg ngày 03/6/2020 — Chương trình Chuyển đổi số quốc gia
- Quyết định 06/QĐ-TTg ngày 06/01/2022 — Đề án 06
- Nghị quyết 76/NQ-CP ngày 15/7/2021 — Chương trình tổng thể CCHC 2021–2030
- Luật Giao dịch điện tử 2023
- Kế hoạch 165/KH-UBND ngày 21/4/2026 (TP Hà Nội), Kế hoạch 173/KH-UBND (phường Yên Sở)

Ngoài ra cần rà soát thêm (**việc của bộ phận pháp chế**): quy định hiện hành về bảo vệ dữ liệu cá nhân và an toàn thông tin mạng áp dụng tại thời điểm triển khai.

### 12.2. Xác thực và phân quyền

| Vai trò | Quyền |
|---|---|
| `staff` | Tạo/xử lý phiên của chính mình; không xem được phiên của người khác |
| `supervisor` | Xem mọi phiên trong đơn vị; xem thống kê; không sửa được dữ liệu phiên |
| `auditor` | Chỉ đọc, xem toàn bộ audit log, xuất báo cáo |
| `admin` | Quản lý người dùng, cấu hình hệ thống; **không** xem được nội dung phiên |

**Hiện thực:**
- JWT có claim `role` và `unit`; kiểm tra ở dependency của FastAPI.
- Nguyên tắc đặc quyền tối thiểu: `admin` cố tình không có quyền đọc dữ liệu người dân.
- Đăng nhập sai 5 lần → khóa tài khoản 15 phút.
- Ghi log mọi lần `permission_denied`.

### 12.3. Bảo vệ dữ liệu

| Yêu cầu (từ Báo cáo sáng kiến) | Hiện thực kỹ thuật |
|---|---|
| *"Chỉ thu thập, xử lý dữ liệu phục vụ trực tiếp việc giải quyết TTHC"* | Chỉ trích xuất các trường có trong catalog của thủ tục đã chọn; không thu thập gì thêm |
| *"Không lưu trữ bản ghi âm khi không còn cần thiết"* | Audio chỉ tồn tại trong Redis với TTL 120 giây; xóa tường minh ngay khi có transcript; ghi `audio_deleted_at` làm bằng chứng; **không bao giờ** ghi audio xuống đĩa |
| *"Không đưa dữ liệu cá nhân lên nền tảng AI không được cơ quan có thẩm quyền cho phép"* | Danh sách nhà cung cấp được duyệt khai báo trong `config.APPROVED_AI_PROVIDERS`; tầng HTTP client chặn mọi hostname ngoài danh sách; vi phạm → ném exception, ghi log nghiêm trọng |
| *"Quá trình hỗ trợ được ghi nhận đầy đủ để phục vụ thống kê, kiểm tra, truy xuất"* | Bảng `audit_log` append-only, đã thu hồi quyền UPDATE/DELETE ở tầng DB |
| Giảm thiểu dữ liệu | `PIIRedactor` che CCCD trước khi gửi LLM; không lưu CCCD đầy đủ trong `sessions` (dùng `citizen_ref`) |
| Mã hóa | TLS 1.2+ cho mọi kết nối; PostgreSQL bật mã hóa at-rest; cột nhạy cảm cân nhắc mã hóa ở tầng ứng dụng (**cần chốt** — Mục 20) |
| Bí mật cấu hình | API key qua biến môi trường, không bao giờ commit vào repo; `.env` nằm trong `.gitignore` |

### 12.4. Ranh giới dữ liệu gửi ra ngoài

```
Dữ liệu ĐƯỢC gửi tới dịch vụ AI bên ngoài:
  ✓ Đoạn audio (tới STT) — bắt buộc để nhận dạng giọng nói
  ✓ Transcript đã che CCCD (tới LLM)
  ✓ Field schema của thủ tục (tới LLM) — dữ liệu công khai, không nhạy cảm
  ✓ Văn bản đọc lại đã che CCCD (tới TTS)

Dữ liệu KHÔNG BAO GIỜ gửi ra ngoài:
  ✗ Số CCCD đầy đủ
  ✗ Thông tin định danh cán bộ
  ✗ Mã hồ sơ trên Cổng DVC
  ✗ Bất kỳ dữ liệu nào từ cơ sở dữ liệu dân cư (hệ thống không có quyền truy cập)
  ✗ Nội dung audit log
```

### 12.5. Thẩm định nhà cung cấp AI

Trước khi ký hợp đồng với bất kỳ nhà cung cấp STT/TTS/LLM nào, **bắt buộc** trả lời bằng văn bản:

1. Dữ liệu được xử lý và lưu trữ ở đâu (quốc gia, trung tâm dữ liệu)?
2. Có lưu lại audio/transcript sau khi xử lý không? Bao lâu?
3. Dữ liệu có được dùng để huấn luyện mô hình không? Có tắt được không?
4. Có ký được thỏa thuận xử lý dữ liệu (DPA) không?
5. Có chứng nhận an toàn thông tin nào (ISO 27001 hoặc tương đương)?
6. Cam kết SLA về khả dụng và độ trễ?
7. Độ chính xác thực đo với tiếng Việt, đặc biệt giọng vùng miền và người cao tuổi?

> Kế hoạch này nêu BlazeAI theo bản Draft, nhưng **chưa có căn cứ độc lập nào để xác nhận** năng lực, chính sách dữ liệu hay vị trí máy chủ của nhà cung cấp này. Bắt buộc phải thẩm định trước khi đưa dữ liệu người dân thật vào. Vì lý do đó, tầng STT/TTS được thiết kế dạng **adapter thay thế được** (Mục 16.3) — chọn sai nhà cung cấp không kéo theo việc phải viết lại hệ thống.

---

## 13. Xử lý lỗi và độ tin cậy

### 13.1. Nguyên tắc suy giảm mềm

| Thành phần hỏng | Còn dùng được gì | Nghiệp vụ có tiếp tục được không |
|---|---|---|
| LLM | STT, TTS, catalog, checklist hồ sơ, nhập tay | **Có** |
| STT | LLM (với transcript gõ tay), TTS, nhập tay | **Có** |
| TTS | Tất cả, đọc lại bằng văn bản trên màn hình | **Có** |
| Redis | Tất cả (chậm hơn, dùng PostgreSQL thay thế) | **Có** |
| PostgreSQL | Không | **Không** — trả 503 |
| Mạng ra ngoài | Catalog, checklist, nhập tay | **Có** |

Chỉ PostgreSQL là điểm hỏng chí mạng. Cần backup và có phương án khôi phục.

### 13.2. Circuit breaker

Áp dụng cho mọi lệnh gọi dịch vụ AI bên ngoài:

```
CLOSED ──(5 lỗi liên tiếp)──▶ OPEN ──(sau 60 giây)──▶ HALF_OPEN
   ▲                                                       │
   └───────────(1 lần gọi thành công)──────────────────────┘
```

Khi mạch mở, không gọi ra ngoài nữa — trả `AI_UNAVAILABLE` ngay, frontend chuyển sang chế độ nhập tay. Tránh để cán bộ chờ vô ích khi dịch vụ đang chết.

### 13.3. Idempotency

Các endpoint `confirm`, `complete`, `citizen-confirm` nhận header `Idempotency-Key`. Gọi lại với cùng key trả về kết quả cũ, không tạo bản ghi trùng. Cần thiết vì mạng ở điểm hỗ trợ có thể chập chờn và cán bộ hay bấm lại.

### 13.4. Giới hạn tần suất

| Đối tượng | Giới hạn |
|---|---|
| Số lần gọi extraction mỗi phiên | 5 (cấu hình được) |
| Số lần gọi extraction mỗi cán bộ mỗi giờ | 60 |
| Số phiên mở đồng thời mỗi cán bộ | 3 |
| Kích thước audio chunk | 64 KB |
| Thời lượng ghi âm một lượt | 120 giây |

---

## 14. Quan sát hệ thống và chỉ số

### 14.1. Log có cấu trúc

Mọi log là JSON một dòng, luôn kèm `request_id` và `session_id`:

```json
{
  "timestamp": "2026-09-15T09:12:33.123+07:00",
  "level": "info",
  "event": "extraction_succeeded",
  "request_id": "req_01J...",
  "session_id": "a3f8...",
  "staff_id": "u_042",
  "procedure_code": "dang_ky_khai_sinh",
  "fields_extracted": 5,
  "fields_missing": 2,
  "latency_ms": 1840,
  "model": "claude-sonnet-5"
}
```

**Tuyệt đối không log:** giá trị trường dữ liệu, transcript nguyên văn, số CCCD. Chỉ log số đếm và siêu dữ liệu. Nội dung chi tiết nằm ở `audit_log` trong database, nơi có kiểm soát truy cập.

### 14.2. Chỉ số theo dõi

| Chỉ số | Loại | Mục đích |
|---|---|---|
| `sessions_started_total{procedure}` | counter | KPI-2 |
| `sessions_completed_total{procedure}` | counter | Tỷ lệ hoàn thành |
| `session_duration_seconds` | histogram | KPI-1 |
| `extraction_latency_ms` | histogram | Trải nghiệm người dùng |
| `extraction_failures_total{reason}` | counter | Độ tin cậy AI |
| `transcripts_flagged_by_staff_total` | counter | Chất lượng STT theo đánh giá thủ công của cán bộ (UC5) |
| `fields_edited_ratio` | gauge | **Độ chính xác thực tế của AI** — tỷ lệ cán bộ phải sửa giá trị gợi ý |
| `readback_rounds` | histogram | KPI-3 — nhiều vòng đọc lại = chất lượng kém |
| `manual_mode_sessions_total` | counter | Tần suất phải nhập tay |
| `ai_provider_errors_total{provider}` | counter | Chất lượng nhà cung cấp |

> `fields_edited_ratio` là chỉ số quan trọng nhất để đánh giá AI có thực sự hữu ích không. Nếu cán bộ phải sửa hơn 30% số trường, việc dùng AI không tiết kiệm được thời gian và cần xem lại prompt hoặc nhà cung cấp STT.

### 14.3. Dashboard KPI

Màn hình `/stats` hiển thị:

- Số phiên mỗi ngày, so với mục tiêu 45–50 (KPI-2)
- Thời gian trung bình mỗi phiên, so với baseline nhập tay (KPI-1)
- Phân bố theo loại thủ tục (KPI-6)
- Top 10 trường hay bị thiếu / hay bị sửa (KPI-6 — "lỗi kê khai thường gặp")
- Tỷ lệ phiên dùng chế độ nhập tay
- Phân bố số vòng đọc lại (KPI-3)

---

## 15. Chiến lược kiểm thử

### 15.1. Kim tự tháp kiểm thử

| Mức | Phạm vi | Công cụ | Mục tiêu bao phủ |
|---|---|---|---|
| Unit | Validator, state machine, quy tắc merge, redactor, grounding check | pytest | **≥90%** cho `app/domain/` |
| Integration | Endpoint API + database, giả lập dịch vụ AI | pytest + respx + testcontainers | Mọi endpoint |
| Contract | Schema output LLM, hợp đồng API STT/TTS | pytest + bộ dữ liệu mẫu cố định | Mọi tích hợp bên ngoài |
| E2E | Trọn vẹn UC1–UC8 | Playwright | Mọi use case |
| Đánh giá AI | Chất lượng trích xuất trên bộ dữ liệu tiếng Việt | Bộ test riêng | Xem 15.3 |
| Thủ công | Kiểm thử chấp nhận với cán bộ thật | Kịch bản viết sẵn | Trước khi thí điểm |

### 15.2. Kiểm thử ưu tiên cao

Những phần **bắt buộc** phải có test trước khi chạy dữ liệu thật:

1. **State machine** — mọi chuyển đổi hợp lệ và bất hợp lệ.
2. **Quy tắc merge (UC2)** — đặc biệt trường hợp không được ghi đè giá trị cán bộ đã xác nhận.
3. **Grounding check** — LLM bịa giá trị phải bị bắt.
4. **Redactor** — CCCD phải bị che, xác minh bằng cách kiểm tra payload gửi đi.
5. **Chặn nhà cung cấp ngoài danh sách** — gọi hostname lạ phải bị chặn.
6. **Không có endpoint bulk confirm** — test khẳng định endpoint đó không tồn tại.
7. **Xóa audio buffer** — sau khi có transcript, Redis không còn key audio.
8. **Audit log bất biến** — thử UPDATE/DELETE phải thất bại.
9. **Luồng dự phòng UC6** — giả lập mọi dịch vụ AI chết, phiên vẫn hoàn tất được.
10. **Phân quyền** — `staff` không xem được phiên của người khác; `admin` không xem được nội dung phiên.

### 15.3. Bộ đánh giá chất lượng AI

Xây dựng bộ dữ liệu **50–100 transcript tiếng Việt** có gán nhãn chuẩn, phản ánh điều kiện thực tế:

| Nhóm | Số mẫu | Đặc điểm |
|---|---|---|
| Rõ ràng, đủ thông tin | 20 | Chuẩn UC1 |
| Thiếu thông tin | 20 | Chuẩn UC2 |
| Mơ hồ, nói vòng vo | 15 | Người cao tuổi hay nói kiểu này |
| Có tiếng ồn / nói ngắt quãng | 15 | Điều kiện quầy thật |
| Nhiều thủ tục trong một lượt | 10 | UC3 |
| Sửa thông tin giữa chừng | 10 | UC4 |
| **Bẫy ảo giác** | 10 | Transcript cố tình thiếu → AI phải trả MISSING, không được đoán |

**Chỉ số đánh giá:**
- Độ chính xác trích xuất từng trường (khớp chính xác và khớp mờ)
- **Tỷ lệ ảo giác** (điền giá trị khi transcript không có) — **mục tiêu 0%**, đây là chỉ số quan trọng nhất
- Tỷ lệ MISSING đúng (bắt được thiếu thông tin thật)
- Tỷ lệ báo thiếu sai (báo thiếu trong khi transcript có)

Chạy lại bộ này **mỗi khi đổi prompt hoặc đổi model**. Không chỉnh prompt mà không chạy lại đánh giá.

> **Lưu ý thu thập dữ liệu:** bộ đánh giá phải dùng dữ liệu giả lập hoặc dữ liệu đã ẩn danh có sự đồng ý. **Không** lấy transcript của người dân thật đưa vào bộ test.

---

## 16. Cấu trúc mã nguồn và môi trường

### 16.1. Cây thư mục

```
Agent/
├── pyproject.toml              # uv, khai báo phụ thuộc
├── uv.lock
├── .env.example
├── .gitignore
├── README.md
├── Plan.MD
├── alembic.ini
│
├── app/
│   ├── main.py                 # Khởi tạo FastAPI, đăng ký middleware
│   ├── config.py               # Cấu hình qua pydantic-settings
│   ├── deps.py                 # Dependency dùng chung (db, auth, ...)
│   │
│   ├── api/
│   │   ├── auth.py
│   │   ├── procedures.py
│   │   ├── sessions.py
│   │   ├── voice.py            # WebSocket
│   │   ├── extraction.py
│   │   ├── fields.py
│   │   ├── readback.py
│   │   ├── audit.py
│   │   └── stats.py
│   │
│   ├── domain/                 # Logic thuần — KHÔNG phụ thuộc I/O
│   │   ├── state_machine.py
│   │   ├── merge.py            # Quy tắc gộp đa lượt (UC2)
│   │   ├── validators.py
│   │   ├── extraction_schema.py
│   │   └── warnings.py         # Sinh cảnh báo
│   │
│   ├── services/
│   │   ├── catalog.py
│   │   ├── stt/
│   │   │   ├── base.py         # Giao diện trừu tượng STTProvider
│   │   │   ├── blaze.py
│   │   │   └── mock.py         # Dùng cho test và phát triển
│   │   ├── tts/
│   │   │   ├── base.py
│   │   │   ├── blaze.py
│   │   │   └── mock.py
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── claude.py
│   │   │   └── mock.py
│   │   ├── extractor.py        # Điều phối: redact → gọi LLM → verify
│   │   ├── grounding.py
│   │   ├── redactor.py
│   │   ├── audit.py
│   │   └── circuit_breaker.py
│   │
│   ├── models/                 # SQLAlchemy
│   │   ├── base.py
│   │   ├── staff.py
│   │   ├── session.py
│   │   ├── voice.py
│   │   ├── extraction.py
│   │   └── audit.py
│   │
│   ├── schemas/                # Pydantic cho API
│   │   ├── session.py
│   │   ├── field.py
│   │   ├── extraction.py
│   │   └── common.py
│   │
│   ├── db/
│   │   ├── database.py
│   │   └── redis_client.py
│   │
│   └── static_data/
│       └── procedures/
│           ├── _schema.json    # JSON Schema kiểm tra file catalog
│           ├── dang_ky_khai_sinh.json
│           ├── dang_ky_ket_hon.json
│           ├── chung_thuc_dien_tu.json
│           ├── xac_nhan_cu_tru.json
│           └── dang_ky_khai_tu.json
│
├── migrations/                 # Alembic
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   └── ai_eval/
│       ├── dataset/            # Transcript mẫu đã gán nhãn
│       └── test_extraction_quality.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── api/
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       │   ├── useVoiceStream.ts
│       │   └── useSession.ts
│       └── types/
│
├── scripts/
│   ├── seed_users.py
│   ├── validate_catalog.py     # Kiểm tra file catalog trong CI
│   └── retention_cleanup.py    # Job dọn dữ liệu hết hạn
│
└── docs/
    ├── api.md
    ├── deployment.md
    ├── security_review.md      # Nộp cho bộ phận an toàn thông tin
    └── staff_manual_vi.md      # Tài liệu hướng dẫn cán bộ
```

### 16.2. Nguyên tắc phân tầng

```
api/  ──▶  services/  ──▶  domain/
  │            │
  └────────────┴──────────▶  models/, db/
```

- `domain/` là hàm thuần, không I/O, không phụ thuộc framework — dễ test, dễ suy luận đúng sai.
- `services/` điều phối I/O và gọi `domain/`.
- `api/` chỉ lo HTTP: parse request, gọi service, format response.
- **Cấm** gọi tắt từ `api/` xuống thẳng `models/` bỏ qua `services/`.

### 16.3. Trừu tượng hóa nhà cung cấp

```python
# app/services/stt/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass(frozen=True)
class TranscriptChunk:
    text: str
    is_final: bool
    confidence: float
    provider: str
    latency_ms: int

class STTProvider(ABC):
    @abstractmethod
    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes], language: str = "vi"
    ) -> AsyncIterator[TranscriptChunk]: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

Nhà cung cấp cụ thể chọn qua biến môi trường `STT_PROVIDER=blaze|mock`. Nhờ vậy, đổi nhà cung cấp chỉ cần viết thêm một adapter — quan trọng vì BlazeAI chưa được thẩm định.

### 16.4. Cấu hình

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Ứng dụng
    app_env: str = "development"          # development | staging | production
    secret_key: str
    jwt_expire_hours: int = 8

    # Cơ sở dữ liệu
    database_url: str
    redis_url: str

    # Nhà cung cấp AI
    stt_provider: str = "mock"
    tts_provider: str = "mock"
    llm_provider: str = "claude"

    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-5"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    blaze_api_key: str | None = None
    blaze_base_url: str | None = None

    # Danh sách nhà cung cấp được duyệt (NT-10)
    approved_ai_hosts: list[str] = ["api.anthropic.com"]

    # Ngưỡng nghiệp vụ
    stt_min_confidence: float = 0.65
    max_extractions_per_session: int = 5
    max_recording_seconds: int = 120
    audio_buffer_ttl_seconds: int = 120

    # Thời hạn lưu trữ (cần chốt với đơn vị chủ trì)
    transcript_retention_days: int = 90
    audit_retention_days: int = 730

    class Config:
        env_file = ".env"
```

### 16.5. Thiết lập môi trường phát triển

Python 3.12 và môi trường ảo **đã được tạo sẵn** trong thư mục dự án.

```bash
# Môi trường ảo đã có tại .venv (Python 3.12.13)
# Kích hoạt:
.venv\Scripts\activate          # Windows CMD
.venv\Scripts\Activate.ps1      # PowerShell

# Cài phụ thuộc (sau khi có pyproject.toml)
uv sync

# Chạy migration
uv run alembic upgrade head

# Chạy server phát triển
uv run uvicorn app.main:app --reload

# Chạy test
uv run pytest
uv run pytest tests/ai_eval -v      # Đánh giá chất lượng AI

# Kiểm tra chất lượng mã
uv run ruff check .
uv run mypy app/
```

---

## 17. Triển khai và vận hành

### 17.1. Môi trường

| Môi trường | Mục đích | Dữ liệu |
|---|---|---|
| `development` | Máy lập trình viên | Dữ liệu giả, dịch vụ AI dạng mock |
| `staging` | Kiểm thử tích hợp, nghiệm thu với cán bộ | Dữ liệu giả lập, dịch vụ AI thật |
| `production` | Thí điểm tại điểm hỗ trợ | Dữ liệu thật |

**Quy tắc tuyệt đối:** không bao giờ sao chép dữ liệu production sang staging hay development.

### 17.2. Hạ tầng

- **Đề xuất:** triển khai on-premise hoặc trên hạ tầng đám mây trong nước, đặt tại phường hoặc trung tâm dữ liệu của thành phố.
- Backend chạy trong Docker; `docker-compose` cho staging, cấu hình phù hợp cho production tùy hạ tầng thực tế.
- PostgreSQL và Redis triển khai riêng, có backup.
- Reverse proxy (nginx) kết thúc TLS.

### 17.3. Backup và khôi phục

| Đối tượng | Tần suất | Lưu giữ | Kiểm tra khôi phục |
|---|---|---|---|
| PostgreSQL đầy đủ | Hằng ngày | 30 ngày | Hằng tháng |
| PostgreSQL WAL | Liên tục | 7 ngày | — |
| Cấu hình + catalog | Theo mỗi thay đổi | Vô hạn (trong git) | — |

Redis **không cần** backup — chỉ chứa dữ liệu tạm thời.

### 17.4. Danh sách kiểm tra trước khi vận hành

- [ ] Bộ phận an toàn thông tin đã rà soát và duyệt
- [ ] Bộ phận pháp chế đã rà soát về xử lý dữ liệu cá nhân
- [ ] Đã ký DPA với các nhà cung cấp AI
- [ ] Catalog thủ tục đã được phòng chuyên môn duyệt bằng văn bản
- [ ] Đã đo baseline thời gian nhập tay (phục vụ KPI-1)
- [ ] Đã tập huấn cán bộ, có tài liệu hướng dẫn tiếng Việt
- [ ] Đã kiểm thử khôi phục backup thành công
- [ ] Đã diễn tập luồng dự phòng khi AI chết
- [ ] Nội dung thông báo cho người dân về việc sử dụng AI đã được duyệt
- [ ] Đã cấu hình cảnh báo khi tỷ lệ lỗi vượt ngưỡng
- [ ] Đã kiểm thử tải: 3 phiên đồng thời với đủ số cán bộ tại quầy

---

## 18. Kế hoạch thực hiện theo giai đoạn

### 18.1. Lưu ý quan trọng về mốc thời gian

Báo cáo sáng kiến ghi thời gian áp dụng **01/7/2026 – 15/12/2026**. Hôm nay là **30/8/2026** — đã qua gần 2 tháng của khung thời gian này. Bản Draft đề xuất "9 tuần xây dựng trước khi thí điểm", tức nếu bắt đầu code hôm nay thì phần mềm chỉ sẵn sàng vào khoảng đầu tháng 11/2026, còn khoảng 6 tuần thí điểm.

**Hai phương án, cần đơn vị chủ trì quyết định:**

| Phương án | Nội dung | Ưu / Nhược |
|---|---|---|
| **A. Thu hẹp phạm vi** | Chỉ làm **1 thủ tục** (đăng ký khai sinh), bỏ UC3, dashboard tối giản → sẵn sàng trong **5 tuần**, thí điểm từ giữa tháng 10 | Kịp khung thời gian; đổi lại phạm vi hẹp |
| **B. Điều chỉnh thời gian thí điểm** | Giữ nguyên phạm vi đầy đủ, xin gia hạn thí điểm sang quý I/2027 | Sản phẩm hoàn chỉnh; cần văn bản xin điều chỉnh kế hoạch |

Kế hoạch dưới đây trình bày theo **Phương án A** (thu hẹp), có ghi rõ hạng mục nào hoãn sang giai đoạn sau.

### 18.2. Giai đoạn 0 — Chuẩn bị (tuần 0, làm song song)

**Không cần code**, nhưng chặn các giai đoạn sau nếu chưa xong:

| Việc | Người chịu trách nhiệm |
|---|---|
| Chốt danh mục thủ tục cho V1 | Phòng Văn hóa – Xã hội |
| Soạn và duyệt nội dung catalog (trường dữ liệu, thành phần hồ sơ) | Phòng chuyên môn |
| **Đo baseline thời gian nhập tay** (tối thiểu 30 lượt) | Cán bộ tại quầy |
| Gửi bộ câu hỏi thẩm định cho nhà cung cấp AI | Đơn vị chủ trì |
| Soạn nội dung thông báo/xin ý kiến người dân | Pháp chế |
| Chuẩn bị hạ tầng (máy chủ, mạng, micro, loa) | Bộ phận kỹ thuật |

> Baseline ở Giai đoạn 0 là **bắt buộc**. Không có nó thì không thể chứng minh KPI-1 ("rút ngắn 60% thời gian") bằng số liệu.

### 18.3. Các giai đoạn phát triển

| GĐ | Nội dung | Thời gian | Sản phẩm bàn giao |
|---|---|---|---|
| **1** | Nền tảng: FastAPI skeleton, PostgreSQL + migration, xác thực & phân quyền, audit logger, catalog service, state machine + unit test | **1 tuần** | API chạy được, tạo/tra cứu phiên, ghi log đầy đủ |
| **2** | Tầng AI: adapter LLM, prompt trích xuất, schema output, grounding check, validator, redactor, xử lý lỗi + circuit breaker. **Bộ đánh giá AI với transcript giả lập** | **1.5 tuần** | Trích xuất chạy được với transcript gõ tay; báo cáo tỷ lệ ảo giác |
| **3** | Tầng giọng nói: adapter STT/TTS, WebSocket streaming, quản lý audio buffer + xóa tự động, xử lý confidence thấp | **1 tuần** | Ghi âm → transcript hoạt động; TTS đọc lại được |
| **4** | Frontend: đăng nhập, màn hình làm việc, xác nhận từng trường, checklist hồ sơ, đọc lại, hoàn tất phiên, chế độ nhập tay | **1.5 tuần** | Giao diện hoàn chỉnh cho UC1, UC2, UC4, UC5, UC6, UC8 |
| **5** | Kiểm tra & thống kê: màn hình audit, dashboard KPI, job dọn dữ liệu hết hạn, xuất báo cáo | **0.5 tuần** | Màn hình tra cứu và thống kê |
| **6** | Hoàn thiện: E2E test, kiểm tra bảo mật, kiểm thử tải, tài liệu hướng dẫn cán bộ, tập huấn | **1 tuần** | Sẵn sàng nghiệm thu |
| | **Tổng** | **6.5 tuần** | |

**Hoãn sang sau thí điểm:** UC3 (nhiều thủ tục cùng lúc), các thủ tục thứ 2–5 trong catalog, xuất báo cáo PDF, quản lý người dùng qua giao diện (giai đoạn đầu dùng script).

### 18.4. Giai đoạn thí điểm

| Tuần | Nội dung |
|---|---|
| Tuần 1 | Chạy song song: cán bộ dùng công cụ **và** nhập tay như cũ, đối chiếu kết quả. Không dùng công cụ để ra quyết định |
| Tuần 2–3 | Dùng thật với thủ tục ưu tiên, theo dõi sát `fields_edited_ratio` |
| Tuần 4+ | Mở rộng nếu chỉ số đạt; thu thập phiếu khảo sát (100 phiếu theo kế hoạch) |
| Cuối kỳ | Tổng hợp số liệu, đối chiếu KPI, viết báo cáo kết quả |

**Tiêu chí dừng thí điểm** (bất kỳ điều nào xảy ra thì tạm dừng để rà soát):
- Phát hiện **1 trường hợp** AI bịa dữ liệu lọt qua được cả bốn lớp bảo vệ và tới hồ sơ thật
- `fields_edited_ratio` > 40% liên tục 3 ngày (AI không giúp được gì)
- Phát hiện sự cố lộ dữ liệu cá nhân
- Cán bộ báo công cụ làm chậm hơn nhập tay

---

## 19. Rủi ro và phương án giảm thiểu

| # | Rủi ro | Khả năng | Mức độ | Giảm thiểu |
|---|---|---|---|---|
| R1 | **AI bịa dữ liệu vào hồ sơ có giá trị pháp lý** | Trung bình | **Nghiêm trọng** | 4 lớp bảo vệ (Mục 10.1); bắt buộc trích dẫn căn cứ; cán bộ xác nhận từng trường; bộ test bẫy ảo giác |
| R2 | **BlazeAI không đạt yêu cầu về dữ liệu hoặc chất lượng** | Trung bình | Cao | Thiết kế adapter thay thế được; thẩm định trước khi ký; có nhà cung cấp dự phòng |
| R3 | **STT nhận diện kém với giọng người cao tuổi** — đúng nhóm đối tượng ưu tiên | **Cao** | Cao | Ngưỡng confidence; luôn có nhập tay; **test thực tế với người cao tuổi ở phường trước khi triển khai** |
| R4 | Lộ dữ liệu cá nhân qua dịch vụ AI bên ngoài | Thấp | **Nghiêm trọng** | Che CCCD; danh sách nhà cung cấp được duyệt chặn ở tầng code; DPA; rà soát an toàn thông tin |
| R5 | Cán bộ tin AI quá mức, xác nhận qua loa | **Cao** | Cao | Không có nút xác nhận tất cả; hiển thị căn cứ trích dẫn; banner nhắc nhở; tập huấn; theo dõi thời gian giữa hiển thị và xác nhận |
| R6 | Không kịp khung thời gian thí điểm | **Cao** | Trung bình | Phương án A thu hẹp phạm vi (Mục 18.1) |
| R7 | Catalog sai so với quy định hiện hành | Trung bình | Cao | Bắt buộc có người duyệt; ghi rõ căn cứ pháp lý; rà soát định kỳ |
| R8 | Người dân không đồng ý dùng AI | Trung bình | Thấp | Chế độ `manual_only` (UC8); AI là tùy chọn, không bắt buộc |
| R9 | Mạng chập chờn tại điểm hỗ trợ | Trung bình | Trung bình | Circuit breaker; suy giảm mềm; idempotency |
| R10 | Chi phí gọi API vượt dự toán | Thấp | Trung bình | Giới hạn số lần gọi mỗi phiên; theo dõi token; cảnh báo ngân sách |
| R11 | Không chứng minh được KPI vì thiếu baseline | **Cao** | Trung bình | Giai đoạn 0 bắt buộc đo baseline trước khi bật AI |
| R12 | Người dân hiểu nhầm AI là người quyết định hồ sơ | Trung bình | Trung bình | Cán bộ giải thích rõ khi xin ý kiến; nội dung thông báo do pháp chế duyệt |

---

## 20. Vấn đề cần chốt trước khi code

Sắp xếp theo mức độ chặn công việc.

### 20.1. Chặn Giai đoạn 1

| # | Câu hỏi | Người quyết định |
|---|---|---|
| Q1 | Danh mục thủ tục cho V1 gồm những thủ tục nào? Ưu tiên thủ tục nào làm trước? | Phòng Văn hóa – Xã hội |
| Q2 | Với mỗi thủ tục: chính xác các trường dữ liệu và thành phần hồ sơ là gì? Căn cứ văn bản nào? | Phòng chuyên môn |
| Q3 | Chọn Phương án A (thu hẹp) hay Phương án B (gia hạn thí điểm)? | Đơn vị chủ trì |
| Q4 | Bao nhiêu cán bộ sẽ dùng? Bao nhiêu quầy đồng thời? | Tổ CĐS cộng đồng |

### 20.2. Chặn Giai đoạn 2 (tầng AI)

| # | Câu hỏi | Người quyết định |
|---|---|---|
| Q5 | Có được phép gửi họ tên và địa chỉ người dân tới Claude API không? Nếu không, phải che thêm những gì? | Pháp chế + An toàn thông tin |
| Q6 | Vị trí xử lý dữ liệu của Claude API có được chấp thuận không? | An toàn thông tin |
| Q7 | Cơ quan có thẩm quyền đã cho phép dùng nền tảng AI nào? (Báo cáo yêu cầu "không đưa dữ liệu cá nhân lên nền tảng AI không được cơ quan có thẩm quyền cho phép") | Đơn vị chủ trì |

### 20.3. Chặn Giai đoạn 3 (giọng nói)

| # | Câu hỏi | Người quyết định |
|---|---|---|
| Q8 | BlazeAI: tài liệu API, giá, SLA, vị trí máy chủ, chính sách lưu trữ dữ liệu? | Đơn vị chủ trì |
| Q9 | Nếu BlazeAI không đạt, dùng nhà cung cấp STT/TTS tiếng Việt nào thay thế? | Kỹ thuật + Pháp chế |
| Q10 | Đã test độ chính xác STT với giọng người cao tuổi tại phường chưa? | Tổ CĐS cộng đồng |

### 20.4. Chặn vận hành

| # | Câu hỏi | Người quyết định |
|---|---|---|
| Q11 | Thời hạn lưu transcript và dữ liệu trường là bao lâu? | Pháp chế |
| Q12 | Triển khai trên hạ tầng nào? On-premise tại phường hay đám mây? | Bộ phận kỹ thuật |
| Q13 | Ai chịu trách nhiệm vận hành, backup, xử lý sự cố sau khi bàn giao? | Đơn vị chủ trì |
| Q14 | Nội dung thông báo/xin ý kiến người dân về việc dùng AI đã có chưa? | Pháp chế |
| Q15 | Có cần mã hóa ở tầng ứng dụng cho các cột nhạy cảm không, hay mã hóa at-rest của PostgreSQL là đủ? | An toàn thông tin |

---

## 21. Phụ lục

### 21.1. Bảng ánh xạ: yêu cầu trong Báo cáo sáng kiến → thiết kế kỹ thuật

| Nội dung trong Báo cáo sáng kiến | Thể hiện trong kế hoạch này |
|---|---|
| "AI hỗ trợ, không thay thế công chức" | NT-1, NT-3; không có endpoint bulk confirm; GD-2 |
| "Mọi thông tin AI gợi ý phải được cán bộ kiểm tra, đối chiếu" | Bảng `field_states` tách `suggested_value` / `confirmed_value`; GD-1, GD-5 |
| "Chỉ được sử dụng sau khi người dân xác nhận" | State `CITIZEN_CONFIRMED` bắt buộc trước `COMPLETED`; bảng `citizen_confirmations` |
| Bước 1: người dân trình bày bằng lời nói | WebSocket `/sessions/{id}/voice`, UC1 |
| Bước 2: cán bộ đăng nhập hộ, chọn nhóm thủ tục | Thao tác thủ công; `POST /sessions/{id}/procedure` chỉ ghi nhận |
| Bước 3: AI trích xuất họ tên, ngày sinh, địa chỉ, SĐT, nội dung yêu cầu | `POST /sessions/{id}/extract`; catalog định nghĩa các trường |
| Bước 4: AI gợi ý biểu mẫu, cảnh báo thiếu sót | `required_documents` + `warnings` trong response |
| Bước 5: cán bộ kiểm tra, chuẩn hóa, nhập vào Cổng DVC | Xác nhận từng trường; nút "Chép"; không tích hợp Cổng DVC |
| Bước 6: người dân đọc/nghe lại, xác nhận | `POST /sessions/{id}/readback` + `citizen-confirm`; UC4 |
| Bước 7: thông báo mã hồ sơ, hướng dẫn tra cứu | `POST /sessions/{id}/complete` với `dossier_code` |
| "Không lưu trữ bản ghi âm khi không còn cần thiết" | Redis TTL 120s; `audio_deleted_at`; không ghi audio xuống đĩa |
| "Không đưa dữ liệu lên nền tảng AI không được phép" | `approved_ai_hosts` chặn ở tầng code |
| "Ghi nhận đầy đủ để thống kê, kiểm tra, truy xuất" | `audit_log` append-only; UC7; dashboard `/stats` |
| Hỗ trợ người cao tuổi, người yếu thế | UC5 (xử lý giọng không rõ); GD-9 (cỡ chữ lớn); R3 |
| "Giảm hồ sơ phải chỉnh sửa" | Validator + cảnh báo thiếu sót; theo dõi `readback_rounds` |
| Tạo bộ dữ liệu thống kê nhu cầu, lỗi thường gặp | `/stats/procedures`, `/stats/warnings` |

### 21.2. Thuật ngữ

| Thuật ngữ | Giải thích |
|---|---|
| **STT** | Speech-to-Text — chuyển giọng nói thành văn bản |
| **TTS** | Text-to-Speech — chuyển văn bản thành giọng nói |
| **LLM** | Large Language Model — mô hình ngôn ngữ lớn |
| **Cascaded** | Kiến trúc nối tiếp: STT → LLM → TTS, thay vì mô hình hợp nhất |
| **Grounding** | Kiểm chứng mọi giá trị AI đưa ra đều truy vết được về dữ liệu nguồn |
| **Ảo giác (hallucination)** | Mô hình tự bịa ra thông tin không có trong dữ liệu đầu vào |
| **Circuit breaker** | Cơ chế ngắt mạch, ngừng gọi dịch vụ đang lỗi để tránh chờ vô ích |
| **Idempotency** | Gọi lại nhiều lần cho cùng kết quả, không tạo bản ghi trùng |
| **Append-only** | Chỉ ghi thêm, không sửa không xóa — dùng cho audit log |
| **PII** | Personally Identifiable Information — thông tin định danh cá nhân |
| **DPA** | Data Processing Agreement — thỏa thuận xử lý dữ liệu với nhà cung cấp |

### 21.3. Định hướng giai đoạn tiếp theo

Các hạng mục **ngoài phạm vi V1**, cần điều kiện bổ sung:

**A. Tự động điền form trên Cổng DVC / VNeID**

Báo cáo sáng kiến có nêu định hướng hệ thống tự động điền các trường trên biểu mẫu điện tử. Về kỹ thuật, có thể làm bằng cách đọc cấu trúc trang và điền sau khi cán bộ xác nhận.

**Điều kiện tiên quyết:**
- Văn bản chấp thuận của đơn vị chủ quản Cổng DVC quốc gia / VNeID
- Đánh giá tác động an toàn thông tin
- Cơ chế kiểm soát: cán bộ vẫn phải xem lại và bấm nộp thủ công
- Không dùng kỹ thuật tự động hóa giao diện không được phép

Khuyến nghị: nếu theo đuổi hướng này, nên đề nghị đơn vị chủ quản cung cấp **API chính thức** thay vì tự động hóa trên giao diện — cách sau dễ hỏng khi Cổng DVC thay đổi và có thể vi phạm điều khoản sử dụng.

**B. Tra cứu cơ sở dữ liệu dân cư**

Điền sẵn thông tin từ CSDL dân cư sẽ giảm đáng kể việc phải nói và nhập lại. Cần quyền truy cập chính thức theo Đề án 06 và thẩm quyền phù hợp — nằm ngoài phạm vi một công cụ hỗ trợ cấp phường ở giai đoạn thí điểm.

**C. Nhân rộng ra các phường khác**

Theo Nội dung 6 của Báo cáo sáng kiến. Yêu cầu kỹ thuật khi nhân rộng:
- Catalog tách theo đơn vị (mỗi phường có thể có khác biệt)
- Hỗ trợ nhiều đơn vị trong một hệ thống (multi-tenant)
- Thống kê tổng hợp cấp thành phố
- Tài liệu vận hành chuẩn hóa cho đơn vị mới

**D. Mở rộng khả năng**
- Hỗ trợ tiếng dân tộc thiểu số
- Ứng dụng cho người dân tự dùng tại nhà (cần thiết kế lại toàn bộ mô hình kiểm soát — không còn cán bộ ở giữa)
- Kết nối hệ thống một cửa để theo dõi trạng thái hồ sơ

---

*Tài liệu này phục vụ mục đích lập kế hoạch kỹ thuật nội bộ. Cần được bộ phận pháp chế và an toàn thông tin rà soát, phê duyệt trước khi triển khai chính thức với dữ liệu người dân thật.*

**Phiên bản 1.0 — 30/8/2026**
