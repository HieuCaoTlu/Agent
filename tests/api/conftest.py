"""Fixture cho test tầng API (J) — dùng `httpx.AsyncClient` gọi thẳng ASGI app.

Override toàn bộ dependency I/O thật (DB, Redis, provider AI) bằng phiên bản
test: `db_session` (SQLite in-memory, từ `tests/conftest.py`) và `AsyncMock`
cho Redis — không cần Postgres/Redis/Blaze/Claude thật chạy để test router.
"""

from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_catalog_service
from app.db.database import get_db
from app.db.redis_client import get_redis
from app.main import app
from app.services.catalog_service import CatalogService

_CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "static_data" / "procedures"
FIXED_ACTIVE_DATE = date(2026, 9, 15)


class _FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return FIXED_ACTIVE_DATE


@pytest.fixture(autouse=True)
def _freeze_today_everywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đóng băng `date.today()` trong mọi service — catalog thật có
    `effective_from` ở tương lai gần so với ngày hệ thống dev thật (cùng kỹ
    thuật đã dùng từ `tests/services/test_session_service.py`)."""
    for module in (
        "app.services.session_service",
        "app.services.extraction_service",
        "app.services.field_service",
        "app.services.readback_service",
        "app.api.routers.procedures",
    ):
        monkeypatch.setattr(f"{module}.date", _FixedDate)


@pytest.fixture
def redis_mock() -> AsyncMock:
    """Redis giả lập bằng `dict` trong bộ nhớ — đủ để `set`/`get`/`delete` hoạt
    động thật giữa nhiều lệnh gọi trong cùng một test (ví dụ: đọc lại giá trị
    vừa `store_for_session()` ghi), không cần Redis thật chạy. TTL/`expire`
    không mô phỏng (không cần cho test router)."""
    store: dict[str, bytes] = {}
    mock = AsyncMock()

    async def _set(key: str, value: bytes, **kwargs: object) -> None:
        store[key] = value

    async def _get(key: str) -> bytes | None:
        return store.get(key)

    async def _delete(*keys: str) -> None:
        for key in keys:
            store.pop(key, None)

    mock.set.side_effect = _set
    mock.get.side_effect = _get
    mock.delete.side_effect = _delete
    return mock


@pytest_asyncio.fixture
async def client(db_session, redis_mock: AsyncMock) -> AsyncIterator[AsyncClient]:
    async def _override_get_db() -> AsyncIterator:
        yield db_session

    async def _override_get_redis() -> AsyncIterator:
        yield redis_mock

    def _override_get_catalog_service() -> CatalogService:
        return CatalogService(_CATALOG_DIR)

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    app.dependency_overrides[get_catalog_service] = _override_get_catalog_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
