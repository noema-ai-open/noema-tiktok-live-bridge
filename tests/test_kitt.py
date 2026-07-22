import asyncio
import sys
from pathlib import Path
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
from app.version import __version__


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


@pytest.mark.asyncio
async def test_frontend_uses_versioned_assets_and_disables_cache(tmp_path) -> None:
    app = create_app(
        AppConfig(
            mode="fallback",
            database_path=tmp_path / "frontend-cache.sqlite3",
            tts_engine="dummy",
        )
    )

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

    assert response.status_code == 200
    assert response.headers["cache-control"] == (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    assert f'/app.js?v={__version__}' in response.text
    assert f'/noema-ui.js?v={__version__}' in response.text
    assert f'/kitt-header.css?v={__version__}' in response.text
    assert f'>v{__version__}</span>' in response.text


def test_kitt_frontend_is_slim_strip_without_voicebox_console() -> None:
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    script = (frontend / "noema-ui.js").read_text(encoding="utf-8")
    styles = (frontend / "kitt-header.css").read_text(encoding="utf-8")

    assert 'strip.className = "kitt-strip"' in script
    assert "strip.append(scanner)" in script
    assert "voicebox.remove()" in script
    assert "consoleElement.append(voicebox" not in script
    assert ".kitt-strip" in styles
    assert ".kitt-voicebox" in styles
    assert "display: none !important" in styles
    assert "kitt-strip-scan" in styles
