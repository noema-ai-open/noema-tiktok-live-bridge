import sys
import types

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
async def test_edge_tts_plays_assembled_mp3_directly(monkeypatch) -> None:
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
    played = {}

    async def fake_play(audio, content_type):
        played.update(audio=audio, content_type=content_type)

    monkeypatch.setattr(engine, "_play", fake_play)
    await engine.speak("Hallo", "de-DE-KatjaNeural", 0, 100, None)

    assert played["audio"] == b"mp3-part-1mp3-part-2"
    assert played["content_type"] == "audio/mpeg"


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


@pytest.mark.asyncio
async def test_fetch_all_voices_sorts_german_first(monkeypatch) -> None:
    from app.tts import edge as edge_module

    edge_module._voice_cache = None
    module = types.ModuleType("edge_tts")

    async def list_voices():
        return [
            {"ShortName": "en-US-GuyNeural", "Locale": "en-US", "FriendlyName": "Guy"},
            {"ShortName": "de-DE-KatjaNeural", "Locale": "de-DE", "FriendlyName": "Katja"},
        ]

    module.list_voices = list_voices
    monkeypatch.setitem(sys.modules, "edge_tts", module)

    voices = await edge_module.fetch_all_voices()
    assert voices[0]["id"] == "de-DE-KatjaNeural"
    assert voices[1]["id"] == "en-US-GuyNeural"
    edge_module._voice_cache = None


@pytest.mark.asyncio
async def test_fetch_all_voices_falls_back_on_error(monkeypatch) -> None:
    from app.tts import edge as edge_module

    edge_module._voice_cache = None
    module = types.ModuleType("edge_tts")

    async def list_voices():
        raise RuntimeError("no network")

    module.list_voices = list_voices
    monkeypatch.setitem(sys.modules, "edge_tts", module)

    voices = await edge_module.fetch_all_voices()
    assert voices == [{"id": v, "name": v} for v in edge_module.KNOWN_VOICES]
    edge_module._voice_cache = None
