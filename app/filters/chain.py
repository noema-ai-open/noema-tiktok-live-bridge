from collections.abc import Iterable

from app.events.models import Event
from app.filters.base import EventFilter, FilterResult


class FilterChain:
    def __init__(self, filters: Iterable[EventFilter] = ()) -> None:
        self.filters = list(filters)

    async def apply(self, event: Event) -> FilterResult:
        current = event
        for event_filter in self.filters:
            result = await event_filter.apply(current)
            if not result.allowed:
                return result
            current = result.event
        return FilterResult.allow(current)


__all__ = ["FilterChain", "FilterResult"]

