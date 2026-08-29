"""`TTSCacheService` — Mục H2 của Checklist.

Lưu audio kết quả TTS vào Redis với TTL ngắn, phục vụ endpoint tải về (frontend
gọi TTS xong không cần giữ audio ở client, tải lại qua key khi cần — ví dụ
người dân xin nghe lại). Key không mang thông tin cá nhân, chỉ là UUID ngẫu
nhiên — nội dung audio có thể chứa dữ liệu công dân nên TTL phải ngắn.
"""

import uuid

import redis.asyncio as redis

_KEY_PREFIX = "tts_audio:"
_DEFAULT_TTL_SECONDS = 300


class TTSCacheService:
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    async def store(self, audio_bytes: bytes) -> str:
        """Lưu audio, trả về key để tải lại (dùng trong URL endpoint tải về)."""
        key = f"{_KEY_PREFIX}{uuid.uuid4()}"
        await self._redis.set(key, audio_bytes, ex=self._ttl_seconds)
        return key

    async def retrieve(self, key: str) -> bytes | None:
        """Lấy lại audio theo key — `None` nếu không tồn tại hoặc đã hết TTL."""
        return await self._redis.get(key)
