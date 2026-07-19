from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.events.bus import EventBus
from app.events.dedupe import EventDeduplicator
from app.events.models import Event
from app.events.normalizer import EventNormalizer
from app.filters.chain import FilterChain
from app.storage.history import EventHistory


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    accepted: bool
    event: Event
    reason: str | None = None


class EventPipeline:
    def __init__(
        self,
        normalizer: EventNormalizer,
        deduplicator: EventDeduplicator,
        filter_chain: FilterChain,
        bus: EventBus,
        history: EventHistory,
        ring_buffer_size: int = 500,
    ) -> None:
        self.normalizer = normalizer
        self.deduplicator = deduplicator
        self.filter_chain = filter_chain
        self.bus = bus
        self.history = history
        self.ring_buffer: deque[Event] = deque(maxlen=ring_buffer_size)

    async def process(self, raw: Event | Mapping[str, Any]) -> ProcessingResult:
        event = self.normalizer.normalize(raw)
        if await self.deduplicator.is_duplicate(event):
            return ProcessingResult(False, event, "duplicate")
        filtered = await self.filter_chain.apply(event)
        if not filtered.allowed:
            return ProcessingResult(False, filtered.event, filtered.reason)

        event = filtered.event
        self.ring_buffer.append(event)
        self.history.append(event)
        await self.bus.publish(event)
        return ProcessingResult(True, event)

    def latest(self, limit: int) -> list[Event]:
        if limit <= 0:
            return []
        return list(self.ring_buffer)[-limit:]

