"""Factory chọn `TTSProvider` theo cấu hình — Mục H1 của Checklist.

Nơi duy nhất quyết định dùng provider thật hay mock — service khác luôn nhận
một `TTSProvider` đã dựng sẵn (dependency injection), không tự gọi factory.
"""

from urllib.parse import urlparse

from app.config import Settings
from app.tts.base import TTSProvider
from app.tts.blaze_provider import BlazeBatchTTS
from app.tts.exceptions import UnapprovedHostError
from app.tts.mock_provider import MockTTSProvider


def create_tts_provider(settings: Settings) -> TTSProvider:
    if settings.tts_provider == "mock":
        return MockTTSProvider()

    assert settings.blaze_api_token is not None  # Settings validator đã bắt buộc khi 'blaze'
    host = urlparse(settings.blaze_base_url).hostname or ""
    if host not in settings.approved_ai_hosts:
        raise UnapprovedHostError(host)

    return BlazeBatchTTS(
        api_token=settings.blaze_api_token,
        base_url=settings.blaze_base_url,
        model=settings.blaze_tts_model,
        speaker_id=settings.blaze_tts_speaker_id,
        language=settings.blaze_tts_language,
        audio_format=settings.blaze_tts_audio_format,
        audio_quality=settings.blaze_tts_audio_quality,
        audio_speed=settings.blaze_tts_audio_speed,
        normalization=settings.blaze_tts_normalization,
    )
