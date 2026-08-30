"""Dependency injection dùng chung cho mọi router — Mục J của Checklist.

Mỗi hàm `get_*_service` là một FastAPI dependency: nhận `AsyncSession` từ
`get_db()` (vòng đời một request) và các thành phần không có trạng thái theo
request (catalog, provider AI, Redis client) từ dependency lồng nhau bên dưới.
Router không tự new() service hay tự gọi factory — luôn qua `Depends(...)` ở
đây, để test có thể `app.dependency_overrides[...]` thay bằng fake/mock.
"""

from functools import lru_cache

import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_db
from app.db.redis_client import get_redis
from app.llm.base import LLMProvider
from app.llm.factory import create_llm_provider
from app.repositories.audit_repository import AuditRepository
from app.repositories.citizen_confirmation_repository import CitizenConfirmationRepository
from app.repositories.extraction_repository import ExtractionRepository
from app.repositories.field_history_repository import FieldHistoryRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.voice_turn_repository import VoiceTurnRepository
from app.services.catalog_service import CatalogService
from app.services.extraction_service import ExtractionService
from app.services.field_service import FieldService
from app.services.readback_service import ReadbackService
from app.services.session_service import SessionService
from app.services.tts_cache_service import TTSCacheService
from app.services.voice_service import VoiceService
from app.stt.base import STTProvider
from app.stt.factory import create_stt_provider
from app.tts.base import TTSProvider
from app.tts.factory import create_tts_provider


@lru_cache
def get_catalog_service() -> CatalogService:
    """Catalog nạp một lần, dùng chung toàn app (D2) — không đọc lại file mỗi request."""
    return CatalogService()


@lru_cache
def get_llm_provider() -> LLMProvider:
    return create_llm_provider(get_settings())


@lru_cache
def get_stt_provider() -> STTProvider:
    return create_stt_provider(get_settings())


@lru_cache
def get_tts_provider() -> TTSProvider:
    return create_tts_provider(get_settings())


async def get_tts_cache_service(
    redis_client: redis.Redis = Depends(get_redis),
) -> TTSCacheService:
    return TTSCacheService(redis_client)


def get_session_service(
    db: AsyncSession = Depends(get_db),
    catalog: CatalogService = Depends(get_catalog_service),
) -> SessionService:
    return SessionService(
        session_repository=SessionRepository(db),
        field_state_repository=FieldStateRepository(db),
        audit_repository=AuditRepository(db),
        catalog_service=catalog,
    )


def get_extraction_service(
    db: AsyncSession = Depends(get_db),
    catalog: CatalogService = Depends(get_catalog_service),
    llm: LLMProvider = Depends(get_llm_provider),
    settings: Settings = Depends(get_settings),
) -> ExtractionService:
    return ExtractionService(
        session_repository=SessionRepository(db),
        voice_turn_repository=VoiceTurnRepository(db),
        extraction_repository=ExtractionRepository(db),
        field_state_repository=FieldStateRepository(db),
        field_history_repository=FieldHistoryRepository(db),
        audit_repository=AuditRepository(db),
        catalog_service=catalog,
        llm_provider=llm,
        max_extractions_per_session=settings.max_extractions_per_session,
    )


def get_field_service(
    db: AsyncSession = Depends(get_db),
    catalog: CatalogService = Depends(get_catalog_service),
) -> FieldService:
    return FieldService(
        session_repository=SessionRepository(db),
        field_state_repository=FieldStateRepository(db),
        field_history_repository=FieldHistoryRepository(db),
        audit_repository=AuditRepository(db),
        catalog_service=catalog,
    )


def get_readback_service(
    db: AsyncSession = Depends(get_db),
    catalog: CatalogService = Depends(get_catalog_service),
    tts: TTSProvider = Depends(get_tts_provider),
    tts_cache: TTSCacheService = Depends(get_tts_cache_service),
) -> ReadbackService:
    return ReadbackService(
        session_repository=SessionRepository(db),
        field_state_repository=FieldStateRepository(db),
        citizen_confirmation_repository=CitizenConfirmationRepository(db),
        audit_repository=AuditRepository(db),
        catalog_service=catalog,
        tts_provider=tts,
        tts_cache_service=tts_cache,
    )


def get_voice_service(
    db: AsyncSession = Depends(get_db),
    stt: STTProvider = Depends(get_stt_provider),
    redis_client: redis.Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> VoiceService:
    return VoiceService(
        session_repository=SessionRepository(db),
        voice_turn_repository=VoiceTurnRepository(db),
        audit_repository=AuditRepository(db),
        stt_provider=stt,
        redis_client=redis_client,
        audio_buffer_ttl_seconds=settings.audio_buffer_ttl_seconds,
    )


async def get_voice_turn_repository(db: AsyncSession = Depends(get_db)) -> VoiceTurnRepository:
    """Dùng riêng ở J3 (GET/PATCH turns) — không cần dựng cả `VoiceService`."""
    return VoiceTurnRepository(db)


async def get_extraction_repository(db: AsyncSession = Depends(get_db)) -> ExtractionRepository:
    """Dùng riêng ở J4 (`GET /extractions` — lịch sử, không gọi LLM)."""
    return ExtractionRepository(db)


async def get_audit_repository(db: AsyncSession = Depends(get_db)) -> AuditRepository:
    return AuditRepository(db)
