from datetime import timezone

import pytest
from pydantic import ValidationError

from app.events.models import Event, EventType
from app.events.normalizer import EventNormalizer


def test_normalizer_fills_defaults_and_forces_platform() -> None:
    event = EventNormalizer().normalize(
        {
            "platform": "something-else",
            "event_type": "chat_message",
            "user": {"display_name": "Guest", "user_id": "42"},
            "message": "plain <b>text</b>",
        }
    )

    assert event.platform == "tiktok"
    assert event.event_type == EventType.CHAT_MESSAGE
    assert event.event_id
    assert event.timestamp.tzinfo == timezone.utc
    assert event.message == "plain <b>text</b>"
    assert event.metadata == {}


def test_event_rejects_non_text_message(event_factory) -> None:
    payload = event_factory().model_dump()
    payload["message"] = {"command": "do-something"}
    with pytest.raises(ValidationError, match="message must be text"):
        Event.model_validate(payload)


def test_non_chat_event_cannot_have_message(event_factory) -> None:
    payload = event_factory(event_type="join", message=None).model_dump()
    payload["message"] = "not valid here"
    with pytest.raises(ValidationError, match="only valid"):
        Event.model_validate(payload)

