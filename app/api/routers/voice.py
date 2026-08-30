"""Router K — WebSocket giọng nói (`WS /api/v1/sessions/{id}/voice`).

Giao thức (Mục 9.2 của Plan.MD, dòng 982-997):
  Client → Server: `{"type": "start", ...}`, `{"type": "audio", "seq": N, "data": "<base64>"}`,
  `{"type": "stop"}`.
  Server → Client: `{"type": "partial", "text": ...}`,
  `{"type": "final", "turn_id": ..., "turn_number": ..., "text": ...}`,
  `{"type": "error", "code": ..., "message": ...}`,
  `{"type": "audio_deleted", "turn_id": ...}`.

Kiến trúc: một task nền tiêu thụ `VoiceService.stream_results(turn_id)`
(real-time, I4) và đẩy `partial`/`final` về client song song với vòng lặp
chính nhận message JSON từ client — hai luồng độc lập trên cùng kết nối,
cần thiết vì STT có thể trả kết quả bất kỳ lúc nào, không đồng bộ với nhịp
client gửi chunk.
"""

import asyncio
import base64
import uuid

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.deps import get_voice_service
from app.config import Settings, get_settings
from app.db.database import get_db
from app.services.voice_service import VoiceService, VoiceTurnNotFound
from app.stt.exceptions import STTError

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["voice"])

# Giới hạn kích thước một chunk audio đã giải mã base64 (L2) — 256 KiB đủ cho
# vài trăm ms PCM 16kHz/mono/16-bit, chặn client gửi payload bất thường lớn
# làm tràn buffer Redis/bộ nhớ tiến trình.
_MAX_CHUNK_BYTES = 256 * 1024


async def _send_error(websocket: WebSocket, code: str, message: str) -> None:
    await websocket.send_json({"type": "error", "code": code, "message": message})


@router.websocket("/api/v1/sessions/{session_id}/voice")
async def voice_websocket(
    websocket: WebSocket,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    service: VoiceService = Depends(get_voice_service),
    settings: Settings = Depends(get_settings),
) -> None:
    await websocket.accept()

    turn_id: uuid.UUID | None = None
    turn_number: int | None = None
    forward_task: asyncio.Task[None] | None = None
    recording_deadline: float | None = None

    try:
        while True:
            timeout = (
                max(recording_deadline - asyncio.get_event_loop().time(), 0)
                if recording_deadline is not None
                else None
            )
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
            except TimeoutError:
                # Vượt max_recording_seconds (L2) — tự động chốt lượt hiện tại,
                # không đóng kết nối (cán bộ có thể bấm ghi âm lượt kế tiếp).
                await _finalize_and_cleanup(websocket, service, db, turn_id, forward_task)
                await _send_error(
                    websocket,
                    "RECORDING_TIMEOUT",
                    f"Đã vượt giới hạn {settings.max_recording_seconds}s ghi âm, tự động dừng.",
                )
                turn_id, turn_number, forward_task, recording_deadline = None, None, None, None
                continue

            msg_type = message.get("type")

            if msg_type == "start":
                if turn_id is not None:
                    await _send_error(
                        websocket, "ALREADY_RECORDING", "Lượt ghi âm đang mở, hãy gửi 'stop' trước."
                    )
                    continue
                try:
                    voice_turn = await service.start_recording(session_id)
                    await db.commit()
                except Exception as exc:  # noqa: BLE001 — chuyển mọi lỗi khởi tạo thành message error
                    await _send_error(websocket, "START_FAILED", str(exc))
                    continue
                turn_id = voice_turn.id
                turn_number = voice_turn.turn_number
                recording_deadline = (
                    asyncio.get_event_loop().time() + settings.max_recording_seconds
                )
                forward_task = asyncio.create_task(
                    _forward_results(websocket, service, turn_id, turn_number)
                )

            elif msg_type == "audio":
                if turn_id is None:
                    await _send_error(
                        websocket,
                        "NOT_RECORDING",
                        "Chưa bắt đầu lượt ghi âm, hãy gửi 'start' trước.",
                    )
                    continue
                data = message.get("data", "")
                try:
                    chunk = base64.b64decode(data)
                except Exception:  # noqa: BLE001 — payload base64 không hợp lệ là lỗi của client
                    await _send_error(websocket, "INVALID_AUDIO", "Dữ liệu audio không hợp lệ.")
                    continue
                if len(chunk) > _MAX_CHUNK_BYTES:
                    await _send_error(
                        websocket,
                        "CHUNK_TOO_LARGE",
                        f"Chunk audio vượt giới hạn {_MAX_CHUNK_BYTES} byte.",
                    )
                    continue
                try:
                    await service.process_audio_chunk(turn_id, chunk)
                except STTError as exc:
                    await _send_error(websocket, "STT_UNAVAILABLE", str(exc))

            elif msg_type == "stop":
                if turn_id is None:
                    await _send_error(
                        websocket, "NOT_RECORDING", "Không có lượt ghi âm nào đang mở."
                    )
                    continue
                await _finalize_and_cleanup(websocket, service, db, turn_id, forward_task)
                turn_id, turn_number, forward_task, recording_deadline = None, None, None, None

            else:
                await _send_error(
                    websocket, "UNKNOWN_MESSAGE_TYPE", f"Không hiểu type='{msg_type}'."
                )

    except WebSocketDisconnect:
        # Ngắt kết nối đột ngột (đóng tab, mất mạng) — dọn buffer, ghi audit,
        # không chờ client gửi 'stop' (Checklist K: "xử lý ngắt kết nối đột ngột").
        logger.warning(
            "voice_websocket_disconnected", session_id=str(session_id), turn_id=str(turn_id)
        )
        if turn_id is not None:
            if forward_task is not None:
                forward_task.cancel()
            try:
                await service.delete_audio_buffer(turn_id)
                await db.commit()
            except VoiceTurnNotFound:
                pass


