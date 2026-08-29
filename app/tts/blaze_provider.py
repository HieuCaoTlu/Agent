"""`BlazeBatchTTS` — Mục H2 của Checklist.

**Chưa xác minh được với API thật** (cần Blaze API token thật để test tích
hợp — chưa có ở thời điểm viết): định dạng response có thể là audio nhị phân
trực tiếp (`Content-Type: audio/*`) hoặc JSON chứa audio dạng base64. Xử lý
cả hai khả năng dựa vào `Content-Type` của response — cần xác nhận lại khi
có token thật để test tích hợp (xem Checklist Mục H2).
"""

import base64

import httpx

from app.tts.base import SynthesisResult, TTSProvider
from app.tts.exceptions import TTSAPIError, TTSConnectionError


class BlazeBatchTTS(TTSProvider):
    def __init__(
        self,
        api_token: str,
        base_url: str,
        model: str,
        speaker_id: str,
        language: str = "vi",
        audio_format: str = "mp3",
        audio_quality: int = 64,
        audio_speed: float = 1.0,
        normalization: str = "basic",
    ) -> None:
        self._api_token = api_token
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._speaker_id = speaker_id
        self._language = language
        self._audio_format = audio_format
        self._audio_quality = audio_quality
        self._audio_speed = audio_speed
        self._normalization = normalization

    async def synthesize(self, text: str) -> SynthesisResult:
        url = f"{self._base_url}/v1/tts"
        body = {
            "query": text,
            "language": self._language,
            "audio_speed": self._audio_speed,
            "audio_quality": self._audio_quality,
            "audio_format": self._audio_format,
            "normalization": self._normalization,
            "speaker_id": self._speaker_id,
            "model": self._model,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {self._api_token}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
        except httpx.TransportError as exc:
            raise TTSConnectionError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise TTSAPIError(str(exc)) from exc

        return self._parse_response(response)

    def _parse_response(self, response: httpx.Response) -> SynthesisResult:
        content_type = response.headers.get("content-type", "")
        if content_type.startswith("audio/"):
            return SynthesisResult(
                audio_bytes=response.content, audio_format=self._audio_format, provider="blaze"
            )

        data = response.json()
        audio_field = data.get("audio") or data.get("audio_base64")
        if audio_field is None:
            raise TTSAPIError(f"Không tìm thấy audio trong response JSON: {data!r}")
        return SynthesisResult(
            audio_bytes=base64.b64decode(audio_field),
            audio_format=self._audio_format,
            provider="blaze",
        )

    async def health_check(self) -> bool:
        url = f"{self._base_url}/v1/tts"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.head(
                    url, headers={"Authorization": f"Bearer {self._api_token}"}, timeout=5.0
                )
        except httpx.TransportError:
            return False
        return response.status_code < 500
