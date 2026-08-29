"""`BlazeSTTProvider` — Mục G2/G3 của Checklist.

Bọc cả hai giao thức Blaze (WebSocket streaming G2, HTTP file G3) sau cùng
một interface `STTProvider` — tầng gọi không biết chi tiết giao thức.
"""

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import websockets

from app.stt.base import STTProvider, TranscriptChunk
from app.stt.exceptions import STTAPIError, STTConnectionError

_MAX_FILE_RETRIES = 2


class BlazeSTTProvider(STTProvider):
    def __init__(
        self,
        api_token: str,
        base_url: str,
        ws_base_url: str,
        stream_model: str,
        async_model: str,
        language: str = "vi",
        topic: str = "",
        context: str = "",
        bias_keywords: list[str] | None = None,
    ) -> None:
        self._api_token = api_token
        self._base_url = base_url.rstrip("/")
        self._ws_base_url = ws_base_url.rstrip("/")
        self._stream_model = stream_model
        self._async_model = async_model
        self._language = language
        self._topic = topic
        self._context = context
        self._bias_keywords = bias_keywords or []

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        """Mở WS `{BLAZE_WS_BASE_URL}/v1/stt/realtime`, gửi audio, nhận transcript (G2).

        Không nuốt lỗi kết nối giữa chừng: mọi transcript `final` đã nhận được
        trước khi mất kết nối vẫn đã được `yield` ra ngoài (tầng gọi giữ được
        toàn bộ transcript nhận trước đó — không mất dữ liệu), lỗi chỉ ném ra
        sau khi ngừng nhận thêm được nữa.
        """
        uri = f"{self._ws_base_url}/v1/stt/realtime"
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "token": self._api_token,
                            "language": self._language,
                            "model": self._stream_model,
                            "topic": self._topic,
                            "context": self._context,
                            "bias_keywords": self._bias_keywords,
                        }
                    )
                )
                ready_raw = await ws.recv()
                ready = json.loads(ready_raw)
                if ready.get("type") != "ready":
                    raise STTAPIError(f"Blaze STT không trả 'ready', nhận: {ready_raw!r}")

                async for chunk in self._pump_audio_and_receive(ws, audio_stream):
                    yield chunk
        except websockets.exceptions.WebSocketException as exc:
            raise STTConnectionError(str(exc)) from exc

    async def _pump_audio_and_receive(
        self, ws: websockets.ClientConnection, audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptChunk]:
        """Gửi audio và nhận transcript đồng thời (2 task song song).

        Gửi tuần tự theo `audio_stream` là việc của task riêng — không chờ
        request/response theo cặp, vì Blaze có thể gửi nhiều message `partial`
        cho một đoạn audio, hoặc gộp nhiều đoạn audio thành một `final`.
        """
        send_task = asyncio.create_task(self._send_all_audio(ws, audio_stream))
        try:
            async for raw in ws:
                chunk = self._parse_message(raw)
                if chunk is not None:
                    yield chunk
                if send_task.done() and chunk is not None and chunk.is_final:
                    break
        finally:
            if not send_task.done():
                send_task.cancel()
            await asyncio.gather(send_task, return_exceptions=True)

    @staticmethod
    async def _send_all_audio(
        ws: websockets.ClientConnection, audio_stream: AsyncIterator[bytes]
    ) -> None:
        async for audio_bytes in audio_stream:
            await ws.send(audio_bytes)

    def _parse_message(self, raw: str | bytes) -> TranscriptChunk | None:
        data = json.loads(raw)
        msg_type = data.get("type")
        if msg_type not in ("partial", "final"):
            return None
        return TranscriptChunk(
            text=data.get("text", ""), is_final=(msg_type == "final"), provider="blaze"
        )

    async def transcribe_file(self, audio_bytes: bytes) -> TranscriptChunk:
        """`POST {BLAZE_BASE_URL}/v1/stt/execute?model=stt-async-1.5` (G3).

        Retry có giới hạn (`_MAX_FILE_RETRIES`) chỉ cho lỗi mạng tạm thời —
        không retry vô hạn vì audio đã hữu hạn, thời gian thực đã trôi qua (G4).
        """
        url = f"{self._base_url}/v1/stt/execute"
        last_error: Exception | None = None
        async with httpx.AsyncClient() as client:
            for _attempt in range(_MAX_FILE_RETRIES + 1):
                try:
                    response = await client.post(
                        url,
                        params={"model": self._async_model},
                        headers={"Authorization": f"Bearer {self._api_token}"},
                        files={"audio_file": audio_bytes},
                    )
                    response.raise_for_status()
                    data = response.json()
                    return TranscriptChunk(
                        text=data.get("text", ""), is_final=True, provider="blaze"
                    )
                except httpx.TransportError as exc:
                    last_error = exc
                    continue
                except httpx.HTTPStatusError as exc:
                    raise STTAPIError(str(exc)) from exc
        assert last_error is not None
        raise STTConnectionError(str(last_error))

    async def health_check(self) -> bool:
        url = f"{self._base_url}/v1/stt/execute"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(
                    url, headers={"Authorization": f"Bearer {self._api_token}"}, timeout=5.0
                )
        except httpx.TransportError:
            return False
        return response.status_code < 500
