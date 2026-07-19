import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_health_status_events_and_fallback_with_asgi_transport(fallback_app) -> None:
    async with fallback_app.router.lifespan_context(fallback_app):
        transport = httpx.ASGITransport(app=fallback_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json() == {"status": "ok"}

            status = await client.get("/status")
            assert status.status_code == 200
            assert status.json() == {
                "mode": "fallback",
                "connector_status": "unavailable",
                "queue_lengths": {"subscribers": [], "ring_buffer": 0},
            }

            posted = await client.post(
                "/fallback/message",
                json={"display_name": "Local Viewer", "message": "hello from fallback"},
            )
            assert posted.status_code == 200
            assert posted.json()["accepted"] is True
            assert posted.json()["event"]["platform"] == "tiktok"
            assert posted.json()["event"]["metadata"] == {"source": "fallback"}

            events = await client.get("/events", params={"limit": 1})
            assert events.status_code == 200
            assert [event["message"] for event in events.json()] == ["hello from fallback"]


@pytest.mark.asyncio
async def test_settings_partial_update_is_validated(fallback_app) -> None:
    async with fallback_app.router.lifespan_context(fallback_app):
        transport = httpx.ASGITransport(app=fallback_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/settings", json={"max_message_length": 4, "retention": "24h"}
            )
            assert response.status_code == 200
            assert response.json()["max_message_length"] == 4
            assert response.json()["retention"] == "24h"

            blocked = await client.post(
                "/fallback/message", json={"display_name": "Viewer", "message": "too long"}
            )
            assert blocked.json()["accepted"] is False
            assert blocked.json()["reason"] == "max_length"

            invalid = await client.post("/settings", json={"max_message_length": 0})
            assert invalid.status_code == 422


def test_websocket_outputs_filtered_fallback_event(fallback_app) -> None:
    with TestClient(fallback_app) as client:
        with client.websocket_connect("/ws/events") as websocket:
            response = client.post(
                "/fallback/message",
                json={"display_name": "WS Viewer", "message": "live local text"},
            )
            assert response.status_code == 200
            event = websocket.receive_json()
            assert event["event_type"] == "chat_message"
            assert event["message"] == "live local text"


def test_fallback_endpoint_rejects_non_fallback_mode(tmp_path) -> None:
    from app.config import AppConfig
    from app.main import create_app

    app = create_app(AppConfig(mode="live", database_path=tmp_path / "live.sqlite3"))
    with TestClient(app) as client:
        response = client.post(
            "/fallback/message", json={"display_name": "Viewer", "message": "hello"}
        )
    assert response.status_code == 409

