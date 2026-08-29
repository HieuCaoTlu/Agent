"""Fixture dùng chung cho toàn bộ test — DB SQLite in-memory, cô lập từng test."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Một AsyncSession trên SQLite in-memory, schema tạo mới cho mỗi test.

    Dùng SQLite thay Postgres ở đây để test chạy nhanh, không cần hạ tầng —
    phù hợp cho test đơn vị của repository layer (CRUD, constraint cơ bản).
    Hành vi đặc thù Postgres (REVOKE UPDATE/DELETE, generated column) không
    kiểm tra được ở đây — xem migrations/versions cho các trường hợp đó.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
