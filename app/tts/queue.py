import asyncio
import logging
import re
import time
import unicodedata
from collections import deque
from html.parser import HTMLParser

from app.events.bus import EventBus
from app.events.models import Event, EventType
from app.storage.settings import RuntimeSettings
from app.tts.base import TTSEngine

logger = logging.getLogger(__name__)


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def sanitize_text(text: str) -> str:
    """Reduce user-controlled markup to a single line of plain text."""
    parser = _PlainTextParser()
    try:
        parser.feed(text)
        parser.close()
        plain = " ".join(parser.parts)
    except Exception:
        plain = text
    plain = plain.replace("<", " ").replace(">", " ")
    plain = "".join(
        character
        for character in plain
        if not unicodedata.category(character).startswith("C") or character.isspace()
    )
    return re.sub(r"\s+", " ", plain).strip()


class TTSQueueWorker:
    def __init__(
        self,
        bus: EventBus,
        engine: TTSEngine,
        settings: RuntimeSettings,
    ) -> None:
        self.bus = bus
        self.engine = engine
        self.settings = settings
        self._pending: deque[str] = deque()
        self._pending_event = asyncio.Event()
        self._event_queue: asyncio.Queue[Event] | None = None
        self._listener_task: asyncio.Task[None] | None = None
        self._speaker_task: asyncio.Task[None] | None = None
        self._current_speech: asyncio.Task[None] | None = None
        self._last_spoken_by_user: dict[str, float] = {}
        self._running = False

    @property
    def queue_size(self) -> int:
        return len(self._pending)

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self.settings.tts_enabled:
            self._start_speaker()
            await self._subscribe()

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        await self._unsubscribe()
        await self.clear()
        await self._stop_speaker()

    async def update_settings(self, settings: RuntimeSettings) -> None:
        was_enabled = self.settings.tts_enabled
        self.settings = settings
        while len(self._pending) > settings.tts_queue_max:
            self._pending.popleft()
        if not self._pending:
            self._pending_event.clear()
        if not self._running:
            return
        if settings.tts_enabled and not was_enabled:
            self._start_speaker()
            await self._subscribe()
        elif was_enabled and not settings.tts_enabled:
            await self._unsubscribe()
            await self.clear()
            await self._stop_speaker()

    def _start_speaker(self) -> None:
        if self._speaker_task is None:
            self._speaker_task = asyncio.create_task(
                self._speaker_loop(), name="tts-speaker"
            )

    async def _stop_speaker(self) -> None:
        if self._speaker_task is not None:
            self._speaker_task.cancel()
            await asyncio.gather(self._speaker_task, return_exceptions=True)
            self._speaker_task = None

    async def _subscribe(self) -> None:
        if self._event_queue is not None:
            return
        self._event_queue = await self.bus.subscribe()
        self._listener_task = asyncio.create_task(
            self._listen_for_events(), name="tts-event-listener"
        )

    async def _unsubscribe(self) -> None:
        listener = self._listener_task
        self._listener_task = None
        if listener is not None:
            listener.cancel()
            await asyncio.gather(listener, return_exceptions=True)
        event_queue = self._event_queue
        self._event_queue = None
        if event_queue is not None:
            await self.bus.unsubscribe(event_queue)

    async def _listen_for_events(self) -> None:
        queue = self._event_queue
        if queue is None:
            return
        while True:
            event = await queue.get()
            if event.event_type != EventType.CHAT_MESSAGE or event.message is None:
                continue
            now = time.monotonic()
            last_spoken = self._last_spoken_by_user.get(event.user.user_id)
            if (
                last_spoken is not None
                and now - last_spoken < self.settings.tts_user_cooldown_seconds
            ):
                continue
            text = event.message
            if self.settings.read_username:
                text = f"{event.user.display_name}: {text}"
            text = self._prepare(text)
            if not text:
                continue
            self._last_spoken_by_user[event.user.user_id] = now
            self._enqueue(text)

    def _prepare(self, text: str) -> str:
        return sanitize_text(text)[: self.settings.tts_max_length].rstrip()

    def _enqueue(self, text: str) -> None:
        max_size = self.settings.tts_queue_max
        while len(self._pending) >= max_size:
            self._pending.popleft()
        self._pending.append(text)
        self._pending_event.set()

    def enqueue_test(self, text: str) -> bool:
        prepared = self._prepare(text)
        if not prepared:
            return False
        self._enqueue(prepared)
        return True

    async def clear(self) -> None:
        self._pending.clear()
        self._pending_event.clear()
        current = self._current_speech
        if current is not None and not current.done():
            current.cancel()
        self._safe_engine_stop()
        if current is not None:
            await asyncio.gather(current, return_exceptions=True)

    def _safe_engine_stop(self) -> None:
        try:
            self.engine.stop()
        except Exception:
            logger.exception("TTS engine failed while stopping playback")

    async def _speaker_loop(self) -> None:
        while True:
            await self._pending_event.wait()
            if not self._pending:
                self._pending_event.clear()
                continue
            text = self._pending.popleft()
            if not self._pending:
                self._pending_event.clear()
            settings = self.settings
            speech = asyncio.create_task(
                self.engine.speak(
                    text,
                    settings.tts_voice,
                    0,
                    settings.tts_volume,
                    settings.tts_device,
                )
            )
            self._current_speech = speech
            try:
                await asyncio.wait_for(speech, timeout=settings.tts_timeout_seconds)
            except TimeoutError:
                self._safe_engine_stop()
            except asyncio.CancelledError:
                if asyncio.current_task() and asyncio.current_task().cancelling():
                    speech.cancel()
                    raise
                # clear() deliberately cancels only the current utterance.
            except Exception:
                logger.exception("TTS engine failed while speaking")
            finally:
                if self._current_speech is speech:
                    self._current_speech = None
