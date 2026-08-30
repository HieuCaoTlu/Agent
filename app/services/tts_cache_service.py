"""`TTSCacheService` — Mục H2 của Checklist.

Lưu audio kết quả TTS vào Redis với TTL ngắn, phục vụ endpoint tải về (frontend
gọi TTS xong không cần giữ audio ở client, tải lại qua key khi cần — ví dụ
người dân xin nghe lại). Key không mang thông tin cá nhân, chỉ là UUID ngẫu
nhiên — nội dung audio có thể chứa dữ liệu công dân nên TTL phải ngắn.
"""

import uuid

import redis.asyncio as redis

_KEY_PREFIX = "tts_audio:"
_SESSION_KEY_PREFIX = "tts_audio_session:"
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

    async def store_for_session(self, session_id: uuid.UUID, audio_bytes: bytes) -> str:
        """Lưu audio đọc lại mới nhất của một phiên — key cố định (ghi đè lần đọc trước).

        Dùng cho `GET /sessions/{id}/readback/audio` (J6): endpoint không mang
        theo key ngẫu nhiên trong URL, nên phải tra theo `session_id` thay vì
        UUID ngẫu nhiên như `store()`.
        """
        key = f"{_SESSION_KEY_PREFIX}{session_id}"
        await self._redis.set(key, audio_bytes, ex=self._ttl_seconds)
        return key

    async def retrieve_for_session(self, session_id: uuid.UUID) -> bytes | None:
        """Lấy audio đọc lại mới nhất của phiên — `None` nếu chưa đọc lại hoặc đã hết TTL."""
        return await self._redis.get(f"{_SESSION_KEY_PREFIX}{session_id}")
