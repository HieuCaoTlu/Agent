"""Import tập trung mọi model để SQLAlchemy mapper resolve được forward reference
(`"Session"`, `"VoiceTurn"`...) và để Alembic autogenerate thấy đủ bảng qua `Base.metadata`.
"""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.confirmation import CitizenConfirmation
from app.models.extraction import Extraction, FieldHistory, FieldState
from app.models.session import Session
from app.models.voice import VoiceTurn

__all__ = [
    "Base",
    "Session",
    "VoiceTurn",
    "Extraction",
    "FieldState",
    "FieldHistory",
    "CitizenConfirmation",
    "AuditLog",
]
