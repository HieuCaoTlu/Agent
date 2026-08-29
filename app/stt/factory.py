"""Factory chọn `STTProvider` theo cấu hình — Mục G1 của Checklist.

Nơi duy nhất quyết định dùng provider thật hay mock — service khác luôn nhận
một `STTProvider` đã dựng sẵn (dependency injection), không tự gọi factory.
"""

from urllib.parse import urlparse

from app.config import Settings
from app.stt.base import STTProvider
from app.stt.blaze_provider import BlazeSTTProvider
from app.stt.exceptions import UnapprovedHostError
from app.stt.mock_provider import MockSTTProvider


def create_stt_provider(settings: Settings) -> STTProvider:
    if settings.stt_provider == "mock":
        return MockSTTProvider()

    assert settings.blaze_api_token is not None  # Settings validator đã bắt buộc khi 'blaze'
    host = urlparse(settings.blaze_base_url).hostname or ""
    if host not in settings.approved_ai_hosts:
        raise UnapprovedHostError(host)

    return BlazeSTTProvider(
        api_token=settings.blaze_api_token,
        base_url=settings.blaze_base_url,
        ws_base_url=settings.blaze_ws_base_url,
        stream_model=settings.blaze_stt_stream_model,
        async_model=settings.blaze_stt_async_model,
        language=settings.blaze_stt_language,
        topic=settings.blaze_stt_topic,
        context=settings.blaze_stt_context,
        bias_keywords=settings.blaze_stt_bias_keywords,
    )
