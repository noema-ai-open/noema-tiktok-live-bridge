from app.events.models import Event, EventType
from app.filters.base import FilterResult


class MaxLengthFilter:
    def __init__(self, max_length: int = 500) -> None:
        if max_length < 1:
            raise ValueError("max_length must be positive")
        self.max_length = max_length

    async def apply(self, event: Event) -> FilterResult:
        is_too_long = (
            event.event_type == EventType.CHAT_MESSAGE
            and len(event.message or "") > self.max_length
        )
        if is_too_long:
            return FilterResult.block(event, "max_length")
        return FilterResult.allow(event)
