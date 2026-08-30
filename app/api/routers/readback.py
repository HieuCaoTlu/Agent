"""Router J6 — Đọc lại và xác nhận."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_readback_service, get_tts_cache_service
from app.api.schemas import CitizenConfirmationResponse, CitizenConfirmRequest, ReadbackResponse
from app.config import Settings, get_settings
from app.db.database import get_db
from app.services.readback_service import ReadbackService
from app.services.tts_cache_service import TTSCacheService

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["readback"])

# Ánh xạ định dạng audio TTS (config) -> media type HTTP chuẩn. `pcm` không có
# media type MIME chuẩn phổ biến — dùng octet-stream, frontend tự biết cách
# giải mã theo `blaze_tts_pcm_sample_rate` đã cấu hình sẵn.
_AUDIO_FORMAT_MEDIA_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "pcm": "application/octet-stream",
}


@router.post("/readback", response_model=ReadbackResponse)
async def generate_readback(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    service: ReadbackService = Depends(get_readback_service),
) -> ReadbackResponse:
    """Sinh nội dung và audio đọc lại. Audio (nếu có) được lưu vào Redis theo
    `session_id` — tải về qua `GET /readback/audio` ngay sau đó."""
    outcome = await service.generate_readback(session_id)
    await db.commit()
    return ReadbackResponse.from_domain(outcome)


@router.get("/readback/audio")
async def get_readback_audio(
    session_id: uuid.UUID,
    tts_cache: TTSCacheService = Depends(get_tts_cache_service),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Tải audio TTS đã sinh gần nhất cho phiên — 404 nếu chưa đọc lại hoặc đã hết TTL."""
    audio_bytes = await tts_cache.retrieve_for_session(session_id)
    if audio_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="Chưa có audio đọc lại cho phiên này, hoặc đã hết hạn lưu tạm.",
        )
    media_type = _AUDIO_FORMAT_MEDIA_TYPES.get(
        settings.blaze_tts_audio_format, "application/octet-stream"
    )
    return Response(content=audio_bytes, media_type=media_type)


@router.post("/citizen-confirm", response_model=CitizenConfirmationResponse)
async def citizen_confirm(
    session_id: uuid.UUID,
    body: CitizenConfirmRequest,
    db: AsyncSession = Depends(get_db),
    service: ReadbackService = Depends(get_readback_service),
) -> CitizenConfirmationResponse:
    """Ghi nhận xác nhận/từ chối của người dân sau khi nghe/đọc lại.

    TODO(J7): hỗ trợ header `Idempotency-Key` — chưa hiện thực ở MVP này
    (xem Checklist.MD mục J7).
    """
    confirmation = await service.record_citizen_confirmation(
        session_id,
        confirmed=body.confirmed,
        readback_text=body.readback_text,
        staff_name=body.staff_name,
        note=body.note,
        readback_method=body.readback_method,
    )
    await db.commit()
    return CitizenConfirmationResponse.from_model(confirmation)
