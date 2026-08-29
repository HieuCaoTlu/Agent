from app.stt.mock_provider import MockSTTProvider


async def _fake_audio_stream():
    yield b"\x00\x01"
    yield b"\x02\x03"


async def test_transcribe_stream_yields_scripted_chunks() -> None:
    provider = MockSTTProvider(script=["câu một", "câu hai"])
    chunks = [chunk async for chunk in provider.transcribe_stream(_fake_audio_stream())]

    assert [c.text for c in chunks] == ["câu một", "câu hai"]
    assert all(c.is_final for c in chunks)
    assert all(c.provider == "mock" for c in chunks)


async def test_transcribe_stream_default_script() -> None:
    provider = MockSTTProvider()
    chunks = [chunk async for chunk in provider.transcribe_stream(_fake_audio_stream())]
    assert len(chunks) == 1


async def test_transcribe_file_returns_first_script_line() -> None:
    provider = MockSTTProvider(script=["nội dung file"])
    chunk = await provider.transcribe_file(b"fake audio bytes")
    assert chunk.text == "nội dung file"
    assert chunk.is_final is True


async def test_health_check_always_true() -> None:
    provider = MockSTTProvider()
    assert await provider.health_check() is True


def test_transcript_chunk_has_no_confidence_field() -> None:
    """Xác nhận quyết định G: không dùng ngưỡng confidence cho STT."""
    from app.stt.base import TranscriptChunk

    fields = {f for f in TranscriptChunk.__dataclass_fields__}
    assert "confidence" not in fields
