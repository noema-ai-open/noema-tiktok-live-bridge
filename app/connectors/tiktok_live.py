"""TikTok LIVE connector implemented with the UNOFFICIAL TikTokLive library.

TikTokLive reverse-engineers TikTok and obtains request signatures through the
third-party Euler Stream service. Both mechanisms can change or break at any
time; this connector must therefore always remain optional and failure-tolerant.
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import random
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.connectors.base import BaseConnector, EventCallback

logger = logging.getLogger(__name__)

_EVENT_TYPES = {
    "ConnectEvent": "status",
    "DisconnectEvent": "status",
    "CommentEvent": "chat_message",
    "JoinEvent": "join",
    "LikeEvent": "like",
    "FollowEvent": "follow",
    "ShareEvent": "share",
    "GiftEvent": "gift",
    "SubscribeEvent": "subscribe",
}


def _value(obj: object, *path: str) -> Any:
    current: Any = obj
    for part in path:
        if current is None:
            return None
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def _first(obj: object, *paths: tuple[str, ...]) -> Any:
    for path in paths:
        value = _value(obj, *path)
        if value is not None and value != "":
            return value
    return None


def _timestamp(event: object) -> datetime:
    value = _first(event, ("timestamp",), ("common", "create_time"), ("create_time",))
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)) and value > 0:
        # TikTok schemas have used both seconds and milliseconds.
        seconds = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(seconds, timezone.utc)
        except (OverflowError, OSError, ValueError):
            pass
    return datetime.now(timezone.utc)


def _event_user(event: object) -> dict[str, object]:
    user = _value(event, "user")
    source = user if user is not None else event
    unique_id = _first(
        source,
        ("unique_id",),
        ("user_id",),
        ("id_str",),
        ("id",),
    )
    display_name = _first(
        source,
        ("nickname",),
        ("display_name",),
        ("name",),
        ("unique_id",),
    )
    user_id = str(unique_id) if unique_id is not None else "tiktok:system"
    return {
        "display_name": str(display_name or "TikTok Live"),
        "user_id": user_id,
        "is_moderator": bool(_first(source, ("is_moderator",)) or False),
        "is_subscriber": bool(
            _first(
                source,
                ("is_subscriber",),
                ("is_subscribe",),
                ("subscribe_info", "is_member"),
            )
            or False
        ),
    }


def map_tiktok_event(event: object, event_name: str | None = None) -> dict[str, object]:
    """Map a TikTokLive-like object without importing the optional library."""
    name = event_name or type(event).__name__
    try:
        event_type = _EVENT_TYPES[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported TikTokLive event: {name}") from exc

    event_id = _first(
        event,
        ("common", "msg_id"),
        ("msg_id",),
        ("event_id",),
        ("id",),
    )
    metadata: dict[str, object] = {}
    result: dict[str, object] = {
        "event_type": event_type,
        "event_id": str(event_id or f"tiktok-{uuid4()}"),
        "timestamp": _timestamp(event),
        "user": _event_user(event),
        "metadata": metadata,
    }

    if name == "ConnectEvent":
        metadata["status"] = "connected"
        room_id = _first(event, ("room_id",))
        if room_id is not None:
            metadata["room_id"] = room_id
    elif name == "DisconnectEvent":
        metadata["status"] = "disconnected"
    elif name == "CommentEvent":
        result["message"] = str(_first(event, ("comment",), ("message",)) or "")
    elif name == "LikeEvent":
        like_count = _first(event, ("count",), ("like_count",))
        if like_count is not None:
            metadata["like_count"] = like_count
    elif name == "GiftEvent":
        gift_name = _first(
            event,
            ("gift", "name"),
            ("gift_name",),
            ("extended_gift", "name"),
        )
        repeat_count = _first(
            event, ("repeat_count",), ("gift", "repeat_count"), ("count",)
        )
        diamond_count = _first(
            event, ("gift", "diamond_count"), ("diamond_count",)
        )
        if gift_name is not None:
            metadata["gift_name"] = gift_name
        if repeat_count is not None:
            metadata["repeat_count"] = repeat_count
        if diamond_count is not None:
            metadata["diamond_count"] = diamond_count
    return result


def calculate_backoff(
    attempt: int,
    *,
    initial: float = 5.0,
    factor: float = 2.0,
    maximum: float = 300.0,
    jitter: float = 0.2,
    random_value: float | None = None,
) -> float:
    """Return capped exponential backoff with symmetric proportional jitter."""
    if attempt < 0:
        raise ValueError("attempt must not be negative")
    if initial < 0 or factor < 1 or maximum < 0 or not 0 <= jitter <= 1:
        raise ValueError("invalid backoff parameters")
    base = min(maximum, initial * factor**attempt)
    if jitter == 0 or base == 0:
        return base
    sample = random.random() if random_value is None else random_value
    if not 0 <= sample <= 1:
        raise ValueError("random_value must be between 0 and 1")
    return min(maximum, max(0.0, base * (1 + jitter * (2 * sample - 1))))


def _load_tiktoklive() -> tuple[type[Any], dict[str, type[Any]], tuple[type[BaseException], ...], Any]:
    package = importlib.import_module("TikTokLive")
    events_module = importlib.import_module("TikTokLive.events")
    errors_module = importlib.import_module("TikTokLive.client.errors")
    settings_module = importlib.import_module("TikTokLive.client.web.web_settings")
    client_class = getattr(package, "TikTokLiveClient")
    event_classes = {
        name: event_class
        for name in _EVENT_TYPES
        if (event_class := getattr(events_module, name, None)) is not None
    }
    offline_error = getattr(errors_module, "UserOfflineError", None)
    offline_errors = (offline_error,) if isinstance(offline_error, type) else ()
    return client_class, event_classes, offline_errors, getattr(settings_module, "WebDefaults")


class TikTokLiveConnector(BaseConnector):
    def __init__(
        self,
        on_event: EventCallback,
        username: str | None,
        *,
        eulerstream_api_key: str | None = None,
        live_offline_poll_seconds: float = 60.0,
    ) -> None:
        super().__init__(on_event)
        if live_offline_poll_seconds <= 0:
            raise ValueError("live_offline_poll_seconds must be positive")
        self.username = username.strip().lstrip("@") if username else ""
        self.eulerstream_api_key = eulerstream_api_key
        self.live_offline_poll_seconds = live_offline_poll_seconds
        self._status = "disconnected"
        self._last_error: str | None = None
        self._task: asyncio.Task[None] | None = None
        self._client: Any | None = None
        self._stopping = False
        self._connected_since: float | None = None
        self._dependency: tuple[
            type[Any], dict[str, type[Any]], tuple[type[BaseException], ...], Any
        ] | None = None

    @property
    def status(self) -> str:
        return self._status

    @property
    def last_error(self) -> str | None:
        return self._last_error

    async def connect(self) -> None:
        if self._task is not None and not self._task.done():
            return
        if not self.username:
            await self._mark_unavailable(
                "TikTok live mode requires NOEMA_TIKTOK_USERNAME in .env"
            )
            return
        try:
            self._dependency = _load_tiktoklive()
        except Exception as exc:
            await self._mark_unavailable(
                "TikTokLive is not installed or incompatible; install the optional "
                "live extra with `python -m pip install -e '.[live]'`",
                exc,
            )
            return
        self._stopping = False
        self._last_error = None
        self._task = asyncio.create_task(self._run(), name="tiktok-live-connector")

    async def disconnect(self) -> None:
        self._stopping = True
        client = self._client
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("TikTokLive failed during graceful disconnect")
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._client = None
        self._connected_since = None
        if self._status != "unavailable":
            self._status = "disconnected"

    async def _mark_unavailable(
        self, message: str, cause: BaseException | None = None
    ) -> None:
        self._status = "unavailable"
        self._last_error = message
        if cause is None:
            logger.error(message)
        else:
            logger.error("%s (%s)", message, type(cause).__name__)
        await self._emit_status("unavailable", error=message)

    async def _emit_status(self, status: str, *, error: str | None = None) -> None:
        metadata: dict[str, object] = {"status": status}
        if error:
            metadata["error"] = error
        await self.on_event(
            {
                "event_type": "status",
                "event_id": f"tiktok-status-{uuid4()}",
                "timestamp": datetime.now(timezone.utc),
                "user": {
                    "display_name": self.username or "TikTok Live",
                    "user_id": self.username or "tiktok:system",
                    "is_moderator": False,
                    "is_subscriber": False,
                },
                "metadata": metadata,
            }
        )

    def _add_listeners(self, client: Any, event_classes: dict[str, type[Any]]) -> None:
        for name, event_class in event_classes.items():
            async def listener(event: object, event_name: str = name) -> None:
                try:
                    mapped = map_tiktok_event(event, event_name)
                    if event_name == "ConnectEvent":
                        self._status = "connected"
                        self._connected_since = time.monotonic()
                    elif event_name == "DisconnectEvent":
                        self._status = "disconnected"
                    await self.on_event(mapped)
                except Exception:
                    logger.exception("Failed to process %s", event_name)

            client.add_listener(event_class, listener)

    def _was_stable(self) -> bool:
        return (
            self._connected_since is not None
            and time.monotonic() - self._connected_since > 60.0
        )

    async def _run(self) -> None:
        dependency = self._dependency
        if dependency is None:
            return
        client_class, event_classes, offline_errors, web_defaults = dependency
        attempt = 0
        try:
            while not self._stopping:
                delay: float
                self._connected_since = None
                try:
                    if self.eulerstream_api_key:
                        web_defaults.tiktok_sign_api_key = self.eulerstream_api_key
                    client = client_class(unique_id=self.username)
                    self._client = client
                    self._add_listeners(client, event_classes)
                    self._status = "connecting"
                    await self._emit_status("connecting")
                    await client.connect()
                    if self._stopping:
                        break
                    if self._was_stable():
                        attempt = 0
                    delay = calculate_backoff(attempt)
                    attempt += 1
                    self._status = "reconnecting"
                    await self._emit_status("reconnecting")
                except asyncio.CancelledError:
                    raise
                except offline_errors:
                    if self._stopping:
                        break
                    attempt = 0
                    self._status = "offline"
                    await self._emit_status("offline")
                    delay = self.live_offline_poll_seconds
                except Exception as exc:
                    if self._stopping:
                        break
                    if self._was_stable():
                        attempt = 0
                    delay = calculate_backoff(attempt)
                    attempt += 1
                    self._status = "reconnecting"
                    self._last_error = (
                        f"TikTokLive connection failed ({type(exc).__name__})"
                    )
                    logger.warning(
                        "TikTokLive connection failed; retrying in %.1fs (%s)",
                        delay,
                        type(exc).__name__,
                    )
                    await self._emit_status("reconnecting", error=self._last_error)
                finally:
                    self._client = None
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        finally:
            self._client = None
            self._connected_since = None
            if self._status != "unavailable":
                self._status = "disconnected"
