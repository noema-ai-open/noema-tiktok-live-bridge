import asyncio
from types import SimpleNamespace

import pytest

from app.connectors.tiktok_live import (
    TikTokLiveConnector,
    _connection_error,
    _connection_profiles,
    _is_websocket_http_400,
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


def test_connection_error_keeps_useful_exception_detail_bounded() -> None:
    error = _connection_error(RuntimeError("signature service returned 429"))
    assert error == (
        "TikTokLive connection failed (RuntimeError): "
        "signature service returned 429"
    )
    long_error = _connection_error(RuntimeError("x" * 500))
    assert long_error.endswith("...")
    assert len(long_error) < 360


def test_connection_error_includes_tiktok_handshake_reason() -> None:
    class RejectedHandshake(RuntimeError):
        status_code = 400
        headers = {"Handshake-Msg": "invalid route"}

    exc = RejectedHandshake("server rejected WebSocket connection: HTTP 400")
    error = _connection_error(exc)

    assert "HTTP 400" in error
    assert "TikTok handshake: invalid route" in error
    assert _is_websocket_http_400(exc)


def test_http_400_detection_walks_exception_chain() -> None:
    cause = RuntimeError("server rejected WebSocket connection: HTTP 400")
    wrapper = RuntimeError("connect failed")
    wrapper.__cause__ = cause

    assert _is_websocket_http_400(wrapper)
    assert not _is_websocket_http_400(RuntimeError("HTTP 429"))


def test_connection_profiles_try_keyless_and_compatible_handshakes() -> None:
    profiles = _connection_profiles("secret")

    assert [name for name, _, _ in profiles] == [
        "default/configured-key",
        "default/community-key",
        "compat/configured-key",
        "compat/community-key",
    ]
    assert profiles[0][1] == "secret"
    assert profiles[1][1] is None
    assert profiles[2][2] == {
        "subprotocols": None,
        "compression": None,
        "origin": "https://www.tiktok.com",
    }


@pytest.mark.asyncio
async def test_http_400_rotates_through_connection_profiles(monkeypatch) -> None:
    received: list[dict[str, object]] = []
    calls: list[tuple[str | None, dict[str, object]]] = []
    web_defaults = SimpleNamespace(tiktok_sign_api_key=None)

    async def collect(event: dict[str, object]) -> None:
        received.append(event)

    class RejectedHandshake(RuntimeError):
        status_code = 400
        headers: dict[str, str] = {}

    class RejectingClient:
        def __init__(self, *, unique_id: str, ws_kwargs: dict[str, object]) -> None:
            assert unique_id == "streamer"
            calls.append((web_defaults.tiktok_sign_api_key, ws_kwargs))

        def add_listener(self, event_class, listener) -> None:
            pass

        async def connect(self) -> None:
            raise RejectedHandshake(
                "server rejected WebSocket connection: HTTP 400"
            )

        async def disconnect(self) -> None:
            pass

    monkeypatch.setattr(
        "app.connectors.tiktok_live._load_tiktoklive",
        lambda: (RejectingClient, {}, (), web_defaults),
    )
    monkeypatch.setattr(
        "app.connectors.tiktok_live.calculate_backoff", lambda *args, **kwargs: 0
    )
    connector = TikTokLiveConnector(collect, "streamer", eulerstream_api_key="secret")

    await connector.connect()
    for _ in range(100):
        if len(calls) >= 4:
            break
        await asyncio.sleep(0)
    await connector.disconnect()

    assert calls[:4] == [
        ("secret", {}),
        (None, {}),
        (
            "secret",
            {
                "subprotocols": None,
                "compression": None,
                "origin": "https://www.tiktok.com",
            },
        ),
        (
            None,
            {
                "subprotocols": None,
                "compression": None,
                "origin": "https://www.tiktok.com",
            },
        ),
    ]
    assert any(event["metadata"]["status"] == "reconnecting" for event in received)


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
