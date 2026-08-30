#!/usr/bin/env bash
# Mục Q của Checklist — khởi động backend + frontend cùng lúc cho phát triển
# local (không qua Docker — dùng docker-compose.yml khi cần môi trường đóng
# gói đầy đủ). Giả định PostgreSQL/Redis đã chạy sẵn (`docker compose up -d
# postgres redis`) và `.env`/`frontend/.env.local` đã có, `uv sync`/`npm
# install` đã chạy trước đó.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

cleanup() {
    echo ""
    echo "Đang dừng backend và frontend..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Áp dụng migration (alembic upgrade head)..."
uv run alembic upgrade head

echo "==> Khởi động backend (uvicorn --reload) tại :8000..."
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "==> Khởi động frontend (vite dev) tại :5173..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000  (docs: http://localhost:8000/docs)"
echo "Frontend: http://localhost:5173"
echo "Ctrl+C để dừng cả hai."

wait "$BACKEND_PID" "$FRONTEND_PID"
