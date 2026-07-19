import asyncio
import time

from app.events.models import Event


class EventDeduplicator:
    def __init__(self, window_seconds: float = 30.0) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.window_seconds = window_seconds
        self._seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def is_duplicate(self, event: Event) -> bool:
        now = time.monotonic()
        async with self._lock:
            cutoff = now - self.window_seconds
            expired = [event_id for event_id, seen_at in self._seen.items() if seen_at < cutoff]
            for event_id in expired:
                del self._seen[event_id]

            previous = self._seen.get(event.event_id)
            if previous is not None and now - previous <= self.window_seconds:
                return True
            self._seen[event.event_id] = now
            return False

    @property
    def tracked_count(self) -> int:
        return len(self._seen)

