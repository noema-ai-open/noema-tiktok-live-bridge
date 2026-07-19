from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.config.settings import AppConfig
from app.connectors.base import BaseConnector
from app.connectors.mock import MockConnector
from app.events.bus import EventBus
from app.events.dedupe import EventDeduplicator
from app.events.normalizer import EventNormalizer
from app.filters.chain import FilterChain
from app.filters.control_chars import ControlCharacterFilter
from app.filters.cooldown import UserCooldownFilter
from app.filters.max_length import MaxLengthFilter
from app.filters.repetition import RepetitionSpamFilter
from app.filters.url import URLFilter
from app.filters.words import WordListFilter
from app.pipeline import EventPipeline, ProcessingResult
from app.storage.history import EventHistory
from app.storage.settings import RuntimeSettings, SettingsStore, SettingsUpdate


class BridgeService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        Path(config.database_path).parent.mkdir(parents=True, exist_ok=True)
        self.settings_store = SettingsStore(config.database_path)
        runtime = self.settings_store.get()
        self.history = EventHistory(config.database_path, runtime.retention)
        self.bus = EventBus()
        self.pipeline = EventPipeline(
            normalizer=EventNormalizer(),
            deduplicator=EventDeduplicator(config.dedupe_window_seconds),
            filter_chain=self._build_filter_chain(runtime),
            bus=self.bus,
            history=self.history,
            ring_buffer_size=config.ring_buffer_size,
        )
        self.connector: BaseConnector | None = None
        if config.mode == "mock":
            self.connector = MockConnector(
                on_event=self._on_connector_event,
                events_per_second=config.mock_events_per_second,
            )

    @staticmethod
    def _build_filter_chain(settings: RuntimeSettings) -> FilterChain:
        filters = [ControlCharacterFilter()]
        if settings.block_urls:
            filters.append(URLFilter())
        filters.extend(
            [
                MaxLengthFilter(settings.max_message_length),
                WordListFilter(settings.blacklist_words, settings.whitelist_words),
                RepetitionSpamFilter(
                    settings.spam_max_repetitions, settings.spam_window_seconds
                ),
                UserCooldownFilter(settings.user_cooldown_seconds),
            ]
        )
        return FilterChain(filters)

    async def _on_connector_event(self, raw: Mapping[str, Any]) -> None:
        await self.pipeline.process(raw)

    async def start(self) -> None:
        if self.connector is not None:
            await self.connector.connect()

    async def stop(self) -> None:
        if self.connector is not None:
            await self.connector.disconnect()
        self.history.close()
        self.settings_store.close()

    async def update_settings(self, update: SettingsUpdate) -> RuntimeSettings:
        settings = self.settings_store.update(update)
        self.history.set_retention(settings.retention)
        self.pipeline.filter_chain = self._build_filter_chain(settings)
        return settings

    async def process_fallback(self, raw: dict[str, object]) -> ProcessingResult:
        return await self.pipeline.process(raw)

    def status_payload(self) -> dict[str, object]:
        connector_status = self.connector.status if self.connector is not None else "unavailable"
        return {
            "mode": self.config.mode,
            "connector_status": connector_status,
            "queue_lengths": {
                "subscribers": self.bus.queue_lengths,
                "ring_buffer": len(self.pipeline.ring_buffer),
            },
        }
