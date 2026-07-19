import asyncio

import httpx
import pytest

from app.config import AppConfig
from app.events.bus import EventBus
from app.main import create_app
from app.storage.settings import RuntimeSettings
from app.tts.dummy import DummyEngine
from app.tts.queue import TTSQueueWorker
from app.tts.sapi import SAPIEngine


async def wait_until(predicate, timeout: float = 1.0) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.005)


async def publish_messages(bus, event_factory, *messages: str, user_id: str = "user-1"):
    for index, message in enumerate(messages):
        await bus.publish(
            event_factory(event_id=f"tts-{index}", message=message, user_id=user_id)
        )


@pytest.mark.asyncio
async def test_tts_queue_preserves_order_and_sanitizes_markup(event_factory) -> None:
    bus = EventBus()
    engine = DummyEngine()
    worker = TTSQueueWorker(bus, engine, RuntimeSettings(tts_enabled=True))
    await worker.start()
    try:
        await publish_messages(bus, event_factory, "first", "<speak>second</speak>", "third")
        await wait_until(lambda: len(engine.spoken_texts) == 3)
        assert engine.spoken_texts == ["first", "second", "third"]
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_queue_applies_per_user_cooldown_and_max_length(event_factory) -> None:
    bus = EventBus()
    engine = DummyEngine()
    settings = RuntimeSettings(
        tts_enabled=True,
        tts_user_cooldown_seconds=60,
        tts_max_length=5,
    )
    worker = TTSQueueWorker(bus, engine, settings)
    await worker.start()
    try:
        await publish_messages(bus, event_factory, "abcdefgh", "blocked")
        await publish_messages(bus, event_factory, "other", user_id="user-2")
        await wait_until(lambda: len(engine.spoken_texts) == 2)
        assert engine.spoken_texts == ["abcde", "other"]
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_queue_overflow_discards_oldest_waiting_item(event_factory) -> None:
    bus = EventBus()
    engine = DummyEngine(duration=0.05)
    worker = TTSQueueWorker(
        bus,
        engine,
        RuntimeSettings(tts_enabled=True, tts_queue_max=2),
    )
    await worker.start()
    try:
        await publish_messages(bus, event_factory, "one")
        await wait_until(lambda: engine.spoken_texts == ["one"])
        await publish_messages(bus, event_factory, "two", "three", "four")
        await wait_until(lambda: len(engine.spoken_texts) == 3)
        assert engine.spoken_texts == ["one", "three", "four"]
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_clear_stops_current_output_and_empties_queue(event_factory) -> None:
    bus = EventBus()
    engine = DummyEngine(duration=None)
    worker = TTSQueueWorker(bus, engine, RuntimeSettings(tts_enabled=True))
    await worker.start()
    try:
        await publish_messages(bus, event_factory, "one", "two")
        await wait_until(lambda: engine.spoken_texts == ["one"])
        await worker.clear()
        await asyncio.sleep(0.02)
        assert engine.spoken_texts == ["one"]
        assert worker.queue_size == 0
        assert engine.stop_count >= 1
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_timeout_stops_hung_engine_and_continues(event_factory) -> None:
    bus = EventBus()
    engine = DummyEngine(duration=None)
    worker = TTSQueueWorker(
        bus,
        engine,
        RuntimeSettings(tts_enabled=True, tts_timeout_seconds=0.03),
    )
    await worker.start()
    try:
        await publish_messages(bus, event_factory, "one", "two")
        await wait_until(lambda: len(engine.spoken_texts) == 2)
        assert engine.stop_count >= 1
        assert worker.is_running
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_engine_error_does_not_end_worker(event_factory) -> None:
    class FlakyEngine(DummyEngine):
        async def speak(self, text, voice, rate, volume, device) -> None:
            if text == "bad":
                raise RuntimeError("simulated engine failure")
            await super().speak(text, voice, rate, volume, device)

    bus = EventBus()
    engine = FlakyEngine()
    worker = TTSQueueWorker(bus, engine, RuntimeSettings(tts_enabled=True))
    await worker.start()
    try:
        await publish_messages(bus, event_factory, "bad", "good")
        await wait_until(lambda: engine.spoken_texts == ["good"])
        assert worker.is_running
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_settings_take_effect_live(event_factory) -> None:
    bus = EventBus()
    engine = DummyEngine()
    worker = TTSQueueWorker(bus, engine, RuntimeSettings(tts_enabled=False))
    await worker.start()
    try:
        await worker.update_settings(
            RuntimeSettings(
                tts_enabled=True,
                read_username=True,
                tts_voice="dummy",
                tts_volume=42,
                tts_device="output-1",
            )
        )
        await publish_messages(bus, event_factory, "hello")
        await wait_until(lambda: len(engine.calls) == 1)
        assert engine.calls[0] == {
            "text": "Viewer: hello",
            "voice": "dummy",
            "rate": 0,
            "volume": 42,
            "device": "output-1",
        }
    finally:
        await worker.stop()


@pytest.mark.asyncio
async def test_tts_api_test_stop_voices_and_disabled_conflict(tmp_path) -> None:
    app = create_app(
        AppConfig(
            mode="fallback",
            database_path=tmp_path / "tts-api.sqlite3",
            tts_engine="dummy",
        )
    )
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            disabled = await client.post("/tts/test", json={"text": "hello"})
            assert disabled.status_code == 409

            enabled = await client.post("/settings", json={"tts_enabled": True})
            assert enabled.status_code == 200
            queued = await client.post("/tts/test", json={"text": "<speak>hello</speak>"})
            assert queued.status_code == 202
            assert queued.json() == {"queued": True}
            engine = app.state.bridge.tts_engine
            await wait_until(lambda: engine.spoken_texts == ["hello"])

            fallback = await client.post(
                "/fallback/message",
                json={"display_name": "API Viewer", "message": "from event bus"},
            )
            assert fallback.json()["accepted"] is True
            await wait_until(
                lambda: engine.spoken_texts == ["hello", "from event bus"]
            )

            voices = await client.get("/tts/voices")
            assert voices.status_code == 200
            assert voices.json() == [{"id": "dummy", "name": "Dummy Voice"}]
            devices = await client.get("/audio/devices")
            assert devices.status_code == 200
            assert isinstance(devices.json(), list)

            engine.duration = None
            hanging = await client.post("/tts/test", json={"text": "hanging"})
            assert hanging.status_code == 202
            await wait_until(lambda: engine.spoken_texts[-1] == "hanging")
            await client.post("/tts/test", json={"text": "queued behind it"})
            stopped = await client.post("/tts/stop")
            assert stopped.status_code == 200
            assert stopped.json() == {"stopped": True}
            assert app.state.bridge.tts_worker.queue_size == 0


def test_sapi_is_inert_off_windows() -> None:
    engine = SAPIEngine()
    if not engine.is_available():
        assert engine.list_voices() == []
        assert engine.list_audio_outputs() == []
        engine.stop()
