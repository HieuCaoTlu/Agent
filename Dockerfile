# Dockerfile cho voice-ai-mvp — dùng uv để cài dependency đúng theo uv.lock,
# chỉ cài nhóm production (không có playwright, vốn chỉ cần lúc dev để khảo
# sát dữ liệu thủ tục, không cần lúc chạy server thật).
FROM python:3.12-slim AS base

# Cài uv bằng cách copy binary tĩnh từ image chính chủ của Astral — nhanh và
# không cần internet ngoài lúc build image.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Cài dependency trước, tách riêng khỏi COPY code để tận dụng cache layer —
# chỉ rebuild lại bước cài đặt khi pyproject.toml/uv.lock đổi.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy toàn bộ source code cần thiết để chạy server (không copy scripts/,
# extension/ — không cần lúc runtime).
COPY app ./app
COPY static ./static
COPY data ./data
# app/main.py import build_index (module ở root, dùng để tái tạo data/index.json
# từ PDF) — phải có mặt dù không được gọi lúc khởi động bình thường.
COPY build_index.py ./

# data/logs không được commit (xem .gitignore) nhưng app cần thư mục này tồn
# tại để ghi log hội thoại lúc chạy.
RUN mkdir -p data/logs

EXPOSE 8000

ENV PATH="/app/.venv/bin:${PATH}"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
