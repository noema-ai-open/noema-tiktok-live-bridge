import asyncio
import random
from datetime import datetime, timezone
from itertools import cycle
from uuid import uuid4

from app.connectors.base import BaseConnector, EventCallback
from app.events.models import EventType


class MockConnector(BaseConnector):
    """Offline connector that continuously emits representative fake events."""

    def __init__(
        self,
        on_event: EventCallback,
        events_per_second: float = 1.0,
        seed: int | None = None,
    ) -> None:
        super().__init__(on_event)
        if events_per_second <= 0:
            raise ValueError("events_per_second must be positive")
        self.events_per_second = events_per_second
        self._random = random.Random(seed)
        event_types = list(EventType)
        self._random.shuffle(event_types)
        self._event_types = cycle(event_types)
        self._task: asyncio.Task[None] | None = None
        self._connected = False

    @property
    def status(self) -> str:
        return "connected" if self._connected else "disconnected"

    async def connect(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._connected = True
        self._task = asyncio.create_task(self._run(), name="mock-connector")

    async def disconnect(self) -> None:
        self._connected = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        interval = 1.0 / self.events_per_second
        try:
            while self._connected:
                await self.on_event(self._make_event(next(self._event_types)))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise
        finally:
            self._connected = False

    def _make_event(self, event_type: EventType) -> dict[str, object]:
        number = self._random.randint(1, 9999)
        event: dict[str, object] = {
            "event_type": event_type.value,
            "event_id": f"mock-{uuid4()}",
            "timestamp": datetime.now(timezone.utc),
            "user": {
                "display_name": f"Viewer {number}",
                "user_id": f"mock-user-{number}",
                "is_moderator": self._random.random() < 0.05,
                "is_subscriber": self._random.random() < 0.25,
            },
            "metadata": {"simulated": True},
        }
        if event_type == EventType.CHAT_MESSAGE:
            event["message"] = self._random.choice(
                ["Hello!", "Great stream", "Nice to be here", "👏👏👏"]
            )
        elif event_type == EventType.LIKE:
            event["metadata"] = {"simulated": True, "like_count": self._random.randint(1, 20)}
        elif event_type == EventType.GIFT:
            event["metadata"] = {"simulated": True, "gift_name": "Mock Rose", "count": 1}
        return event

