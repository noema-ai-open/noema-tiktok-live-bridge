import asyncio
import sys
from types import SimpleNamespace

import httpx
import pytest

from app.config import AppConfig
from app.main import create_app
from app.tts.edge import (
    EdgeTTSEngine,
    KITT_STYLE_BASE_VOICE,
    KITT_STYLE_PITCH,
    KITT_STYLE_RATE,
    KITT_STYLE_VOICE_ID,
)


async def wait_until(predicate, timeout: float = 1.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.005)


@pytest.mark.asyncio
async def test_kitt_style_uses_regular_edge_voice_with_prosody(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCommunicate:
        def __init__(self, text: str, voice: str, **prosody: str) -> None:
            captured.update(text=text, voice=voice, prosody=prosody)

        async def stream(self):
            yield {"type": "audio", "data": b"fake-mp3"}

    monkeypatch.setitem(sys.modules, "edge_tts", SimpleNamespace(Communicate=FakeCommunicate))
    engine = EdgeTTSEngine()

    async def fake_play(audio: bytes, content_type: str) -> None:
        captured.update(audio=audio, content_type=content_type)

    monkeypatch.setattr(engine, "_play", fake_play)

    await engine.speak("System bereit", KITT_STYLE_VOICE_ID, 0, 100, None)

    assert captured == {
        "text": "System bereit",
        "voice": KITT_STYLE_BASE_VOICE,
        "prosody": {"rate": KITT_STYLE_RATE, "pitch": KITT_STYLE_PITCH},
        "audio": b"fake-mp3",
        "content_type": "audio/mpeg",
    }


@pytest.mark.asyncio
async def test_tts_state_reports_actual_playback(tmp_path) -> None:
    app = create_app(
        AppConfig(
            mode="fallback",
            database_path=tmp_path / "kitt-state.sqlite3",
            tts_engine="dummy",
        )
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            idle = await client.get("/tts/state")
            assert idle.status_code == 200
            assert idle.json() == {"speaking": False}

            engine = app.state.bridge.tts_engine
            engine.duration = None
            queued = await client.post("/tts/test", json={"text": "KITT spricht"})
            assert queued.status_code == 202
            await wait_until(
                lambda: app.state.bridge.tts_worker._current_speech is not None
            )

            speaking = await client.get("/tts/state")
            assert speaking.json() == {"speaking": True}

            await client.post("/tts/stop")
            await wait_until(
                lambda: app.state.bridge.tts_worker._current_speech is None
            )
            stopped = await client.get("/tts/state")
            assert stopped.json() == {"speaking": False}
