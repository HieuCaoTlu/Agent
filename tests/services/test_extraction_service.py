"""Test `ExtractionService` — Mục I2 của Checklist (12 bước, UC2, UC4)."""

import json
import uuid
from datetime import date
from pathlib import Path

import pytest

from app.domain.exceptions import DomainError
from app.llm.base import LLMProvider, LLMResponse
from app.llm.exceptions import LLMConnectionError
from app.models.session import Session
from app.models.voice import VoiceTurn
from app.repositories.audit_repository import AuditRepository
from app.repositories.extraction_repository import ExtractionRepository
from app.repositories.field_history_repository import FieldHistoryRepository
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.voice_turn_repository import VoiceTurnRepository
from app.services.catalog_service import CatalogService
from app.services.extraction_service import (
    ExtractionLimitExceeded,
    ExtractionService,
    SessionNotFoundForExtraction,
)

_CATALOG_DIR = Path(__file__).resolve().parent.parent.parent / "app" / "static_data" / "procedures"
_FIXED_ACTIVE_DATE = date(2026, 9, 15)


class _FixedDate(date):
    @classmethod
    def today(cls) -> date:
        return _FIXED_ACTIVE_DATE


@pytest.fixture(autouse=True)
def _freeze_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.extraction_service.date", _FixedDate)


