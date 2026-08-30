"""Điểm khởi động ứng dụng FastAPI.

Ghi chú MVP: không có middleware xác thực/JWT ở phiên bản này (xem
Checklist.MD mục "Đã lược bỏ khỏi MVP") — toàn bộ endpoint dùng trực tiếp
trong mạng nội bộ điểm hỗ trợ.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import get_llm_provider, get_stt_provider, get_tts_provider
from app.api.routers import extraction, fields, procedures, readback, sessions, turns
from app.config import get_settings
from app.db.database import dispose_engine, get_engine
from app.db.redis_client import dispose_pool, get_redis
from app.domain.exceptions import DomainError, InvalidTransitionError, ProcedureNotFound
from app.services.extraction_service import ExtractionLimitExceeded

logger = structlog.get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


def _new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def _error_response(
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    detail: str | None = None,
    fallback_available: bool = False,
) -> JSONResponse:
    """Dựng response lỗi theo định dạng thống nhất — Mục 9.1 của Plan."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "detail": detail,
                "request_id": request_id,
                "fallback_available": fallback_available,
            }
        },
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Kết nối/ngắt DB, Redis, nạp catalog khi khởi động/tắt ứng dụng.

    Engine DB, pool Redis và catalog đều tạo lười (lazy, `lru_cache`/biến
    module) ở lần dùng đầu tiên (`app.db.database`, `app.db.redis_client`,
    `app.api.deps.get_catalog_service`) — lifespan chỉ chịu trách nhiệm dọn
    dẹp lúc tắt ứng dụng, không cần chủ động "khởi tạo" ở đây.
    """
    settings = get_settings()
    logger.info("app_starting", app_env=settings.app_env)

    yield

    logger.info("app_stopping")
    await dispose_engine()
    await dispose_pool()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Trợ lý giọng nói AI hỗ trợ TTHC trực tuyến",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or _new_request_id()
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @app.exception_handler(InvalidTransitionError)
    async def handle_invalid_transition(
        request: Request, exc: InvalidTransitionError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _new_request_id())
        logger.warning(
            "invalid_transition",
            request_id=request_id,
            current_state=exc.current_state,
            transition_event=exc.event,
        )
        return _error_response(
            status_code=409,
            code="INVALID_TRANSITION",
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(ProcedureNotFound)
    async def handle_procedure_not_found(request: Request, exc: ProcedureNotFound) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _new_request_id())
        logger.warning("procedure_not_found", request_id=request_id, code=exc.code)
        return _error_response(
            status_code=404,
            code="PROCEDURE_NOT_FOUND",
            message=exc.message,
            request_id=request_id,
        )

    @app.exception_handler(ExtractionLimitExceeded)
    async def handle_extraction_limit_exceeded(
        request: Request, exc: ExtractionLimitExceeded
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _new_request_id())
        logger.warning(
            "extraction_limit_exceeded", request_id=request_id, session_id=str(exc.session_id)
        )
        return _error_response(
            status_code=429,
            code="EXTRACTION_LIMIT_EXCEEDED",
            message=str(exc),
            request_id=request_id,
            fallback_available=True,
        )

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        """Fallback chung cho mọi `DomainError` không có handler riêng ở trên.

        Mỗi service (I1-I5) tự định nghĩa exception "not found" riêng (tránh
        phụ thuộc ngược giữa các service) — ở tầng HTTP chúng đều có cùng ý
        nghĩa 404. Exception nào không phải "not found" (ví dụ
        `NoProcedureSelected`) coi là 409 — trạng thái phiên chưa đủ điều
        kiện thực hiện thao tác, không phải lỗi đầu vào của client.
        """
        request_id = getattr(request.state, "request_id", _new_request_id())
        is_not_found = "NotFound" in type(exc).__name__
        logger.warning(
            "domain_error", request_id=request_id, error_type=type(exc).__name__, error=str(exc)
        )
        return _error_response(
            status_code=404 if is_not_found else 409,
            code=type(exc).__name__,
            message=str(exc),
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _new_request_id())
        logger.error("unhandled_exception", request_id=request_id, error=str(exc), exc_info=exc)
        return _error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Đã có lỗi hệ thống xảy ra, vui lòng thử lại hoặc báo cán bộ kỹ thuật.",
            request_id=request_id,
            detail=str(exc) if settings.app_env != "production" else None,
        )

    @app.get("/health")
    async def health_check() -> dict:
        """Kiểm tra DB, Redis, các provider AI (L1 — suy giảm mềm dựa trên kết quả này)."""
        database_status = "unknown"
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.run_sync(lambda _: None)
            database_status = "ok"
        except Exception:
            database_status = "unreachable"

        redis_status = "unknown"
        try:
            async for client in get_redis():
                await client.ping()
                redis_status = "ok"
        except Exception:
            redis_status = "unreachable"

        llm_ok = await get_llm_provider().health_check()
        stt_ok = await get_stt_provider().health_check()
        tts_ok = await get_tts_provider().health_check()

        return {
            "status": "ok",
            "app_env": settings.app_env,
            "checks": {
                "database": database_status,
                "redis": redis_status,
                "llm_provider": settings.llm_provider,
                "llm_provider_ok": llm_ok,
                "stt_provider": settings.stt_provider,
                "stt_provider_ok": stt_ok,
                "tts_provider": settings.tts_provider,
                "tts_provider_ok": tts_ok,
            },
        }

    app.include_router(procedures.router)
    app.include_router(sessions.router)
    app.include_router(turns.router)
    app.include_router(extraction.router)
    app.include_router(fields.router)
    app.include_router(readback.router)

    return app


app = create_app()
