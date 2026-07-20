import io
import sys
import types
import wave

import pytest

from app.tts.base import TTSError
from app.tts.edge import EdgeTTSEngine
from app.config.settings import AppConfig
from app.service import BridgeService


def _fake_edge_module(chunks):
    module = types.ModuleType("edge_tts")

    class Communicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def stream(self):
            for chunk in chunks:
                yield chunk

    module.Communicate = Communicate
    return module


@pytest.mark.asyncio
async def test_edge_tts_decodes_stream_to_wav(monkeypatch) -> None:
    pcm = b"\x00\x01" * 2400
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(24000)
        wav_file.writeframes(pcm)

    monkeypatch.setitem(
        sys.modules,
        "edge_tts",
        _fake_edge_module(
            [
                {"type": "audio", "data": b"mp3-part-1"},
                {"type": "WordBoundary"},
                {"type": "audio", "data": b"mp3-part-2"},
            ]
        ),
    )
    engine = EdgeTTSEngine()
    seen = {}

    def fake_decode(mp3: bytes) -> bytes:
        seen["mp3"] = mp3
        return wav_buffer.getvalue()

    monkeypatch.setattr(EdgeTTSEngine, "_mp3_to_wav", staticmethod(fake_decode))
    played = {}

    async def fake_play(audio, content_type):
        played.update(audio=audio, content_type=content_type)

    monkeypatch.setattr(engine, "_play", fake_play)
    await engine.speak("Hallo", "de-DE-KatjaNeural", 0, 100, None)

    assert seen["mp3"] == b"mp3-part-1mp3-part-2"
    assert played["content_type"] == "audio/wav"
    assert played["audio"][:4] == b"RIFF"


@pytest.mark.asyncio
async def test_edge_tts_raises_on_empty_audio(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "edge_tts", _fake_edge_module([]))
    engine = EdgeTTSEngine()

    with pytest.raises(TTSError):
        await engine.speak("Hallo", None, 0, 100, None)


def test_edge_tts_lists_german_voices() -> None:
    engine = EdgeTTSEngine()
    voices = [voice["id"] for voice in engine.list_voices()]
    assert "de-DE-KatjaNeural" in voices


def test_service_selects_edge_engine_from_config() -> None:
    config = AppConfig(tts_engine="edge")
    engine = BridgeService._build_tts_engine("edge", config)
    assert isinstance(engine, EdgeTTSEngine)
