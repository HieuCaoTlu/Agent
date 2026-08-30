"""Cấu hình ứng dụng, đọc từ biến môi trường (.env).

Đối chiếu với `.env.example` — mọi biến môi trường liệt kê ở đó phải có field
tương ứng trong `Settings` bên dưới.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_csv(value: str | list[str]) -> list[str]:
    """Chuyển chuỗi phân cách dấu phẩy trong .env thành list[str], bỏ khoảng trắng thừa."""
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Ứng dụng ----------
    app_env: Literal["development", "staging", "production"] = "development"
    secret_key: str = "change-me-to-a-random-32-byte-secret"
    jwt_expire_hours: int = 8

    # ---------- PostgreSQL ----------
    database_url: str = "postgresql+asyncpg://app_user:app_password@localhost:5432/tthc_ai"

    # ---------- Redis ----------
    redis_url: str = "redis://localhost:6379/0"

    # ---------- Nhà cung cấp AI (chọn provider) ----------
    stt_provider: Literal["mock", "blaze"] = "mock"
    tts_provider: Literal["mock", "blaze"] = "mock"
    llm_provider: Literal["mock", "claude", "gemini"] = "claude"

    # ---------- Claude API (Anthropic) ----------
    anthropic_api_key: str | None = None
    llm_model: str = "claude-sonnet-5"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2

    # ---------- Gemini API (Google) ----------
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # ---------- Blaze API ----------
    blaze_api_token: str | None = None
    blaze_base_url: str = "https://api.blaze.vn"
    blaze_ws_base_url: str = "wss://api.blaze.vn"

    # --- STT (Speech-to-Text) ---
    blaze_stt_async_model: str = "stt-async-1.5"
    blaze_stt_stream_model: str = "stt-stream-1.5"
    blaze_stt_language: str = "vi"
    blaze_stt_topic: str = ""
    blaze_stt_context: str = ""
    blaze_stt_bias_keywords: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # --- TTS (Text-to-Speech) ---
    blaze_tts_model: str = "v2.0_pro"
    blaze_tts_realtime_model: str = "2.0-realtime"
    blaze_tts_speaker_id: str = "HN-Nam-1-BL"
    blaze_tts_language: str = "vi"
    blaze_tts_audio_format: Literal["pcm", "mp3", "opus", "wav"] = "mp3"
    blaze_tts_audio_quality: int = 64
    blaze_tts_audio_speed: float = 1.0
    blaze_tts_normalization: str = "basic"
    blaze_tts_pcm_sample_rate: int = 24000

    # ---------- Danh sách nhà cung cấp AI được duyệt (NT-10) ----------
    approved_ai_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "api.anthropic.com",
            "api.blaze.vn",
            "generativelanguage.googleapis.com",
        ]
    )

    # ---------- Ngưỡng nghiệp vụ ----------
    stt_min_confidence: float = 0.65
    max_extractions_per_session: int = 5
    max_recording_seconds: int = 120
    audio_buffer_ttl_seconds: int = 120
    max_concurrent_sessions_per_staff: int = 3

    # ---------- Thời hạn lưu trữ ----------
    transcript_retention_days: int = 90
    audit_retention_days: int = 730

    # ---------- CORS ----------
    frontend_origin: str = "http://localhost:5173"

    @field_validator("approved_ai_hosts", "blaze_stt_bias_keywords", mode="before")
    @classmethod
    def _parse_csv_fields(cls, value: str | list[str]) -> list[str]:
        return _split_csv(value)

    @model_validator(mode="after")
    def _require_anthropic_key_for_claude(self) -> "Settings":
        if self.llm_provider == "claude" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY là bắt buộc khi LLM_PROVIDER=claude. "
                "Điền giá trị trong file .env hoặc đổi LLM_PROVIDER=mock để phát triển."
            )
        return self

    @model_validator(mode="after")
    def _require_gemini_key_for_gemini(self) -> "Settings":
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY là bắt buộc khi LLM_PROVIDER=gemini. "
                "Điền giá trị trong file .env hoặc đổi LLM_PROVIDER=mock để phát triển."
            )
        return self

    @model_validator(mode="after")
    def _require_blaze_token_for_blaze(self) -> "Settings":
        needs_blaze = self.stt_provider == "blaze" or self.tts_provider == "blaze"
        if needs_blaze and not self.blaze_api_token:
            raise ValueError(
                "BLAZE_API_TOKEN là bắt buộc khi STT_PROVIDER=blaze hoặc TTS_PROVIDER=blaze. "
                "Điền giá trị trong file .env hoặc đổi provider về mock để phát triển."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Trả về instance `Settings` dùng chung, cache lại — dùng làm FastAPI dependency."""
    return Settings()
