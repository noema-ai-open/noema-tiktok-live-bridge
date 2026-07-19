import asyncio

import pytest

from app.events.dedupe import EventDeduplicator


@pytest.mark.asyncio
async def test_deduplicates_non_chat_by_event_id_within_window(event_factory) -> None:
    dedupe = EventDeduplicator(window_seconds=0.02)
    first = event_factory(event_id="same", event_type="follow", message=None)
    second = event_factory(event_id="same", event_type="follow", message=None)

    assert await dedupe.is_duplicate(first) is False
    assert await dedupe.is_duplicate(second) is True
    assert (
        await dedupe.is_duplicate(
            event_factory(event_id="other", event_type="follow", message=None)
        )
        is False
    )

    await asyncio.sleep(0.03)
    assert await dedupe.is_duplicate(second) is False


@pytest.mark.asyncio
async def test_deduplicates_chat_replays_by_user_and_message(event_factory) -> None:
    dedupe = EventDeduplicator(
        window_seconds=0.02,
        chat_replay_window_seconds=0.02,
    )
    first = event_factory(event_id="chat-1", user_id="viewer-1", message="Hallo  Chat")
    replay = event_factory(event_id="chat-2", user_id="viewer-1", message="  hallo chat ")

    assert await dedupe.is_duplicate(first) is False
    assert await dedupe.is_duplicate(replay) is True
    assert (
        await dedupe.is_duplicate(
            event_factory(event_id="chat-3", user_id="viewer-2", message="Hallo Chat")
        )
        is False
    )

    await asyncio.sleep(0.03)
    assert await dedupe.is_duplicate(replay) is False
