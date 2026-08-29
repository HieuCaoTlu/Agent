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

from app.config import get_settings
from app.domain.exceptions import InvalidTransitionError, ProcedureNotFound

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
    """Kết nối/ngắt DB, Redis, nạp catalog khi khởi động/tắt ứng dụng."""
    settings = get_settings()
    logger.info("app_starting", app_env=settings.app_env)

    # TODO(B1): khởi tạo async engine + sessionmaker (app.db.database)
    # TODO(B1): khởi tạo Redis connection pool (app.db.redis_client)
    # TODO(D2): nạp CatalogService, cache toàn bộ file JSON catalog vào bộ nhớ

    yield

    logger.info("app_stopping")
    # TODO(B1): đóng engine DB, đóng Redis pool


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
        """Kiểm tra DB, Redis, các provider AI.

        TODO: thay các giá trị "unknown" bằng health_check() thật của từng
        thành phần khi B1 (DB/Redis) và F/G/H (LLM/STT/TTS provider) hoàn thành.
        """
        return {
            "status": "ok",
            "app_env": settings.app_env,
            "checks": {
                "database": "unknown",
                "redis": "unknown",
                "llm_provider": settings.llm_provider,
                "stt_provider": settings.stt_provider,
                "tts_provider": settings.tts_provider,
            },
        }

    return app


app = create_app()
