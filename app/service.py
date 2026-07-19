from collections.abc import Mapping
from typing import TYPE_CHECKING
from pathlib import Path
from typing import Any

from app.config import defaults
from app.config.settings import AppConfig
from app.connectors.base import BaseConnector
from app.connectors.mock import MockConnector
from app.connectors.tiktok_live import TikTokLiveConnector
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
from app.tts.base import TTSEngine
from app.tts.dummy import DummyEngine
from app.tts.external import ExternalTTSEngine
from app.tts.queue import TTSQueueWorker
from app.tts.sapi import SAPIEngine

if TYPE_CHECKING:
    from app.api.schemas import ConnectionUpdate


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
        self.tts_engine = self._build_tts_engine(config.tts_engine, config)
        self.tts_worker = TTSQueueWorker(self.bus, self.tts_engine, runtime)
        self._started = False
        self.connector: BaseConnector | None = self._build_connector(config)

    def _build_connector(self, config: AppConfig) -> BaseConnector | None:
        if config.mode == "mock":
            return MockConnector(
                on_event=self._on_connector_event,
                events_per_second=config.mock_events_per_second,
            )
        if config.mode == "live":
            return TikTokLiveConnector(
                on_event=self._on_connector_event,
                username=config.tiktok_username,
                eulerstream_api_key=(
                    config.eulerstream_api_key.get_secret_value()
                    if config.eulerstream_api_key
                    else None
                ),
                live_offline_poll_seconds=config.live_offline_poll_seconds,
            )
        return None

    @staticmethod
    def _build_tts_engine(
        configured_engine: str, config: AppConfig | None = None
    ) -> TTSEngine:
        if configured_engine == "dummy":
            return DummyEngine()
        if configured_engine == "deepgram":
            from app.tts.deepgram import DeepgramTTSEngine

            return DeepgramTTSEngine(
                api_key=(
                    config.deepgram_api_key.get_secret_value()
                    if config and config.deepgram_api_key
                    else None
                ),
                player_command=config.external_tts_player_command if config else None,
            )
        if configured_engine == "external":
            return ExternalTTSEngine(
                api_key=(
                    config.external_tts_api_key.get_secret_value()
                    if config and config.external_tts_api_key
                    else None
                ),
                base_url=config.external_tts_base_url if config else None,
                model=(
                    config.external_tts_model
                    if config
                    else defaults.DEFAULT_EXTERNAL_TTS_MODEL
                ),
                player_command=config.external_tts_player_command if config else None,
            )
        sapi = SAPIEngine()
        if sapi.is_available():
            return sapi
        return DummyEngine()

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
        self._started = True
        await self.tts_worker.start()
        if self.connector is not None:
            await self.connector.connect()

    async def stop(self) -> None:
        self._started = False
        if self.connector is not None:
            await self.connector.disconnect()
        await self.tts_worker.stop()
        self.history.close()
        self.settings_store.close()

    async def apply_connection(self, update: "ConnectionUpdate") -> None:
        """Übernimmt Verbindungs-Einstellungen aus der UI und persistiert sie in .env."""
        config = self.config
        if update.mode is not None:
            config.mode = update.mode
        if update.tiktok_username is not None:
            config.tiktok_username = update.tiktok_username.strip().lstrip("@") or None
        if update.tts_engine is not None:
            config.tts_engine = update.tts_engine
        from pydantic import SecretStr

        if update.deepgram_api_key:
            config.deepgram_api_key = SecretStr(update.deepgram_api_key.strip())
        if update.eulerstream_api_key:
            config.eulerstream_api_key = SecretStr(update.eulerstream_api_key.strip())
        if update.external_tts_base_url is not None:
            config.external_tts_base_url = update.external_tts_base_url.strip() or None
        if update.external_tts_model:
            config.external_tts_model = update.external_tts_model.strip()
        if update.external_tts_api_key:
            config.external_tts_api_key = SecretStr(update.external_tts_api_key.strip())
        if update.tts_voice is not None:
            from app.storage.settings import SettingsUpdate as RuntimeUpdate

            await self.update_settings(
                RuntimeUpdate(tts_voice=update.tts_voice.strip() or None)
            )

        old = self.connector
        self.connector = None
        if old is not None:
            await old.disconnect()
        self.connector = self._build_connector(config)
        if self.connector is not None and self._started:
            await self.connector.connect()

        self.tts_engine = self._build_tts_engine(config.tts_engine, config)
        self.tts_worker.engine = self.tts_engine

        from app.storage.envfile import update_env_file

        values = {
            "NOEMA_MODE": config.mode,
            "NOEMA_TIKTOK_USERNAME": config.tiktok_username or "",
            "NOEMA_TTS_ENGINE": config.tts_engine,
        }
        if update.deepgram_api_key:
            values["DEEPGRAM_API_KEY"] = config.deepgram_api_key.get_secret_value()
        if update.eulerstream_api_key:
            values["NOEMA_EULERSTREAM_API_KEY"] = (
                config.eulerstream_api_key.get_secret_value()
            )
        if update.external_tts_base_url is not None:
            values["EXTERNAL_TTS_BASE_URL"] = config.external_tts_base_url or ""
        if update.external_tts_model:
            values["EXTERNAL_TTS_MODEL"] = config.external_tts_model
        if update.external_tts_api_key:
            values["EXTERNAL_TTS_API_KEY"] = (
                config.external_tts_api_key.get_secret_value()
            )
        update_env_file(Path(".env"), values)

    def connection_payload(self) -> dict[str, object]:
        return {
            "mode": self.config.mode,
            "tiktok_username": self.config.tiktok_username,
            "tts_engine": self.config.tts_engine,
            "has_deepgram_key": self.config.deepgram_api_key is not None,
            "has_eulerstream_key": self.config.eulerstream_api_key is not None,
            "has_external_key": self.config.external_tts_api_key is not None,
            "external_tts_base_url": self.config.external_tts_base_url,
            "external_tts_model": self.config.external_tts_model,
            "tts_voice": self.settings_store.get().tts_voice,
            "tts_engine_available": self.tts_engine.is_available(),
        }

    async def update_settings(self, update: SettingsUpdate) -> RuntimeSettings:
        settings = self.settings_store.update(update)
        self.history.set_retention(settings.retention)
        self.pipeline.filter_chain = self._build_filter_chain(settings)
        await self.tts_worker.update_settings(settings)
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
