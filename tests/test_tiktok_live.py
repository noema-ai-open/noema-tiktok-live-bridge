from types import SimpleNamespace

import pytest

from app.connectors.tiktok_live import (
    TikTokLiveConnector,
    calculate_backoff,
    map_tiktok_event,
)
from app.events.models import Event


def fake_user(**overrides: object) -> SimpleNamespace:
    values = {
        "unique_id": "viewer_1",
        "nickname": "Viewer One",
        "is_moderator": True,
        "is_subscriber": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("event_name", "expected_type"),
    [
        ("JoinEvent", "join"),
        ("LikeEvent", "like"),
        ("FollowEvent", "follow"),
        ("ShareEvent", "share"),
        ("SubscribeEvent", "subscribe"),
    ],
)
def test_maps_tiktok_user_events_without_importing_library(
    event_name: str, expected_type: str
) -> None:
    fake = SimpleNamespace(user=fake_user(), common=SimpleNamespace(msg_id=123))

    mapped = map_tiktok_event(fake, event_name)
    normalized = Event.model_validate(mapped)

    assert normalized.event_type.value == expected_type
    assert normalized.event_id == "123"
    assert normalized.user.model_dump() == {
        "display_name": "Viewer One",
        "user_id": "viewer_1",
        "is_moderator": True,
        "is_subscriber": True,
    }


def test_maps_comment_gift_and_status_metadata() -> None:
    comment = map_tiktok_event(
        SimpleNamespace(user=fake_user(), comment="hello"), "CommentEvent"
    )
    gift = map_tiktok_event(
        SimpleNamespace(
            user=fake_user(is_moderator=False, is_subscriber=False),
            gift=SimpleNamespace(name="Rose", diamond_count=1),
            repeat_count=3,
        ),
        "GiftEvent",
    )
    connected = map_tiktok_event(
        SimpleNamespace(unique_id="streamer", room_id=456), "ConnectEvent"
    )
    disconnected = map_tiktok_event(SimpleNamespace(), "DisconnectEvent")

    assert comment["event_type"] == "chat_message"
    assert comment["message"] == "hello"
    assert gift["metadata"] == {
        "gift_name": "Rose",
        "repeat_count": 3,
        "diamond_count": 1,
    }
    assert connected["metadata"] == {"status": "connected", "room_id": 456}
    assert connected["user"]["user_id"] == "streamer"
    assert disconnected["metadata"] == {"status": "disconnected"}
    Event.model_validate(comment)
    Event.model_validate(gift)
    Event.model_validate(connected)
    Event.model_validate(disconnected)


def test_backoff_is_exponential_capped_and_has_bounded_jitter() -> None:
    assert [calculate_backoff(attempt, jitter=0) for attempt in range(8)] == [
        5,
        10,
        20,
        40,
        80,
        160,
        300,
        300,
    ]
    assert calculate_backoff(2, random_value=0.0) == 16
    assert calculate_backoff(2, random_value=1.0) == 24
    assert calculate_backoff(20, random_value=1.0) == 300


@pytest.mark.asyncio
async def test_missing_tiktok_dependency_reports_unavailable(monkeypatch) -> None:
    received: list[dict[str, object]] = []

    async def collect(event: dict[str, object]) -> None:
        received.append(event)

    def missing_dependency():
        raise ModuleNotFoundError("TikTokLive")

    monkeypatch.setattr(
        "app.connectors.tiktok_live._load_tiktoklive", missing_dependency
    )
    connector = TikTokLiveConnector(collect, "streamer")

    await connector.connect()

    assert connector.status == "unavailable"
    assert "install" in (connector.last_error or "")
    assert received[0]["metadata"]["status"] == "unavailable"
