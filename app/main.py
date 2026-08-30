"""Trợ lý giọng nói AI — MVP siêu gọn.

Một WebSocket proxy duy nhất: browser gửi audio thô (PCM 16-bit) lên đây,
server chuyển tiếp vào Gemini Live API (giữ API key an toàn phía server),
rồi chuyển audio Gemini trả lời ngược lại cho browser phát ra loa.
"""

import asyncio
import base64
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

load_dotenv()

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.0-flash-live-001"

app = FastAPI()
client = genai.Client(api_key=GEMINI_API_KEY)

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói thân thiện, trả lời bằng tiếng Việt, "
        "ngắn gọn, tự nhiên như đang trò chuyện trực tiếp."
    ),
)


@app.websocket("/ws")
async def voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()

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
            """Nhận audio trả lời từ Gemini, gửi ra browser để phát."""
            async for chunk in session.receive():
                if chunk.data:
                    await websocket.send_json(
                        {"type": "audio", "data": base64.b64encode(chunk.data).decode()}
                    )
                if chunk.server_content and chunk.server_content.turn_complete:
                    await websocket.send_json({"type": "turn_complete"})

        try:
            await asyncio.gather(from_browser_to_gemini(), from_gemini_to_browser())
        except WebSocketDisconnect:
            pass


app.mount("/", StaticFiles(directory="static", html=True), name="static")
