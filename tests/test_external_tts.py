from typing import Any

import httpx
import pytest

from app.config import AppConfig
from app.service import BridgeService
from app.tts.external import ExternalTTSEngine


@pytest.mark.asyncio
async def test_external_tts_posts_only_required_fields_and_plays_audio(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured["client_kwargs"] = kwargs

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            captured["url"] = url
            captured.update(kwargs)
            return httpx.Response(
                200,
                content=b"RIFFxxxxWAVEaudio",
                headers={"content-type": "audio/wav"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("app.tts.external.httpx.AsyncClient", FakeClient)
    engine = ExternalTTSEngine(
        api_key="secret",
        base_url="https://tts.example/v1/",
        model="voice-model",
    )
    played: dict[str, object] = {}

    async def fake_play(audio: bytes, content_type: str) -> None:
        played.update(audio=audio, content_type=content_type)

    monkeypatch.setattr(engine, "_play", fake_play)

    await engine.speak("Only this text", "coral", 5, 42, "private-device")

    assert captured["url"] == "https://tts.example/v1/audio/speech"
    assert captured["headers"] == {"Authorization": "Bearer secret"}
    assert captured["json"] == {
        "model": "voice-model",
        "voice": "coral",
        "input": "Only this text",
    }
    assert played == {"audio": b"RIFFxxxxWAVEaudio", "content_type": "audio/wav"}


@pytest.mark.asyncio
async def test_external_tts_is_unavailable_without_key_and_never_calls_network(
    monkeypatch,
) -> None:
    called = False

    class UnexpectedClient:
        def __init__(self, **kwargs: object) -> None:
            nonlocal called
            called = True

    monkeypatch.setattr("app.tts.external.httpx.AsyncClient", UnexpectedClient)
    engine = ExternalTTSEngine(api_key=None, base_url="https://tts.example", model="m")

    assert engine.is_available() is False
    assert engine.list_voices() == []
    await engine.speak("text", None, 0, 100, None)
    assert called is False


@pytest.mark.asyncio
async def test_external_tts_swallows_network_errors(monkeypatch, caplog) -> None:
    class BrokenClient:
        async def __aenter__(self) -> "BrokenClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            raise httpx.ConnectError("offline")

        def __init__(self, **kwargs: object) -> None:
            pass

    monkeypatch.setattr("app.tts.external.httpx.AsyncClient", BrokenClient)
    engine = ExternalTTSEngine(
        api_key="secret", base_url="https://tts.example", model="m"
    )

    await engine.speak("text", None, 0, 100, None)

    assert "External TTS request failed" in caplog.text


def test_service_selects_external_engine_from_config() -> None:
    config = AppConfig(
        tts_engine="external",
        external_tts_api_key="secret",
        external_tts_base_url="https://tts.example/v1",
        external_tts_model="custom-model",
        external_tts_player_command="player {file}",
    )

    engine = BridgeService._build_tts_engine("external", config)

    assert isinstance(engine, ExternalTTSEngine)
    assert engine.is_available() is True
    assert engine.model == "custom-model"
    assert engine.player_command == "player {file}"
