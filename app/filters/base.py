from dataclasses import dataclass
from typing import Protocol

from app.events.models import Event


@dataclass(frozen=True, slots=True)
class FilterResult:
    allowed: bool
    event: Event
    reason: str | None = None

    @classmethod
    def allow(cls, event: Event) -> "FilterResult":
        return cls(allowed=True, event=event)

    @classmethod
    def block(cls, event: Event, reason: str) -> "FilterResult":
        return cls(allowed=False, event=event, reason=reason)


class EventFilter(Protocol):
    async def apply(self, event: Event) -> FilterResult: ...

