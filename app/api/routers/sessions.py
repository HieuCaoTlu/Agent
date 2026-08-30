"""Router J2 — Quản lý phiên.

Mỗi endpoint gọi service (chỉ `flush()`, không tự `commit()` — quy ước xuyên
suốt tầng service từ I1) rồi tự `db.commit()` trước khi trả response, để một
request là một transaction trọn vẹn.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session_service
from app.api.schemas import (
    CancelSessionRequest,
    CompleteSessionRequest,
    ConsentRequest,
    CreateSessionRequest,
    SelectProcedureRequest,
    SessionResponse,
    SessionStateResponse,
)
from app.db.database import get_db
from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = await service.create_session(
        staff_name=body.staff_name, parent_session_id=body.parent_session_id, mode=body.mode
    )
    await db.commit()
    return SessionResponse.from_model(session)


@router.get("/{session_id}", response_model=SessionStateResponse)
async def get_session(
    session_id: uuid.UUID, service: SessionService = Depends(get_session_service)
) -> SessionStateResponse:
    """Trạng thái đầy đủ — phiên, mọi trường, cảnh báo hiện tại.

    `SessionNotFound` được xử lý bởi exception handler chung (`app/main.py`).
    """
    snapshot = await service.get_session_state(session_id)
    return SessionStateResponse.from_domain(snapshot)


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    day: date | None = Query(default=None, description="Lọc theo ngày bắt đầu (giờ VN)"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[SessionResponse]:
    """Danh sách phiên gần đây, có phân trang — dùng cho bảng điều khiển (N).

    Truy vấn trực tiếp qua `SessionRepository` thay vì `SessionService` — đây
    là liệt kê thuần túy, không có logic nghiệp vụ nào cần điều phối.
    """
    repo = SessionRepository(db)
    sessions = (
        await repo.list_by_date(day, limit=limit, offset=offset)
        if day is not None
        else await repo.list_recent(limit=limit, offset=offset)
    )
    return [SessionResponse.from_model(s) for s in sessions]


@router.post("/{session_id}/consent", response_model=SessionResponse)
async def record_consent(
    session_id: uuid.UUID,
    body: ConsentRequest,
    db: AsyncSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = await service.record_consent(session_id, body.consented)
    await db.commit()
    return SessionResponse.from_model(session)


@router.post("/{session_id}/procedure", response_model=SessionResponse)
async def select_procedure(
    session_id: uuid.UUID,
    body: SelectProcedureRequest,
    db: AsyncSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = await service.select_procedure(session_id, body.code)
    await db.commit()
    return SessionResponse.from_model(session)


@router.post("/{session_id}/cancel", response_model=SessionResponse)
async def cancel_session(
    session_id: uuid.UUID,
    body: CancelSessionRequest,
    db: AsyncSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    session = await service.cancel_session(session_id, body.reason)
    await db.commit()
    return SessionResponse.from_model(session)


@router.post("/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: uuid.UUID,
    body: CompleteSessionRequest,
    db: AsyncSession = Depends(get_db),
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    """Kết thúc phiên với mã hồ sơ.

    TODO(J7): hỗ trợ header `Idempotency-Key` — chưa hiện thực ở MVP này
    (xem Checklist.MD mục J7). Gọi lại nhiều lần với cùng `dossier_code` hiện
    tại chỉ an toàn nếu phiên đã ở `COMPLETED`; gọi lại từ trạng thái khác đi
    qua `transition()` như bình thường và có thể ném `InvalidTransitionError`.
    """
    session = await service.complete_session(session_id, body.dossier_code)
    await db.commit()
    return SessionResponse.from_model(session)
