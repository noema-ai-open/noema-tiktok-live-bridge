import asyncio

from app.tts.base import TTSEngine, VoiceInfo


class DummyEngine(TTSEngine):
    """In-memory TTS engine used for tests and non-Windows fallback."""

    def __init__(self, duration: float | None = 0.0) -> None:
        self.duration = duration
        self.spoken_texts: list[str] = []
        self.spoken = self.spoken_texts
        self.calls: list[dict[str, object]] = []
        self.stop_count = 0
        self._stop_event: asyncio.Event | None = None

    async def speak(
        self,
        text: str,
        voice: str | None,
        rate: int,
        volume: int,
        device: str | None,
    ) -> None:
        self.spoken_texts.append(text)
        self.calls.append(
            {
                "text": text,
                "voice": voice,
                "rate": rate,
                "volume": volume,
                "device": device,
            }
        )
        stop_event = asyncio.Event()
        self._stop_event = stop_event
        try:
            if self.duration is None:
                await stop_event.wait()
            elif self.duration > 0:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.duration)
                except TimeoutError:
                    pass
        finally:
            if self._stop_event is stop_event:
                self._stop_event = None

    def list_voices(self) -> list[VoiceInfo]:
        return [{"id": "dummy", "name": "Dummy Voice"}]

    def stop(self) -> None:
        self.stop_count += 1
        if self._stop_event is not None:
            self._stop_event.set()

    def is_available(self) -> bool:
        return True
