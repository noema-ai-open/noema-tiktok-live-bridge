from abc import ABC, abstractmethod
from typing import TypedDict


class VoiceInfo(TypedDict):
    id: str
    name: str


class TTSEngine(ABC):
    @abstractmethod
    async def speak(
        self,
        text: str,
        voice: str | None,
        rate: int,
        volume: int,
        device: str | None,
    ) -> None:
        """Speak plain text and return once playback has finished."""

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        """Return stable voice identifiers and display names."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the current utterance as quickly as possible."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this engine can be used on the current system."""
