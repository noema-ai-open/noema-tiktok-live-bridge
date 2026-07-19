import time
from collections import defaultdict, deque
from collections.abc import Callable

from app.events.models import Event, EventType
from app.filters.base import FilterResult


class RepetitionSpamFilter:
    def __init__(
        self,
        max_repetitions: int = 2,
        window_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_repetitions < 1 or window_seconds <= 0:
            raise ValueError("invalid repetition filter limits")
        self.max_repetitions = max_repetitions
        self.window_seconds = window_seconds
        self._clock = clock
        self._messages: dict[str, deque[tuple[float, str]]] = defaultdict(deque)

    async def apply(self, event: Event) -> FilterResult:
        if event.event_type != EventType.CHAT_MESSAGE:
            return FilterResult.allow(event)
        now = self._clock()
        entries = self._messages[event.user.user_id]
        while entries and entries[0][0] < now - self.window_seconds:
            entries.popleft()
        normalized = " ".join((event.message or "").casefold().split())
        repetitions = sum(message == normalized for _, message in entries)
        if repetitions >= self.max_repetitions:
            return FilterResult.block(event, "repetition_spam")
        entries.append((now, normalized))
        return FilterResult.allow(event)

