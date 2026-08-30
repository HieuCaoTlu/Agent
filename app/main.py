"""Trợ lý giọng nói AI — MVP siêu gọn.

Một WebSocket proxy duy nhất: browser gửi audio thô (PCM 16-bit) lên đây,
server chuyển tiếp vào Gemini Live API (giữ API key an toàn phía server),
rồi chuyển audio Gemini trả lời ngược lại cho browser phát ra loa.
"""

import asyncio
import base64
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

import build_index
from app.conversation_log import ConversationLogger
from app.rag import get_routing_index, reload_index

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.5-flash-native-audio-latest"

app = FastAPI()
client = genai.Client(api_key=GEMINI_API_KEY)

# RAG/tool-calling đã được thử (xem app/rag.py, build_index.py, còn giữ
# nguyên cho trang quản lý data/manage.html) nhưng gây hồi quy chất lượng
# trả lời với model audio-native: query tool để trống, Gemini bỏ qua tool ở
# nhiều lượt, instruction dài làm model kém ổn định hơn (xem data/logs/ và
# lịch sử trao đổi). Theo yêu cầu người dùng, quay lại xử lý nguyên thủy —
# Gemini tự trả lời hoàn toàn tự nhiên, không tool, không ràng buộc RAG.
LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói thân thiện, trả lời bằng tiếng Việt, "
        "ngắn gọn, tự nhiên như đang trò chuyện trực tiếp."
    ),
    # Bật transcript văn bản song song với audio — để hiển thị hội thoại
    # dạng chat trên giao diện (người dùng nói gì, AI trả lời gì).
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    # Nới độ nhạy phát hiện giọng nói (VAD) — mặc định dễ bỏ sót giọng nhỏ,
    # nói từ xa micro, hoặc người phát âm không rõ/ngọng vì coi đó là im
    # lặng/tạp âm. LOW sensitivity ở đây nghĩa là "khó bị thuyết phục là im
    # lặng" tức DỄ nhận là có người đang nói hơn — đánh đổi lại là dễ bắt
    # nhầm tạp âm nền hơn một chút, chấp nhận được để ưu tiên không bỏ sót.
    realtime_input_config=types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
            # Giữ lại nhiều audio trước điểm bắt đầu được phát hiện, để
            # không cắt mất âm tiết đầu (người nói chậm/ngọng thường vào
            # câu chậm, dễ bị cắt mất từ đầu nếu padding quá ngắn).
            prefix_padding_ms=300,
            # Chờ lâu hơn trước khi coi là hết lượt nói — người phát âm
            # không rõ/ngọng thường nói chậm, ngắt quãng giữa câu nhiều hơn.
            silence_duration_ms=800,
        )
    ),
)


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    log = ConversationLogger()

    async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as session:

        async def from_browser_to_gemini() -> None:
            """Nhận audio micro (base64 PCM) từ browser, gửi vào Gemini."""
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "audio":
                    pcm_bytes = base64.b64decode(message["data"])
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                    )
                elif message.get("type") == "stop":
                    return

        async def from_gemini_to_browser() -> None:
            """Nhận audio trả lời từ Gemini, gửi ra browser để phát.

            `session.receive()` chỉ trả stream của MỘT lượt phản hồi — hết lượt
            (turn_complete) thì generator tự kết thúc. Phải gọi lại trong vòng
            lặp `while True` để tiếp tục nhận các lượt kế tiếp; nếu không, hàm
            này return sau câu đầu tiên, kéo theo `asyncio.gather` kết thúc và
            đóng cả phiên Gemini — đúng lỗi khiến AI chỉ trả lời được 1 câu.
            """
            # Gom transcript theo lượt để ghi log 1 dòng duy nhất mỗi câu
            # (của người dùng lẫn AI), thay vì một dòng cho mỗi mẩu nhỏ
            # Gemini gửi dần. user_speaking_end (VAD) không dùng làm mốc
            # flush được vì Gemini vẫn có thể gửi thêm mẩu transcript sau đó
            # (giọng ngắt quãng, chưa hết câu thật) — mốc đáng tin duy nhất
            # là turn_complete/interrupted, khi Gemini coi như đã nhận đủ.
            user_buffer = ""
            ai_buffer = ""
            while True:
                async for chunk in session.receive():
                    if chunk.voice_activity:
                        activity = chunk.voice_activity.voice_activity_type
                        if activity == types.VoiceActivityType.ACTIVITY_START:
                            await websocket.send_json({"type": "user_speaking_start"})
                        elif activity == types.VoiceActivityType.ACTIVITY_END:
                            await websocket.send_json({"type": "user_speaking_end"})
                    if chunk.data:
                        await websocket.send_json(
                            {"type": "audio", "data": base64.b64encode(chunk.data).decode()}
                        )
                    content = chunk.server_content
                    if content and content.input_transcription and content.input_transcription.text:
                        text = content.input_transcription.text
                        user_buffer += text
                        await websocket.send_json({"type": "user_transcript", "text": text})
                    if content and content.output_transcription and content.output_transcription.text:
                        text = content.output_transcription.text
                        ai_buffer += text
                        await websocket.send_json({"type": "ai_transcript", "text": text})
                    if content and content.interrupted:
                        await websocket.send_json({"type": "interrupted"})
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            ai_buffer = ""
                    if content and content.turn_complete:
                        await websocket.send_json({"type": "turn_complete"})
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            ai_buffer = ""

        try:
            await asyncio.gather(from_browser_to_gemini(), from_gemini_to_browser())
        except WebSocketDisconnect:
            pass
        finally:
            log.session_end()


