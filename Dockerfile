# Dockerfile backend — Mục Q của Checklist.
#
# Dùng `uv` (đã quản lý dependencies qua pyproject.toml/uv.lock trong suốt dự
# án) thay vì pip trực tiếp, để khớp chính xác phiên bản đã khóa trong
# uv.lock — tránh lệch phiên bản giữa máy dev và container.
FROM python:3.12-slim AS base

# libpq cần cho asyncpg build/runtime trên slim image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy trước file khai báo dependency để tận dụng cache layer Docker — chỉ
# cài lại package khi pyproject.toml/uv.lock đổi, không phải mỗi lần đổi code.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini README.md ./

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Chạy migration rồi khởi động server — đơn giản, phù hợp MVP một instance.
# Môi trường nhiều instance thật sự cần tách bước migration ra khỏi entrypoint
# (init container/job riêng) để tránh chạy đua migration giữa các instance.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
