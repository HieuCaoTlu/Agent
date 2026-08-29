"""Kết nối PostgreSQL: async engine, sessionmaker, dependency FastAPI."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Trả về async engine dùng chung, tạo lười (lazy) lần gọi đầu tiên."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            echo=settings.app_env == "development",
        )
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Trả về sessionmaker dùng chung, tạo lười lần gọi đầu tiên."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _sessionmaker


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: mở một AsyncSession cho vòng đời một request."""
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session


async def dispose_engine() -> None:
    """Đóng toàn bộ connection pool — gọi trong lifespan handler lúc tắt ứng dụng."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
