from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

EventCallback = Callable[[Mapping[str, Any]], Awaitable[None]]


class BaseConnector(ABC):
    def __init__(self, on_event: EventCallback) -> None:
        self.on_event = on_event

    @property
    @abstractmethod
    def status(self) -> str: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

