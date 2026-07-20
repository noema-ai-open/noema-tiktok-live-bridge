import asyncio
from dataclasses import dataclass
from typing import Any

from app.events.models import Event


@dataclass(frozen=True, slots=True)
class BlockedBroadcast:
    reason: str
    event: Event

    def json_payload(self) -> dict[str, Any]:
        return {
            "type": "blocked",
            "reason": self.reason,
            "event": self.event.json_payload(),
        }


@dataclass(frozen=True, slots=True)
class SystemNotice:
    text: str

    def json_payload(self) -> dict[str, Any]:
        return {"type": "system", "text": self.text}


BusEvent = Event | BlockedBroadcast | SystemNotice


class EventBus:
    def __init__(self, subscriber_queue_size: int = 100) -> None:
        self.subscriber_queue_size = subscriber_queue_size
        self._subscribers: dict[asyncio.Queue[BusEvent], bool] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self, *, include_blocked: bool = False
    ) -> asyncio.Queue[BusEvent]:
        queue: asyncio.Queue[BusEvent] = asyncio.Queue(
            maxsize=self.subscriber_queue_size
        )
        async with self._lock:
            self._subscribers[queue] = include_blocked
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[BusEvent]) -> None:
        async with self._lock:
            self._subscribers.pop(queue, None)

    async def publish(self, event: Event) -> None:
        async with self._lock:
            subscribers = tuple(self._subscribers)
        self._broadcast(subscribers, event)

    async def publish_blocked(self, event: Event, reason: str) -> None:
        broadcast = BlockedBroadcast(reason=reason, event=event)
        async with self._lock:
            subscribers = tuple(
                queue
                for queue, include_blocked in self._subscribers.items()
                if include_blocked
            )
        self._broadcast(subscribers, broadcast)

    async def publish_system(self, text: str) -> None:
        # Nur an UI-Abonnenten (include_blocked), nicht in die TTS-Pipeline.
        notice = SystemNotice(text=text)
        async with self._lock:
            subscribers = tuple(
                queue
                for queue, include_blocked in self._subscribers.items()
                if include_blocked
            )
        self._broadcast(subscribers, notice)

    @staticmethod
    def _broadcast(
        subscribers: tuple[asyncio.Queue[BusEvent], ...], message: BusEvent
    ) -> None:
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(message)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def queue_lengths(self) -> list[int]:
        return [queue.qsize() for queue in self._subscribers]
