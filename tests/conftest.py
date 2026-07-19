from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import AppConfig
from app.events.models import Event
from app.main import create_app


def make_event(
    *,
    event_id: str = "event-1",
    event_type: str = "chat_message",
    message: str | None = "hello",
    user_id: str = "user-1",
) -> Event:
    data: dict[str, object] = {
        "event_type": event_type,
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc),
        "user": {
            "display_name": "Viewer",
            "user_id": user_id,
            "is_moderator": False,
            "is_subscriber": False,
        },
        "metadata": {},
    }
    if event_type == "chat_message":
        data["message"] = message
    return Event.model_validate(data)


@pytest.fixture
def event_factory():
    return make_event


@pytest.fixture
def fallback_app(tmp_path: Path):
    return create_app(
        AppConfig(
            mode="fallback",
            database_path=tmp_path / "test.sqlite3",
            ring_buffer_size=10,
        )
    )

