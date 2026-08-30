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
from app import dom_ai
from app import submit_flow
from app.conversation_log import ConversationLogger
from app.extension_bridge import ExtensionCommandError, ExtensionNotConnected, extension_manager
from app.rag import get_routing_index, reload_index

TEXT_MODEL = "gemini-2.5-flash"

SUBMIT_PROVINCE = "Thành phố Hà Nội"
SUBMIT_WARD = "Yên Sở"

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.5-flash-native-audio-latest"

app = FastAPI()
client = genai.Client(api_key=GEMINI_API_KEY)

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói thân thiện, trả lời bằng tiếng Việt, "
        "ngắn gọn, tự nhiên như đang trò chuyện trực tiếp."
    ),
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    realtime_input_config=types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(
            start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
            end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
            prefix_padding_ms=300,
            silence_duration_ms=800,
        )
    ),
)


async def _extract_procedure_name(history: list[tuple[str, str]]) -> str | None:
    if not history:
        return None

    transcript = "\n".join(f"{who}: {text}" for who, text in history)
    prompt = (
        "Đây là đoạn hội thoại giữa người dùng và trợ lý giọng nói về thủ "
        "tục hành chính:\n\n"
        f"{transcript}\n\n"
        "Người dùng vừa yêu cầu nộp hồ sơ. Hãy trả về CHÍNH XÁC tên thủ tục "
        "hành chính đang được nhắc tới (ví dụ: \"Đăng ký khai sinh\"), "
        "không kèm giải thích, không kèm dấu ngoặc kép. Nếu không xác định "
        "được thủ tục nào, trả về đúng chữ KHONG_RO."
    )

    response = await client.aio.models.generate_content(model=TEXT_MODEL, contents=prompt)
    name = (response.text or "").strip()
    if not name or name == "KHONG_RO":
        return None
    return name


async def _handle_submit_procedure(
    websocket: WebSocket, history: list[tuple[str, str]], log: ConversationLogger
) -> None:
    try:
        procedure_name = await _extract_procedure_name(history)
        log.submit_action("extract_procedure_name", {"procedure_name": procedure_name})
        if not procedure_name:
            await websocket.send_json(
                {"type": "submit_procedure_error", "message": "Không xác định được thủ tục cần nộp."}
            )
            return

        await websocket.send_json({"type": "submit_procedure_status", "message": f"Đang tìm kiếm: {procedure_name}..."})
        search_url = submit_flow.build_search_url(procedure_name)
        results_page = await extension_manager.send_command("open_url_and_scan", {"url": search_url})
        log.submit_action("open_search_url", {"url": search_url})

        await websocket.send_json({"type": "submit_procedure_status", "message": "Đang chọn đúng thủ tục..."})
        pick = await dom_ai.pick_search_result(results_page["html"], procedure_name)
        log.submit_action("pick_search_result", pick)
        if not pick.get("result_selector"):
            log.submit_action("pick_search_result_retry")
            await asyncio.sleep(2.0)
            results_page = await extension_manager.send_command("scan_current_page", {})
            pick = await dom_ai.pick_search_result(results_page["html"], procedure_name)
            log.submit_action("pick_search_result_retry_result", pick)
        if not pick.get("result_selector"):
            log.submit_error("pick_search_result", "result_selector rỗng — Gemini không chọn được kết quả nào.")
            await websocket.send_json(
                {"type": "submit_procedure_error", "message": "Không tìm thấy thủ tục trên dichvucong.gov.vn."}
            )
            return
        await extension_manager.send_command("click_selector", {"selector": pick["result_selector"]})
        log.submit_action("click_search_result_done", {"selector": pick["result_selector"]})

        await websocket.send_json(
            {"type": "submit_procedure_status", "message": "Đang điền tỉnh/phường..."}
        )
        await asyncio.sleep(1.5)
        flow_result = await extension_manager.send_command(
            "run_fixed_submit_flow", {"province": SUBMIT_PROVINCE, "ward": SUBMIT_WARD}
        )
        log.submit_action("run_fixed_submit_flow_done", flow_result)

        await websocket.send_json(
            {
                "type": "submit_procedure_done",
                "message": "Đã điền sẵn tỉnh/phường. Vui lòng tự bấm \"Nộp trực tuyến\" và đăng nhập để hoàn tất.",
            }
        )
    except ExtensionNotConnected:
        log.submit_error("extension_connection", "Chưa cài hoặc chưa kết nối tiện ích mở rộng trình duyệt.")
        await websocket.send_json(
            {
                "type": "submit_procedure_error",
                "message": "Chưa cài hoặc chưa kết nối tiện ích mở rộng trình duyệt.",
            }
        )
    except TimeoutError:
        log.submit_error("timeout", "Tiện ích mở rộng không phản hồi kịp thời (quá 20s).")
        await websocket.send_json(
            {"type": "submit_procedure_error", "message": "Tiện ích mở rộng không phản hồi kịp thời."}
        )
    except ExtensionCommandError as exc:
        log.submit_error("extension_command", str(exc))
        await websocket.send_json(
            {"type": "submit_procedure_error", "message": f"Lỗi thao tác trên trang: {exc}"}
        )
    except Exception as exc:
        log.submit_error("unexpected", repr(exc))
        await websocket.send_json(
            {"type": "submit_procedure_error", "message": f"Lỗi không xác định: {exc}"}
        )


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    log = ConversationLogger()
    history: list[tuple[str, str]] = []

    async with client.aio.live.connect(model=MODEL, config=LIVE_CONFIG) as session:

        async def from_browser_to_gemini() -> None:
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "audio":
                    pcm_bytes = base64.b64decode(message["data"])
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                    )
                elif message.get("type") == "submit_procedure":
                    asyncio.create_task(_handle_submit_procedure(websocket, history, log))
                elif message.get("type") == "stop":
                    return

        async def from_gemini_to_browser() -> None:
            user_buffer = ""
            ai_buffer = ""
            submit_hint_shown = False
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
                    if not submit_hint_shown and ("nộp" in user_buffer.lower() or "nộp" in ai_buffer.lower()):
                        submit_hint_shown = True
                        await websocket.send_json({"type": "show_submit_button"})
                    if content and content.interrupted:
                        await websocket.send_json({"type": "interrupted"})
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            history.append(("Người dùng", user_buffer))
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            history.append(("Trợ lý", ai_buffer))
                            ai_buffer = ""
                    if content and content.turn_complete:
                        await websocket.send_json({"type": "turn_complete"})
                        submit_hint_shown = False
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            history.append(("Người dùng", user_buffer))
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            history.append(("Trợ lý", ai_buffer))
                            ai_buffer = ""

        try:
            await asyncio.gather(from_browser_to_gemini(), from_gemini_to_browser())
        except WebSocketDisconnect:
            pass
        finally:
            log.session_end()


@app.websocket("/extension")
async def extension_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await extension_manager.register(websocket)
    try:
        while True:
            message = await websocket.receive_json()
            await extension_manager.handle_response(message)
    except WebSocketDisconnect:
        pass
    finally:
        extension_manager.unregister(websocket)


@app.get("/procedures")
async def list_procedures() -> list[dict]:
    return get_routing_index()


@app.delete("/procedures/{slug}")
async def delete_procedure(slug: str) -> dict:
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
