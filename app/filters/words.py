import re
from collections.abc import Iterable

from app.events.models import Event, EventType
from app.filters.base import FilterResult


class WordListFilter:
    """Block blacklist terms; explicit whitelist terms exempt an otherwise matching message."""

    def __init__(
        self,
        blacklist: Iterable[str] = (),
        whitelist: Iterable[str] = (),
    ) -> None:
        self.blacklist = {word.casefold().strip() for word in blacklist if word.strip()}
        self.whitelist = {word.casefold().strip() for word in whitelist if word.strip()}

    @staticmethod
    def _terms(message: str) -> set[str]:
        return set(re.findall(r"\w+", message.casefold(), flags=re.UNICODE))

    async def apply(self, event: Event) -> FilterResult:
        if event.event_type != EventType.CHAT_MESSAGE:
            return FilterResult.allow(event)
        terms = self._terms(event.message or "")
        if terms & self.whitelist:
            return FilterResult.allow(event)
        if terms & self.blacklist:
            return FilterResult.block(event, "blacklist")
        return FilterResult.allow(event)

