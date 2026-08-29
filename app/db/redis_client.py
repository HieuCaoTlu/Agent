"""Kết nối Redis: connection pool, dependency FastAPI.

Dùng để lưu buffer audio tạm thời (TTL ngắn, xem NT-6 và Mục 8.4 của Plan) và
audio kết quả TTS. Khi Redis lỗi, tầng service phải suy giảm mềm sang lưu
trạng thái phiên trong PostgreSQL (xem Checklist L1) — client này chỉ chịu
trách nhiệm kết nối, không tự xử lý fallback.
"""

from collections.abc import AsyncIterator

import redis.asyncio as redis

from app.config import get_settings

_pool: redis.ConnectionPool | None = None


def get_pool() -> redis.ConnectionPool:
    """Trả về connection pool Redis dùng chung, tạo lười lần gọi đầu tiên."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=False)
    return _pool


async def get_redis() -> AsyncIterator[redis.Redis]:
    """FastAPI dependency: trả về client Redis dùng chung pool."""
    client = redis.Redis(connection_pool=get_pool())
    try:
        yield client
    finally:
        await client.aclose()


async def dispose_pool() -> None:
    """Đóng connection pool — gọi trong lifespan handler lúc tắt ứng dụng."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
