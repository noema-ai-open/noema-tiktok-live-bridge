import httpx
import pytest

from app.tts.deepgram import DeepgramTTSEngine


def test_unavailable_without_key():
    engine = DeepgramTTSEngine(api_key=None)
    assert not engine.is_available()
    assert engine.list_voices() == []


@pytest.mark.asyncio
async def test_speak_sends_deepgram_format(monkeypatch):
    captured = {}

    class FakeResponse:
        content = b"RIFF0000WAVEdata"
        headers = {"content-type": "audio/wav"}

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, *, params, headers, json):
            captured.update(url=url, params=params, headers=headers, json=json)
            return FakeResponse()

    played = {}

    async def fake_play(self, audio, content_type):
        played.update(audio=audio, content_type=content_type)

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(DeepgramTTSEngine, "_play", fake_play)

    engine = DeepgramTTSEngine(api_key="testkey")
    await engine.speak("Hallo Chat", "aura-2-thalia-en", 0, 100, None)

    assert captured["json"] == {"text": "Hallo Chat"}
    assert captured["params"]["model"] == "aura-2-thalia-en"
    assert captured["params"]["container"] == "wav"
    assert captured["headers"]["Authorization"] == "Token testkey"
    assert played["content_type"] == "audio/wav"
