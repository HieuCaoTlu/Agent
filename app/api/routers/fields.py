"""Router J5 — Trường dữ liệu.

Cố ý KHÔNG có endpoint xác nhận hàng loạt (bulk confirm) — NT-1/NT-3: AI hỗ
trợ, không thay thế công chức; cán bộ phải xác nhận từng trường một. Khẳng
định bằng test `tests/api/test_fields_router.py::test_no_bulk_confirm_endpoint`.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_extraction_service, get_field_service
from app.api.schemas import (
    AmendFieldRequest,
    ConfirmFieldRequest,
    ExtractionResponse,
    FieldStateResponse,
    FieldWithValidationResponse,
)
from app.db.database import get_db
from app.services.extraction_service import ExtractionService
from app.services.field_service import FieldService

router = APIRouter(prefix="/api/v1/sessions/{session_id}/fields", tags=["fields"])


@router.get("", response_model=list[FieldWithValidationResponse])
async def get_fields(
    session_id: uuid.UUID, service: FieldService = Depends(get_field_service)
) -> list[FieldWithValidationResponse]:
    fields = await service.get_fields(session_id)
    return [FieldWithValidationResponse.from_domain(f) for f in fields]


@router.post("/{field_name}/confirm", response_model=FieldStateResponse)
async def confirm_field(
    session_id: uuid.UUID,
    field_name: str,
    body: ConfirmFieldRequest,
    db: AsyncSession = Depends(get_db),
    service: FieldService = Depends(get_field_service),
) -> FieldStateResponse:
    """Xác nhận một trường.

    TODO(J7): hỗ trợ header `Idempotency-Key` — chưa hiện thực ở MVP này
    (xem Checklist.MD mục J7).
    """
    field_state = await service.confirm_field(
        session_id, field_name, body.value, staff_name=body.staff_name
    )
    await db.commit()
    return FieldStateResponse.from_model(field_state)


@router.post("/{field_name}/unconfirm", response_model=FieldStateResponse)
async def unconfirm_field(
    session_id: uuid.UUID,
    field_name: str,
    db: AsyncSession = Depends(get_db),
    service: FieldService = Depends(get_field_service),
) -> FieldStateResponse:
    field_state = await service.unconfirm_field(session_id, field_name)
    await db.commit()
    return FieldStateResponse.from_model(field_state)


@router.post("/{field_name}/amend", response_model=ExtractionResponse)
async def amend_field(
    session_id: uuid.UUID,
    field_name: str,
    body: AmendFieldRequest,
    db: AsyncSession = Depends(get_db),
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResponse:
    """Sửa một trường bằng giọng nói (UC4) — chỉ trích xuất lại đúng một trường."""
    outcome = await service.amend_field(session_id, field_name, body.transcript_turns)
    await db.commit()
    return ExtractionResponse.from_domain(outcome.extraction, outcome.warnings)
