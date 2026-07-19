import time
from collections.abc import Callable

from app.events.models import Event, EventType
from app.filters.base import FilterResult


class UserCooldownFilter:
    def __init__(
        self,
        seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if seconds < 0:
            raise ValueError("seconds cannot be negative")
        self.seconds = seconds
        self._clock = clock
        self._last_seen: dict[str, float] = {}

    async def apply(self, event: Event) -> FilterResult:
        if event.event_type != EventType.CHAT_MESSAGE or self.seconds == 0:
            return FilterResult.allow(event)
        now = self._clock()
        last_seen = self._last_seen.get(event.user.user_id)
        if last_seen is not None and now - last_seen < self.seconds:
            return FilterResult.block(event, "user_cooldown")
        self._last_seen[event.user.user_id] = now
        return FilterResult.allow(event)

