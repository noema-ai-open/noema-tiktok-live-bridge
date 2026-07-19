import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect

from app.api.schemas import FallbackMessage
from app.service import BridgeService
from app.storage.settings import SettingsUpdate

router = APIRouter()


def _service(request: Request) -> BridgeService:
    return request.app.state.bridge


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request) -> dict[str, object]:
    return _service(request).status_payload()


@router.get("/events")
async def events(
    request: Request, limit: int = Query(default=100, ge=1, le=1000)
) -> list[dict[str, object]]:
    return [event.json_payload() for event in _service(request).pipeline.latest(limit)]


@router.post("/settings")
async def update_settings(request: Request, update: SettingsUpdate) -> dict[str, object]:
    settings = await _service(request).update_settings(update)
    return settings.model_dump()


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
    queue = await service.bus.subscribe()
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
