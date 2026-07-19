import unicodedata

from app.events.models import Event, EventType
from app.filters.base import FilterResult


class ControlCharacterFilter:
    """Remove Unicode control characters while retaining normal whitespace."""

    async def apply(self, event: Event) -> FilterResult:
        if event.event_type != EventType.CHAT_MESSAGE:
            return FilterResult.allow(event)
        message = event.message or ""
        cleaned = "".join(
            char for char in message if unicodedata.category(char) != "Cc" or char in "\n\t"
        )
        return FilterResult.allow(event.model_copy(update={"message": cleaned}))

