import asyncio
import base64
import os

from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.conversation_log import ConversationLogger

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_VOICE_MODEL = os.environ.get("GEMINI_VOICE_MODEL", "gemini-2.5-flash-native-audio-latest")

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói thân thiện, trả lời bằng tiếng Việt, "
        "ngắn gọn, tự nhiên như đang trò chuyện trực tiếp."
    ),
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    realtime_input_config=types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
    ),
)

async def run_voice_session(websocket: WebSocket, log: ConversationLogger, history: list[tuple[str, str]], on_submit_procedure) -> None:
    async with _gemini_client.aio.live.connect(model=GEMINI_VOICE_MODEL, config=LIVE_CONFIG) as session:

        async def from_browser() -> None:
            while True:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                if msg_type == "audio":
                    pcm_bytes = base64.b64decode(message["data"])
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                    )
                elif msg_type == "activity_start":
                    await session.send_realtime_input(activity_start=types.ActivityStart())
                elif msg_type == "activity_end":
                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                elif msg_type == "submit_procedure":
                    on_submit_procedure(message.get("procedure_name"))
                elif msg_type == "cancel_submit":
                    cancel_text = "Tôi chưa muốn nộp hồ sơ ngay bây giờ, hãy hỏi tôi cần hỗ trợ gì thêm."
                    log.user_transcript(cancel_text)
                    history.append(("Người dùng", cancel_text))
                    await session.send_client_content(
                        turns=types.Content(role="user", parts=[types.Part(text=cancel_text)]),
                        turn_complete=True,
                    )
                elif msg_type == "stop":
                    return

        async def to_browser() -> None:
            user_buffer = ""
            ai_buffer = ""
            while True:
                async for chunk in session.receive():
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
                            history.append(("Người dùng", user_buffer))
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            history.append(("Trợ lý", ai_buffer))
                            ai_buffer = ""
                    if content and content.turn_complete:
                        if "nộp" in user_buffer.lower() or "nộp" in ai_buffer.lower():
                            await websocket.send_json({"type": "show_submit_button"})
                        await websocket.send_json({"type": "turn_complete"})
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            history.append(("Người dùng", user_buffer))
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            history.append(("Trợ lý", ai_buffer))
                            ai_buffer = ""

        try:
            await asyncio.gather(from_browser(), to_browser())
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
