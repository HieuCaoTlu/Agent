# Trợ lý giọng nói AI hỗ trợ kê khai, nộp hồ sơ thủ tục hành chính trực tuyến

Công cụ nội bộ dùng tại quầy hỗ trợ dịch vụ công (phường Yên Sở): người dân trình bày
nhu cầu bằng giọng nói, hệ thống chuyển giọng nói → văn bản, dùng LLM trích xuất các
trường dữ liệu và cảnh báo thiếu sót, hiển thị dưới dạng **gợi ý** cho cán bộ. Cán bộ
đối chiếu giấy tờ gốc, tự tay xác nhận và nhập vào Cổng Dịch vụ công/VNeID.

Tài liệu tham chiếu: [Plan.MD](Plan.MD) · [Checklist.MD](Checklist.MD)

## Yêu cầu

- Python 3.12, [uv](https://docs.astral.sh/uv/)
- Node.js 20+, npm
- Docker + Docker Compose (khuyến nghị cho PostgreSQL/Redis, hoặc toàn bộ ứng dụng)

## Cách 1 — Chạy toàn bộ bằng Docker Compose

```bash
cp .env.example .env   # điền giá trị thật (Anthropic/Blaze API key...), KHÔNG commit .env
docker compose up --build
```

- Backend: http://localhost:8000 (tài liệu API tự sinh: http://localhost:8000/docs)
- Frontend: http://localhost:5173
- PostgreSQL: `localhost:5432` (`app_user`/`app_password`/`tthc_ai`)
- Redis: `localhost:6379`

Migration (`alembic upgrade head`) chạy tự động khi container `backend` khởi động
(xem [Dockerfile](Dockerfile)). Không cần bước "seed catalog" riêng — danh mục thủ tục
là các file JSON tĩnh trong [app/static_data/procedures/](app/static_data/procedures/),
được `CatalogService` đọc trực tiếp từ đĩa, không nạp vào DB.

## Cách 2 — Chạy trực tiếp (không Docker), phù hợp khi phát triển

```bash
# 1. Cài đặt
uv sync
cd frontend && npm install && cd ..
cp .env.example .env            # điền giá trị thật
cp frontend/.env.example frontend/.env.local   # thường để trống là đủ (dùng proxy dev server)

# 2. Chỉ chạy PostgreSQL + Redis bằng Docker (backend/frontend chạy trực tiếp trên máy)
docker compose up -d postgres redis

# 3. Áp dụng migration
uv run alembic upgrade head

# 4. Khởi động backend + frontend cùng lúc
./scripts/run_dev.sh
```

`scripts/run_dev.sh` khởi động `uvicorn --reload` (backend, :8000) và `npm run dev`
(frontend, :5173) song song, dừng cả hai bằng Ctrl+C. Muốn chạy riêng từng phần:

```bash
uv run uvicorn app.main:app --reload          # backend
cd frontend && npm run dev                     # frontend (cửa sổ terminal khác)
```

## Biến môi trường

Xem [.env.example](.env.example) (backend) và [frontend/.env.example](frontend/.env.example)
(frontend) — mỗi biến có chú thích tại chỗ. Các nhóm chính:

| Nhóm | Ghi chú |
|---|---|
| `DATABASE_URL`, `REDIS_URL` | Mặc định trỏ `localhost` — đúng khi chạy Cách 2; docker-compose tự ghi đè thành `postgres`/`redis` (tên service) cho Cách 1 |
| `STT_PROVIDER`, `TTS_PROVIDER`, `LLM_PROVIDER` | `mock` để phát triển/test không cần API key thật; `blaze`/`claude` cho tích hợp thật |
| `ANTHROPIC_API_KEY`, `BLAZE_API_TOKEN` | Bắt buộc khi dùng provider thật — xem `APPROVED_AI_HOSTS` (NT-10, chặn gọi ra ngoài danh sách đã duyệt) |
| Ngưỡng nghiệp vụ (`MAX_EXTRACTIONS_PER_SESSION`, `MAX_RECORDING_SECONDS`...) | Xem L2 của Checklist.MD |

## Kiểm thử

```bash
uv run ruff check .     # lint backend
uv run pytest           # test backend (unit + integration API)

cd frontend
npx tsc --noEmit         # type-check
npm run lint              # oxlint
npm run build             # build production thử
```

Test thủ công (luồng đầu-cuối qua giao diện thật, và mọi provider AI lỗi vẫn hoàn tất
được bằng nhập tay) — xem [tests/manual/README.md](tests/manual/README.md).

## Migration

```bash
uv run alembic upgrade head              # áp dụng migration mới nhất
uv run alembic revision --autogenerate -m "mô tả thay đổi"   # tạo migration mới
```

## Cấu trúc thư mục

```
app/            Backend (FastAPI) — domain, services, routers, providers AI
frontend/       Frontend (React + Vite + TypeScript)
migrations/     Alembic migrations
tests/          Test tự động (backend) + tests/manual (kịch bản thủ công)
scripts/        Script tiện ích (run_dev.sh)
```