async def _forward_results(
    websocket: WebSocket, service: VoiceService, turn_id: uuid.UUID, turn_number: int
) -> None:
    """Task nền: đẩy `partial`/`final` về client ngay khi STT trả về (I4)."""
    try:
        async for result in service.stream_results(turn_id):
            if websocket.client_state != WebSocketState.CONNECTED:
                return
            if result.is_final:
                await websocket.send_json(
                    {
                        "type": "final",
                        "turn_id": str(turn_id),
                        "turn_number": turn_number,
                        "text": result.text,
                    }
                )
            else:
                await websocket.send_json({"type": "partial", "text": result.text})
    except STTError as exc:
        if websocket.client_state == WebSocketState.CONNECTED:
            await _send_error(websocket, "STT_UNAVAILABLE", str(exc))
    except asyncio.CancelledError:
        pass


async def _finalize_and_cleanup(
    websocket: WebSocket,
    service: VoiceService,
    db: AsyncSession,
    turn_id: uuid.UUID,
    forward_task: asyncio.Task[None] | None,
) -> None:
    """Xử lý message `stop`: đóng luồng audio trước (để STT kịp trả chunk
    `is_final` cuối), rồi mới ghép text và lưu — tránh race condition (xem
    docstring `VoiceService.close_recording_stream()`, I4)."""
    results = await service.close_recording_stream(turn_id)
    final_text = next(
        (r.text for r in reversed(results) if r.is_final), results[-1].text if results else ""
    )

    await service.finalize_turn(turn_id, final_text)
    await db.commit()

    if forward_task is not None:
        try:
            await asyncio.wait_for(forward_task, timeout=5)
        except (TimeoutError, asyncio.CancelledError):
            forward_task.cancel()

    await service.delete_audio_buffer(turn_id)
    await db.commit()

    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_json({"type": "audio_deleted", "turn_id": str(turn_id)})
