"""Router J1 — Danh mục thủ tục."""

from datetime import date

from fastapi import APIRouter, Depends

from app.api.deps import get_catalog_service
from app.api.schemas import ProcedureDetailResponse, ProcedureSummaryResponse
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/v1/procedures", tags=["procedures"])


@router.get("", response_model=list[ProcedureSummaryResponse])
async def list_procedures(
    catalog: CatalogService = Depends(get_catalog_service),
) -> list[ProcedureSummaryResponse]:
    """Danh sách thủ tục đang có hiệu lực hôm nay."""
    summaries = catalog.list_active(date.today())
    return [
        ProcedureSummaryResponse(code=s.code, name=s.name, catalog_version=s.catalog_version)
        for s in summaries
    ]


@router.get("/{code}", response_model=ProcedureDetailResponse)
async def get_procedure(
    code: str, catalog: CatalogService = Depends(get_catalog_service)
) -> ProcedureDetailResponse:
    """Chi tiết một thủ tục — field schema và thành phần hồ sơ.

    `ProcedureNotFound` (khi không tồn tại hoặc hết hiệu lực) được xử lý bởi
    exception handler chung ở `app/main.py` (đã có sẵn, trả 404).
    """
    procedure = catalog.get(code, date.today())
    return ProcedureDetailResponse(
        code=procedure.code,
        name=procedure.name,
        catalog_version=procedure.catalog_version,
        legal_basis=procedure.legal_basis,
        fields=procedure.fields,
        required_documents=procedure.required_documents,
    )
