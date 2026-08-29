from app.tts.mock_provider import MockTTSProvider


async def test_synthesize_returns_wav_bytes() -> None:
    provider = MockTTSProvider()
    result = await provider.synthesize("Xin chào")
    assert result.audio_bytes.startswith(b"RIFF")
    assert result.audio_format == "wav"
    assert result.provider == "mock"


async def test_health_check_always_true() -> None:
    provider = MockTTSProvider()
    assert await provider.health_check() is True
