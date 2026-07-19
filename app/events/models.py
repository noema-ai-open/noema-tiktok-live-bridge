from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EventType(str, Enum):
    STATUS = "status"
    JOIN = "join"
    CHAT_MESSAGE = "chat_message"
    LIKE = "like"
    FOLLOW = "follow"
    SHARE = "share"
    GIFT = "gift"
    SUBSCRIBE = "subscribe"


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=200)
    user_id: str = Field(min_length=1, max_length=200)
    is_moderator: bool = False
    is_subscriber: bool = False


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["tiktok"] = "tiktok"
    event_type: EventType
    event_id: str = Field(min_length=1, max_length=300)
    timestamp: datetime
    user: User
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    @field_validator("message", mode="before")
    @classmethod
    def message_must_be_text(cls, value: object) -> object:
        if value is not None and not isinstance(value, str):
            raise ValueError("message must be text")
        return value

    @model_validator(mode="after")
    def message_matches_type(self) -> "Event":
        if self.event_type == EventType.CHAT_MESSAGE and self.message is None:
            raise ValueError("chat_message events require a message")
        if self.event_type != EventType.CHAT_MESSAGE and self.message is not None:
            raise ValueError("message is only valid for chat_message events")
        return self

    def json_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
