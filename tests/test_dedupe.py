import asyncio

import pytest

from app.events.dedupe import EventDeduplicator


@pytest.mark.asyncio
async def test_deduplicates_by_event_id_within_window(event_factory) -> None:
    dedupe = EventDeduplicator(window_seconds=0.02)
    first = event_factory(event_id="same")
    second = event_factory(event_id="same", message="different content")

    assert await dedupe.is_duplicate(first) is False
    assert await dedupe.is_duplicate(second) is True
    assert await dedupe.is_duplicate(event_factory(event_id="other")) is False

    await asyncio.sleep(0.03)
    assert await dedupe.is_duplicate(second) is False

