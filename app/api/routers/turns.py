"""Router J3 — Lượt thoại."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_voice_service, get_voice_turn_repository
from app.api.schemas import EditTranscriptRequest, FlagTranscriptRequest, VoiceTurnResponse
from app.db.database import get_db
from app.repositories.voice_turn_repository import VoiceTurnRepository
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/api/v1/sessions/{session_id}/turns", tags=["turns"])


@router.get("", response_model=list[VoiceTurnResponse])
async def list_turns(
    session_id: uuid.UUID,
    voice_turns: VoiceTurnRepository = Depends(get_voice_turn_repository),
) -> list[VoiceTurnResponse]:
    turns = await voice_turns.list_by_session(session_id)
    return [VoiceTurnResponse.from_model(t) for t in turns]


@router.patch("/{turn_id}", response_model=VoiceTurnResponse)
async def edit_turn_transcript(
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    body: EditTranscriptRequest,
    db: AsyncSession = Depends(get_db),
    service: VoiceService = Depends(get_voice_service),
) -> VoiceTurnResponse:
    """Cán bộ sửa transcript đã nhận diện (UC5).

    `session_id` không dùng trực tiếp (turn đã tự mang `session_id`) — giữ
    trong path để khớp cấu trúc REST lồng nhau `/sessions/{id}/turns/{turn_id}`
    của Checklist; `VoiceTurnNotFound` được xử lý bởi handler chung (J7).
    """
    voice_turn = await service.edit_transcript(turn_id, body.new_text, body.staff_name)
    await db.commit()
    return VoiceTurnResponse.from_model(voice_turn)


@router.post("/{turn_id}/flag", response_model=VoiceTurnResponse)
async def flag_turn(
    session_id: uuid.UUID,
    turn_id: uuid.UUID,
    body: FlagTranscriptRequest,
    db: AsyncSession = Depends(get_db),
    service: VoiceService = Depends(get_voice_service),
) -> VoiceTurnResponse:
    """Cán bộ chủ động đánh dấu một lượt là "chưa rõ" (I4, O2) — không có
    ngưỡng confidence tự động, đánh dấu luôn là hành động thủ công."""
    voice_turn = await service.flag_transcript(turn_id, body.staff_name)
    await db.commit()
    return VoiceTurnResponse.from_model(voice_turn)