class _ScriptedLLMProvider(LLMProvider):
    """Fake provider — trả lần lượt các response đã kịch bản hóa, hoặc ném lỗi."""

    def __init__(self, responses: list[dict | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    async def extract(self, system_prompt: str, user_message: str) -> LLMResponse:
        self.calls.append((system_prompt, user_message))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(
            raw_text=json.dumps(item, ensure_ascii=False),
            input_tokens=10,
            output_tokens=5,
            latency_ms=1,
            model="fake-model",
        )

    async def health_check(self) -> bool:
        return True


async def _make_session_with_procedure(db_session, code: str = "dang_ky_khai_sinh") -> Session:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state="EXTRACTING", procedure_code=code)
    await session_repo.create(session)

    catalog = CatalogService(_CATALOG_DIR)
    procedure = catalog.get(code, _FIXED_ACTIVE_DATE)
    field_repo = FieldStateRepository(db_session)
    for field in procedure.fields:
        await field_repo.upsert(session.id, field.name)
    await db_session.commit()
    return session


async def _add_turn(db_session, session_id: uuid.UUID, text: str, turn_number: int) -> VoiceTurn:
    turn = VoiceTurn(session_id=session_id, turn_number=turn_number, raw_transcript=text)
    await VoiceTurnRepository(db_session).add(turn)
    await db_session.commit()
    return turn


def _make_service(
    db_session, llm_provider: LLMProvider, max_extractions: int = 5
) -> ExtractionService:
    return ExtractionService(
        session_repository=SessionRepository(db_session),
        voice_turn_repository=VoiceTurnRepository(db_session),
        extraction_repository=ExtractionRepository(db_session),
        field_state_repository=FieldStateRepository(db_session),
        field_history_repository=FieldHistoryRepository(db_session),
        audit_repository=AuditRepository(db_session),
        catalog_service=CatalogService(_CATALOG_DIR),
        llm_provider=llm_provider,
        max_extractions_per_session=max_extractions,
    )


async def test_extract_session_not_found_raises(db_session) -> None:
    service = _make_service(db_session, _ScriptedLLMProvider([]))
    with pytest.raises(SessionNotFoundForExtraction):
        await service.extract(uuid.uuid4(), include_turns=[1])


async def test_extract_without_procedure_raises(db_session) -> None:
    session_repo = SessionRepository(db_session)
    session = Session(staff_name="Cán bộ A", state="LISTENING")
    await session_repo.create(session)
    await db_session.commit()

    service = _make_service(db_session, _ScriptedLLMProvider([]))
    with pytest.raises(DomainError):
        await service.extract(session.id, include_turns=[1])


async def test_extract_success_saves_extraction_and_field_state(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Cháu tên Nguyễn Văn Bình, sinh ngày 2020-05-10", 1)

    provider = _ScriptedLLMProvider(
        [
            {
                "fields": [
                    {
                        "name": "ho_ten_nguoi_duoc_khai_sinh",
                        "status": "extracted",
                        "value": "Nguyễn Văn Bình",
                        "confidence": "high",
                        "evidence": "Cháu tên Nguyễn Văn Bình",
                    }
                ],
                "observations": [],
            }
        ]
    )
    service = _make_service(db_session, provider)

    outcome = await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    assert outcome.extraction.status == "success"
    assert outcome.extraction.attempt_number == 1

    field_states = await FieldStateRepository(db_session).list_by_session(session.id)
    ho_ten = next(fs for fs in field_states if fs.field_name == "ho_ten_nguoi_duoc_khai_sinh")
    assert ho_ten.suggested_value == "Nguyễn Văn Bình"
    assert ho_ten.suggested_by == "llm"
    assert ho_ten.ai_confidence == "high"
    assert ho_ten.validation_status == "ok"

    history = await FieldHistoryRepository(db_session).list_by_field(
        session.id, "ho_ten_nguoi_duoc_khai_sinh"
    )
    assert len(history) == 1
    assert history[0].change_source == "llm_extraction"
    assert history[0].new_value == "Nguyễn Văn Bình"


async def test_extract_invalid_value_marked_format_error(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Số điện thoại của tôi là chín một hai", 1)

    provider = _ScriptedLLMProvider(
        [
            {
                "fields": [
                    {
                        "name": "so_dien_thoai",
                        "status": "extracted",
                        "value": "912",  # sai định dạng — vn_phone_10_digits sẽ fail
                        "confidence": "medium",
                        "evidence": "chín một hai",
                    }
                ],
                "observations": [],
            }
        ]
    )
    service = _make_service(db_session, provider)
    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    field_states = await FieldStateRepository(db_session).list_by_session(session.id)
    phone = next(fs for fs in field_states if fs.field_name == "so_dien_thoai")
    assert phone.validation_status == "format_error"
    assert phone.validation_message


async def test_extract_llm_error_saves_failed_extraction(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Xin chào", 1)

    provider = _ScriptedLLMProvider([LLMConnectionError("mất mạng")])
    service = _make_service(db_session, provider)

    outcome = await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    assert outcome.extraction.status == "api_error"
    assert "mất mạng" in outcome.extraction.error_detail

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "extraction_failed" for log in logs)


async def test_extract_llm_error_transitions_session_to_ai_unavailable(db_session) -> None:
    """L1 (bắt buộc, NT-8): LLM lỗi → chuyển phiên sang AI_UNAVAILABLE."""
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Xin chào", 1)

    provider = _ScriptedLLMProvider([LLMConnectionError("mất mạng")])
    service = _make_service(db_session, provider)

    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    refreshed = await SessionRepository(db_session).get(session.id)
    assert refreshed.state == "AI_UNAVAILABLE"


async def test_extract_success_transitions_session_to_suggested(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Xin chào", 1)

    provider = _ScriptedLLMProvider([{"fields": [], "observations": []}])
    service = _make_service(db_session, provider)

    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    refreshed = await SessionRepository(db_session).get(session.id)
    assert refreshed.state == "SUGGESTED"


async def test_extract_parse_failed_does_not_change_session_state(db_session) -> None:
    """Chỉ api_error mới chuyển AI_UNAVAILABLE — parse_failed không phải lỗi
    hạ tầng AI (quyết định của người dùng)."""
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Xin chào", 1)

    class _BadJSONProvider(LLMProvider):
        async def extract(self, system_prompt: str, user_message: str) -> LLMResponse:
            return LLMResponse(
                raw_text="khong-phai-json", input_tokens=1, output_tokens=1, latency_ms=1, model="m"
            )

        async def health_check(self) -> bool:
            return True

    service = _make_service(db_session, _BadJSONProvider())
    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    refreshed = await SessionRepository(db_session).get(session.id)
    assert refreshed.state == "EXTRACTING"  # giữ nguyên — không lùi, không tiến


async def test_amend_field_llm_error_does_not_change_session_state(db_session) -> None:
    """UC4 (sửa một trường) không được lùi trạng thái cả phiên dù LLM lỗi."""
    session = await _make_session_with_procedure(db_session)

    provider = _ScriptedLLMProvider([LLMConnectionError("mất mạng")])
    service = _make_service(db_session, provider)

    await service.amend_field(session.id, "ngay_sinh", transcript_turns=["abc"])
    await db_session.commit()

    refreshed = await SessionRepository(db_session).get(session.id)
    assert refreshed.state == "EXTRACTING"


async def test_extract_malformed_json_saves_parse_failed(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Xin chào", 1)

    class _BadJSONProvider(LLMProvider):
        async def extract(self, system_prompt: str, user_message: str) -> LLMResponse:
            return LLMResponse(
                raw_text="khong-phai-json", input_tokens=1, output_tokens=1, latency_ms=1, model="m"
            )

        async def health_check(self) -> bool:
            return True

    service = _make_service(db_session, _BadJSONProvider())
    outcome = await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    assert outcome.extraction.status == "parse_failed"


async def test_extract_respects_max_extractions_limit(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Xin chào", 1)

    provider = _ScriptedLLMProvider([{"fields": [], "observations": []}])
    service = _make_service(db_session, provider, max_extractions=1)

    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    with pytest.raises(ExtractionLimitExceeded):
        await service.extract(session.id, include_turns=[1])


async def test_extract_merge_keeps_confirmed_value_on_conflict(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Cháu sinh ngày 2020-05-10", 1)

    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(
        session.id, "ngay_sinh", confirmed_value="2020-05-01", is_confirmed=True
    )
    await db_session.commit()

    provider = _ScriptedLLMProvider(
        [
            {
                "fields": [
                    {
                        "name": "ngay_sinh",
                        "status": "extracted",
                        "value": "2020-05-10",
                        "confidence": "high",
                        "evidence": "sinh ngày 2020-05-10",
                    }
                ],
                "observations": [],
            }
        ]
    )
    service = _make_service(db_session, provider)
    outcome = await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    ngay_sinh = await field_repo.get(session.id, "ngay_sinh")
    assert ngay_sinh.confirmed_value == "2020-05-01"  # giữ nguyên giá trị đã xác nhận
    assert ngay_sinh.suggested_value is None  # không bị merge_result ghi đè suggested_value

    logs = await AuditRepository(db_session).list_by_session(session.id)
    assert any(log.action == "extraction_requested" for log in logs)
    assert outcome.extraction.status == "success"


async def test_extract_only_includes_selected_turns(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "LƯỢT MỘT bí mật không nên gửi", 1)
    await _add_turn(db_session, session.id, "LƯỢT HAI nội dung thật", 2)

    provider = _ScriptedLLMProvider([{"fields": [], "observations": []}])
    service = _make_service(db_session, provider)

    await service.extract(session.id, include_turns=[2])
    await db_session.commit()

    _, user_message = provider.calls[0]
    assert "LƯỢT HAI" in user_message
    assert "LƯỢT MỘT" not in user_message


async def test_extract_redacts_cccd_before_calling_llm(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    await _add_turn(db_session, session.id, "Số CCCD của tôi là 012345678901", 1)

    provider = _ScriptedLLMProvider([{"fields": [], "observations": []}])
    service = _make_service(db_session, provider)
    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    _, user_message = provider.calls[0]
    assert "012345678901" not in user_message
    assert "[CCCD_1]" in user_message


async def test_amend_field_extracts_single_field_only(db_session) -> None:
    session = await _make_session_with_procedure(db_session)

    provider = _ScriptedLLMProvider(
        [
            {
                "fields": [
                    {
                        "name": "ngay_sinh",
                        "status": "extracted",
                        "value": "2020-05-10",
                        "confidence": "high",
                        "evidence": "1991",
                    }
                ],
                "observations": [],
            }
        ]
    )
    service = _make_service(db_session, provider)

    outcome = await service.amend_field(
        session.id, "ngay_sinh", transcript_turns=["Sai, tôi sinh năm 2020 không phải 1990"]
    )
    await db_session.commit()

    assert outcome.extraction.status == "success"
    field_states = await FieldStateRepository(db_session).list_by_session(session.id)
    ngay_sinh = next(fs for fs in field_states if fs.field_name == "ngay_sinh")
    assert ngay_sinh.suggested_value == "2020-05-10"


async def test_amend_field_unknown_field_raises(db_session) -> None:
    session = await _make_session_with_procedure(db_session)
    service = _make_service(db_session, _ScriptedLLMProvider([]))

    with pytest.raises(DomainError):
        await service.amend_field(session.id, "khong_ton_tai", transcript_turns=["abc"])


async def test_extract_from_procedure_selected_advances_through_extracting(db_session) -> None:
    """Luồng thật (không giả lập trực tiếp EXTRACTING như fixture chuẩn):
    PROCEDURE_SELECTED --REQUEST_EXTRACTION--> EXTRACTING --EXTRACTION_SUCCESS--> SUGGESTED."""
    session = await _make_session_with_procedure(db_session)
    session.state = "PROCEDURE_SELECTED"
    await SessionRepository(db_session).update(session)
    await db_session.commit()
    await _add_turn(db_session, session.id, "Xin chào", 1)

    provider = _ScriptedLLMProvider([{"fields": [], "observations": []}])
    service = _make_service(db_session, provider)

    await service.extract(session.id, include_turns=[1])
    await db_session.commit()

    refreshed = await SessionRepository(db_session).get(session.id)
    assert refreshed.state == "SUGGESTED"
