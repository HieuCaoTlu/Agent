"""Test `TTSCacheService` — mock client Redis, không cần Redis thật chạy."""

from unittest.mock import AsyncMock

from app.services.tts_cache_service import TTSCacheService


async def test_store_sets_key_with_ttl_and_returns_key() -> None:
    redis_client = AsyncMock()
    service = TTSCacheService(redis_client, ttl_seconds=60)

    key = await service.store(b"audio-bytes")

    assert key.startswith("tts_audio:")
    redis_client.set.assert_awaited_once_with(key, b"audio-bytes", ex=60)


async def test_retrieve_returns_bytes_from_redis() -> None:
    redis_client = AsyncMock()
    redis_client.get.return_value = b"cached-audio"
    service = TTSCacheService(redis_client)

    result = await service.retrieve("tts_audio:some-uuid")
    assert result == b"cached-audio"
    redis_client.get.assert_awaited_once_with("tts_audio:some-uuid")


async def test_retrieve_returns_none_when_missing() -> None:
    redis_client = AsyncMock()
    redis_client.get.return_value = None
    service = TTSCacheService(redis_client)

    result = await service.retrieve("tts_audio:khong-ton-tai")
    assert result is None


async def test_default_ttl_is_short() -> None:
    redis_client = AsyncMock()
    service = TTSCacheService(redis_client)
    await service.store(b"x")
    _, kwargs = redis_client.set.call_args
    assert kwargs["ex"] <= 600  # TTL ngắn — không giữ audio dữ liệu công dân lâu
