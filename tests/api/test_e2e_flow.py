"""Test tích hợp end-to-end cho tầng API (J) — một luồng duy nhất đi qua
J1-J6 theo đúng thứ tự nghiệp vụ (B1-B7 của Plan.MD).

Phạm vi hẹp có chủ đích: đây KHÔNG phải test lặp lại từng nhánh nghiệp vụ đã
test kỹ ở tầng service (I1-I5) — chỉ xác nhận các router nối đúng với nhau
qua HTTP (request → service → response), theo đúng response_model và đúng
mã lỗi domain → HTTP.

**Khoảng trống đã biết (ghi trong Checklist.MD mục J):** bảng chuyển trạng
thái (C1) có các cạnh `start_listening` (CREATED→LISTENING),
`request_extraction`/`extraction_success` (PROCEDURE_SELECTED→EXTRACTING→
SUGGESTED), `open_review` (SUGGESTED→REVIEWING) mà không service/endpoint
nào (I1-I5, J1-J6) hiện gọi tới — `ExtractionService` không đụng
`session.state`, và J2 không có endpoint `start-listening`/`open-review`.
Test này set thẳng `session.state` qua DB cho các bước đó (đánh dấu rõ bằng
comment `# --- khoảng trống ---`) thay vì gọi API, để không phải sửa service
đã hoàn thiện/test kỹ chỉ để phục vụ một test tích hợp.
"""

import uuid

from httpx import AsyncClient

from app.models.voice import VoiceTurn
from app.repositories.field_state_repository import FieldStateRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.voice_turn_repository import VoiceTurnRepository


