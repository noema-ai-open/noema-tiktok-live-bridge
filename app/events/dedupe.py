import asyncio
import time

from app.events.models import Event, EventType


class EventDeduplicator:
    def __init__(
        self,
        window_seconds: float = 30.0,
        chat_replay_window_seconds: float = 300.0,
    ) -> None:
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if chat_replay_window_seconds <= 0:
            raise ValueError("chat_replay_window_seconds must be positive")
        self.window_seconds = window_seconds
        self.chat_replay_window_seconds = chat_replay_window_seconds
        self._seen: dict[str, tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    def _key_and_window(self, event: Event) -> tuple[str, float]:
        if event.event_type == EventType.CHAT_MESSAGE:
            normalized_message = " ".join((event.message or "").split()).casefold()
            return (
                f"chat:{event.user.user_id}:{normalized_message}",
                self.chat_replay_window_seconds,
            )
        return f"event:{event.event_id}", self.window_seconds

    async def is_duplicate(self, event: Event) -> bool:
        now = time.monotonic()
        key, active_window = self._key_and_window(event)
        async with self._lock:
            expired = [
                seen_key
                for seen_key, (seen_at, window) in self._seen.items()
                if now - seen_at > window
            ]
            for seen_key in expired:
                del self._seen[seen_key]

            previous = self._seen.get(key)
            if previous is not None and now - previous[0] <= previous[1]:
                return True
            self._seen[key] = (now, active_window)
            return False

    @property
    def tracked_count(self) -> int:
        return len(self._seen)
