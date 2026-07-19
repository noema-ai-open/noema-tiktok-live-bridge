from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.events.models import Event, User


class EventNormalizer:
    """Convert connector payloads into the one strict internal event format."""

    def normalize(self, raw: Event | Mapping[str, Any]) -> Event:
        if isinstance(raw, Event):
            return raw

        data = dict(raw)
        raw_user = data.get("user") or {}
        if not isinstance(raw_user, Mapping):
            raise ValueError("user must be an object")

        display_name = str(raw_user.get("display_name") or "Anonymous")
        user_id = str(raw_user.get("user_id") or f"anonymous:{display_name}")
        user = User(
            display_name=display_name,
            user_id=user_id,
            is_moderator=bool(raw_user.get("is_moderator", False)),
            is_subscriber=bool(raw_user.get("is_subscriber", False)),
        )
        timestamp = data.get("timestamp") or datetime.now(timezone.utc)
        metadata = data.get("metadata") or {}
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")

        return Event(
            platform="tiktok",
            event_type=data["event_type"],
            event_id=str(data.get("event_id") or uuid4()),
            timestamp=timestamp,
            user=user,
            message=data.get("message"),
            metadata=dict(metadata),
        )