async def test_full_session_flow_from_creation_to_completion(
    client: AsyncClient, db_session
) -> None:
    # B1/B2 — tạo phiên, ghi nhận đồng ý (J2)
    create_resp = await client.post(
        "/api/v1/sessions", json={"staff_name": "Cán bộ A"}
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    consent_resp = await client.post(
        f"/api/v1/sessions/{session_id}/consent", json={"consented": True}
    )
    assert consent_resp.status_code == 200
    assert consent_resp.json()["citizen_consent"] is True

    # B1 — bắt đầu ghi âm (I1 hoàn thiện), chuyển CREATED -> LISTENING
    start_listening_resp = await client.post(
        f"/api/v1/sessions/{session_id}/start-listening"
    )
    assert start_listening_resp.status_code == 200
    assert start_listening_resp.json()["state"] == "LISTENING"

    session_repo = SessionRepository(db_session)

    # B3 — chọn thủ tục (J2), chuyển LISTENING -> PROCEDURE_SELECTED
    procedure_resp = await client.post(
        f"/api/v1/sessions/{session_id}/procedure", json={"code": "dang_ky_khai_sinh"}
    )
    assert procedure_resp.status_code == 200
    assert procedure_resp.json()["state"] == "PROCEDURE_SELECTED"

    # Trạng thái đầy đủ (J2) — mọi field_state đã khởi tạo rỗng theo catalog
    state_resp = await client.get(f"/api/v1/sessions/{session_id}")
    assert state_resp.status_code == 200
    field_names = {fs["field_name"] for fs in state_resp.json()["field_states"]}
    assert "ho_ten_nguoi_duoc_khai_sinh" in field_names

    # B3 — trích xuất (J4); PROCEDURE_SELECTED -> EXTRACTING -> SUGGESTED tự
    # động qua ExtractionService (L). Không cần lượt thoại thật nào — provider
    # mock trả fields rỗng, chỉ cần xác nhận đúng chuyển trạng thái.
    extract_resp = await client.post(
        f"/api/v1/sessions/{session_id}/extract", json={"include_turns": []}
    )
    assert extract_resp.status_code == 200

    session = await session_repo.get(uuid.UUID(session_id))
    assert session.state == "SUGGESTED"

    # B4 — cán bộ mở xem gợi ý (J2 hoàn thiện), chuyển SUGGESTED -> REVIEWING
    open_review_resp = await client.post(f"/api/v1/sessions/{session_id}/open-review")
    assert open_review_resp.status_code == 200
    assert open_review_resp.json()["state"] == "REVIEWING"

    # B5 — cán bộ xác nhận từng trường bắt buộc (J5), tự chuyển FIELDS_CONFIRMED
    catalog_fields = {
        "ho_ten_nguoi_duoc_khai_sinh": "Nguyễn Văn A",
        "ngay_sinh": "2026-01-05",
        "gioi_tinh": "Nam",
        "noi_sinh": "Phường Yên Sở",
        "ho_ten_me": "Trần Thị B",
        "so_cccd_nguoi_yeu_cau": "012345678901",
        "so_dien_thoai": "0912345678",
        "dia_chi_thuong_tru": "Số 1, Yên Sở, Hà Nội",
    }
    for field_name, value in catalog_fields.items():
        confirm_resp = await client.post(
            f"/api/v1/sessions/{session_id}/fields/{field_name}/confirm",
            json={"value": value, "staff_name": "Cán bộ A"},
        )
        assert confirm_resp.status_code == 200, confirm_resp.json()

    session = await session_repo.get(uuid.UUID(session_id))
    assert session.state == "FIELDS_CONFIRMED"

    # B6 — đọc lại (J6), chuyển FIELDS_CONFIRMED -> READBACK
    readback_resp = await client.post(f"/api/v1/sessions/{session_id}/readback")
    assert readback_resp.status_code == 200
    readback_body = readback_resp.json()
    assert readback_body["readback_round"] == 1
    assert "Nguyễn Văn A" in readback_body["text"]

    audio_resp = await client.get(f"/api/v1/sessions/{session_id}/readback/audio")
    if readback_body["audio_available"]:
        assert audio_resp.status_code == 200

    # Người dân xác nhận đúng (J6), chuyển READBACK -> CITIZEN_CONFIRMED
    citizen_confirm_resp = await client.post(
        f"/api/v1/sessions/{session_id}/citizen-confirm",
        json={
            "confirmed": True,
            "readback_text": readback_body["text"],
            "staff_name": "Cán bộ A",
        },
    )
    assert citizen_confirm_resp.status_code == 200
    assert citizen_confirm_resp.json()["confirmed"] is True

    session = await session_repo.get(uuid.UUID(session_id))
    assert session.state == "CITIZEN_CONFIRMED"

    # B7 — hoàn tất phiên với mã hồ sơ (J2), chuyển CITIZEN_CONFIRMED -> COMPLETED
    complete_resp = await client.post(
        f"/api/v1/sessions/{session_id}/complete", json={"dossier_code": "HS-2026-001"}
    )
    assert complete_resp.status_code == 200
    completed_body = complete_resp.json()
    assert completed_body["state"] == "COMPLETED"
    assert completed_body["dossier_code"] == "HS-2026-001"

    # Gọi lại complete lần nữa (đã COMPLETED) phải bị chặn bởi state machine
    repeat_resp = await client.post(
        f"/api/v1/sessions/{session_id}/complete", json={"dossier_code": "HS-2026-001"}
    )
    assert repeat_resp.status_code == 409
    assert repeat_resp.json()["error"]["code"] == "INVALID_TRANSITION"


async def test_flag_turn_marks_flagged_by_staff(client: AsyncClient, db_session) -> None:
    """Smoke test cho `POST /turns/{id}/flag` (O2 — bổ sung khi build frontend,
    `VoiceService.flag_transcript()` đã có từ I4 nhưng thiếu router endpoint)."""
    create_resp = await client.post("/api/v1/sessions", json={"staff_name": "Cán bộ A"})
    session_id = create_resp.json()["id"]

    turn = VoiceTurn(session_id=uuid.UUID(session_id), turn_number=1, raw_transcript="abc")
    await VoiceTurnRepository(db_session).add(turn)
    await db_session.commit()

    flag_resp = await client.post(
        f"/api/v1/sessions/{session_id}/turns/{turn.id}/flag",
        json={"staff_name": "Cán bộ A"},
    )
    assert flag_resp.status_code == 200
    assert flag_resp.json()["flagged_by_staff"] is True


async def test_get_fields_reflects_confirmed_values(client: AsyncClient, db_session) -> None:
    """Smoke test riêng cho J5's `GET /fields` — không lặp lại luồng đầy đủ ở trên."""
    create_resp = await client.post("/api/v1/sessions", json={"staff_name": "Cán bộ A"})
    session_id = create_resp.json()["id"]

    field_repo = FieldStateRepository(db_session)
    await field_repo.upsert(
        uuid.UUID(session_id), "so_dien_thoai", suggested_value="912"  # sai định dạng
    )
    session_repo = SessionRepository(db_session)
    session = await session_repo.get(uuid.UUID(session_id))
    session.procedure_code = "dang_ky_khai_sinh"
    await session_repo.update(session)
    await db_session.commit()

    response = await client.get(f"/api/v1/sessions/{session_id}/fields")
    assert response.status_code == 200
    phone_field = next(
        f for f in response.json() if f["field"]["field_name"] == "so_dien_thoai"
    )
    assert any(not r["valid"] for r in phone_field["validation_results"])