@app.get("/procedures")
async def list_procedures() -> list[dict]:
    """Danh sách thủ tục đang có trong dữ liệu RAG — dùng cho trang quản
    lý (manage.html) hiển thị, đọc thẳng từ index routing đã nạp sẵn trong
    RAM (app/rag.py), không đọc lại đĩa."""
    return get_routing_index()


@app.delete("/procedures/{slug}")
async def delete_procedure(slug: str) -> dict:
    """Xóa một thủ tục khỏi dữ liệu RAG: xóa PDF gốc, file sidecar URL (nếu
    có) và file chi tiết data/procedures/<slug>.json, rồi build lại index
    và nạp lại vào RAM — không cần restart server."""
    entry = next((e for e in get_routing_index() if e["slug"] == slug), None)
    if entry is None:
        return {"ok": False, "error": "Không tìm thấy thủ tục cần xóa."}

    pdf_path = Path("data/pdfs") / entry["source_file"]
    url_path = pdf_path.with_suffix(pdf_path.suffix + ".url.txt")
    detail_path = Path("data/procedures") / f"{slug}.json"

    for path in (pdf_path, url_path, detail_path):
        if path.exists():
            path.unlink()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    build_index.build()
    reload_index()

    return {"ok": True}


@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...), source_url: str = Form(default="")
) -> dict:
    """Nhận PDF "Chi tiết thủ tục hành chính", lưu vào data/pdfs/, build lại
    index RAG ngay (đọc/parse chỉ tốn thời gian một lần lúc upload, không
    phải lúc server khởi động), rồi nạp lại vào RAM — không cần restart
    server để dùng được dữ liệu mới.

    `source_url` (tùy chọn): link trang thủ tục trên dichvucong.gov.vn
    tương ứng với PDF này — ghi ra file sidecar '<tên_pdf>.url.txt' để
    build_index.build() đọc lại và lưu vào cả routing (data/index.json)
    lẫn chi tiết thủ tục, phục vụ tra cứu/hiển thị lại nguồn sau này.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return {"ok": False, "error": "Chỉ chấp nhận file .pdf"}

    dest_dir = Path("data/pdfs")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename
    with dest_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    source_url = source_url.strip()
    url_path = dest_path.with_suffix(dest_path.suffix + ".url.txt")
    if source_url:
        url_path.write_text(source_url, encoding="utf-8")
    elif url_path.exists():
        url_path.unlink()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    build_index.build()
    reload_index()

    return {"ok": True, "saved_as": str(dest_path), "source_url": source_url or None}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
