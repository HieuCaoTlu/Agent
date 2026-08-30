"""Test tích hợp cho router K — WebSocket giọng nói.

Phạm vi hẹp có chủ đích (cùng tinh thần `test_e2e_flow.py`, J): một luồng
duy nhất start → audio → stop, xác nhận đúng giao thức message (Plan.MD
9.2) và đúng thứ tự gọi `VoiceService` (I4) — không lặp lại logic đã test
kỹ ở `tests/services/test_voice_service.py`.
"""

import base64

from starlette.testclient import TestClient

from app.api.deps import get_stt_provider
from app.db.database import get_db
from app.db.redis_client import get_redis
from app.main import app
from app.stt.mock_provider import MockSTTProvider


def test_voice_websocket_full_turn(db_session, redis_mock) -> None:
    async def _override_get_db():
        yield db_session

    async def _override_get_redis():
        yield redis_mock

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis
    app.dependency_overrides[get_stt_provider] = lambda: MockSTTProvider(
        ["xin chào tôi muốn đăng ký khai sinh"]
    )

    try:
        with TestClient(app) as test_client:
            # Tạo phiên trước qua HTTP thường (J2) — WebSocket cần session_id tồn tại.
            create_resp = test_client.post("/api/v1/sessions", json={"staff_name": "Cán bộ A"})
            assert create_resp.status_code == 201
            session_id = create_resp.json()["id"]

            with test_client.websocket_connect(f"/api/v1/sessions/{session_id}/voice") as ws:
                ws.send_json({"type": "start"})

                ws.send_json(
                    {"type": "audio", "seq": 1, "data": base64.b64encode(b"fake-pcm").decode()}
                )

                # MockSTTProvider chỉ phát "final" khi audio_stream đóng — tức
                # khi 'stop' gọi finalize_turn() (đẩy None vào queue audio).
                ws.send_json({"type": "stop"})

                messages = [ws.receive_json() for _ in range(2)]
                by_type = {m["type"]: m for m in messages}

                assert by_type["final"]["text"] == "xin chào tôi muốn đăng ký khai sinh"
                assert by_type["final"]["turn_number"] == 1
                assert by_type["audio_deleted"]["turn_id"]
    finally:
        app.dependency_overrides.clear()
