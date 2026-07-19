import re

from app.events.models import Event, EventType
from app.filters.base import FilterResult


class URLFilter:
    _url = re.compile(
        r"(?i)(?:https?://|www\.)\S+|\b(?:[a-z0-9](?:[a-z0-9-]{0,62})\.)+"
        r"[a-z]{2,63}(?:/\S*)?"
    )

    async def apply(self, event: Event) -> FilterResult:
        if event.event_type == EventType.CHAT_MESSAGE and self._url.search(event.message or ""):
            return FilterResult.block(event, "url")
        return FilterResult.allow(event)
