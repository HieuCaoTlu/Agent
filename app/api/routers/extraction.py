"""Router J4 — Trích xuất."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_extraction_repository, get_extraction_service
from app.api.schemas import ExtractionResponse, ExtractRequest
from app.db.database import get_db
from app.repositories.extraction_repository import ExtractionRepository
from app.services.extraction_service import ExtractionService

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["extraction"])


@router.post("/extract", response_model=ExtractionResponse)
async def extract(
    session_id: uuid.UUID,
    body: ExtractRequest,
    db: AsyncSession = Depends(get_db),
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResponse:
    """Gọi LLM trích xuất trường dữ liệu từ các lượt thoại đã chọn.

    `ExtractionLimitExceeded` được xử lý bởi handler chung (trả 429, L2).
    """
    outcome = await service.extract(
        session_id, include_turns=body.include_turns, only_missing=body.only_missing
    )
    await db.commit()
    return ExtractionResponse.from_domain(outcome.extraction, outcome.warnings)


@router.get("/extractions", response_model=list[ExtractionResponse])
async def list_extractions(
    session_id: uuid.UUID,
    extractions: ExtractionRepository = Depends(get_extraction_repository),
) -> list[ExtractionResponse]:
    """Lịch sử các lần trích xuất — không tính lại `warnings` (chỉ tại thời
    điểm trích xuất mới có ý nghĩa so với `field_states` hiện tại, xem J5).
    """
    history = await extractions.list_by_session(session_id)
    return [ExtractionResponse.from_model_only(e) for e in history]
