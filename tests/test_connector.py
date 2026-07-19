import asyncio

import pytest

from app.connectors.mock import MockConnector
from app.events.models import EventType


@pytest.mark.asyncio
async def test_mock_connector_emits_every_event_type_and_disconnects() -> None:
    received: list[dict[str, object]] = []
    complete = asyncio.Event()

    async def collect(event: dict[str, object]) -> None:
        received.append(event)
        if len(received) >= len(EventType):
            complete.set()

    connector = MockConnector(collect, events_per_second=500, seed=1)
    assert connector.status == "disconnected"
    await connector.connect()
    assert connector.status == "connected"
    await asyncio.wait_for(complete.wait(), timeout=1)
    await connector.disconnect()

    assert connector.status == "disconnected"
    assert {item["event_type"] for item in received[: len(EventType)]} == {
        event_type.value for event_type in EventType
    }
    assert all(item["metadata"]["simulated"] for item in received)

