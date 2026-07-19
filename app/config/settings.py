from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.config import defaults


class AppConfig(BaseSettings):
    """Process-level configuration loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="NOEMA_",
        extra="ignore",
    )

    port: int = Field(default=defaults.DEFAULT_PORT, ge=1, le=65535)
    mode: Literal["mock", "live", "fallback"] = defaults.DEFAULT_MODE
    mock_events_per_second: float = Field(
        default=defaults.DEFAULT_MOCK_EVENTS_PER_SECOND, gt=0, le=1000
    )
    database_path: Path = Path(defaults.DEFAULT_DATABASE_PATH)
    ring_buffer_size: int = Field(default=defaults.DEFAULT_RING_BUFFER_SIZE, ge=1, le=100_000)
    dedupe_window_seconds: float = Field(
        default=defaults.DEFAULT_DEDUPE_WINDOW_SECONDS, gt=0, le=3600
    )

