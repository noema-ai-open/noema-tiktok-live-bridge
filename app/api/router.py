import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from app.api.schemas import ConnectionUpdate, FallbackMessage, TTSTestRequest
from app.audio.devices import list_audio_devices
from app.service import BridgeService
from app.storage.settings import RuntimeSettings, SettingsUpdate

router = APIRouter()


def _service(request: Request) -> BridgeService:
    return request.app.state.bridge


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request) -> dict[str, object]:
    return _service(request).status_payload()


@router.get("/tts/state")
async def tts_state(request: Request) -> dict[str, bool]:
    """Leichter Live-Status für das KITT-Modul in der lokalen Oberfläche."""
    current_speech = _service(request).tts_worker._current_speech
    return {
        "speaking": current_speech is not None and not current_speech.done(),
    }


@router.get("/events")
async def events(
    request: Request, limit: int = Query(default=100, ge=1, le=1000)
) -> list[dict[str, object]]:
    return [event.json_payload() for event in _service(request).pipeline.latest(limit)]


@router.get("/settings")
async def get_settings(request: Request) -> RuntimeSettings:
    return _service(request).settings_store.get()


@router.post("/settings")
async def update_settings(request: Request, update: SettingsUpdate) -> dict[str, object]:
    settings = await _service(request).update_settings(update)
    return settings.model_dump()


@router.post("/tts/test", status_code=202)
async def test_tts(request: Request, body: TTSTestRequest) -> dict[str, bool]:
    service = _service(request)
    settings = service.tts_worker.settings
    if not settings.tts_enabled:
        raise HTTPException(status_code=409, detail="TTS is disabled")
    if not service.tts_engine.is_available():
        raise HTTPException(status_code=409, detail="TTS engine is unavailable")
    if not service.tts_worker.enqueue_test(body.text):
        raise HTTPException(status_code=422, detail="text contains no speakable content")
    return {"queued": True}


@router.post("/tts/stop")
async def stop_tts(request: Request) -> dict[str, bool]:
    await _service(request).tts_worker.clear()
    return {"stopped": True}


@router.get("/tts/voices")
async def tts_voices(request: Request) -> list[dict[str, str]]:
    return _service(request).tts_engine.list_voices()


@router.get("/tts/sapi-voices")
async def sapi_voices() -> list[dict[str, str]]:
    """Installierte Windows-Stimmen, unabhängig vom aktuell aktiven Anbieter."""
    from app.tts.sapi import SAPIEngine

    return SAPIEngine().list_voices()


@router.get("/tts/edge-voices")
async def edge_voices() -> list[dict[str, str]]:
    """Alle Microsoft-Edge-Stimmen, unabhängig vom aktuell aktiven Anbieter."""
    from app.tts.edge import fetch_all_voices

    return await fetch_all_voices()


@router.get("/audio/devices")
async def audio_devices() -> list[dict[str, str]]:
    return list_audio_devices()


@router.post("/fallback/message")
async def fallback_message(request: Request, body: FallbackMessage) -> dict[str, object]:
    service = _service(request)
    if service.config.mode != "fallback":
        raise HTTPException(status_code=409, detail="fallback mode is not active")
    event_id = f"fallback-{uuid4()}"
    result = await service.process_fallback(
        {
            "event_type": "chat_message",
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc),
            "user": {
                "display_name": body.display_name,
                "user_id": f"fallback:{body.display_name}",
                "is_moderator": False,
                "is_subscriber": False,
            },
            "message": body.message,
            "metadata": {"source": "fallback"},
        }
    )
    return {
        "accepted": result.accepted,
        "reason": result.reason,
        "event": result.event.json_payload(),
    }


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket) -> None:
    service: BridgeService = websocket.app.state.bridge
    queue = await service.bus.subscribe(include_blocked=True)
    try:
        # Subscribe before accepting so an event cannot slip through between the
        # completed WebSocket handshake and queue registration.
        await websocket.accept()
        while True:
            event_task = asyncio.create_task(queue.get())
            client_task = asyncio.create_task(websocket.receive())
            done, pending = await asyncio.wait(
                {event_task, client_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            if client_task in done:
                client_message = client_task.result()
                if client_message["type"] == "websocket.disconnect":
                    break
            if event_task in done:
                await websocket.send_json(event_task.result().json_payload())
    except WebSocketDisconnect:
        pass
    finally:
        await service.bus.unsubscribe(queue)


@router.get("/connection")
async def get_connection(request: Request) -> dict[str, object]:
    return _service(request).connection_payload()


@router.get("/connection/keys")
async def get_connection_keys(request: Request) -> dict[str, object]:
    """Klartext-Schlüssel auf ausdrücklichen Wunsch (lokale App, localhost)."""
    config = _service(request).config
    return {
        "deepgram_api_key": (
            config.deepgram_api_key.get_secret_value()
            if config.deepgram_api_key
            else None
        ),
        "external_tts_api_key": (
            config.external_tts_api_key.get_secret_value()
            if config.external_tts_api_key
            else None
        ),
    }


@router.post("/connection")
async def update_connection(request: Request, body: ConnectionUpdate) -> dict[str, object]:
    service = _service(request)
    await service.apply_connection(body)
    return service.connection_payload()
