import json
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retention: Literal["none", "session", "24h", "7d"] = "none"
    max_message_length: int = Field(default=500, ge=1, le=10_000)
    block_urls: bool = True
    blacklist_words: list[str] = Field(default_factory=list, max_length=500)
    whitelist_words: list[str] = Field(default_factory=list, max_length=500)
    spam_max_repetitions: int = Field(default=2, ge=1, le=100)
    spam_window_seconds: float = Field(default=30.0, gt=0, le=3600)
    user_cooldown_seconds: float = Field(default=0.0, ge=0, le=3600)


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    retention: Literal["none", "session", "24h", "7d"] | None = None
    max_message_length: int | None = Field(default=None, ge=1, le=10_000)
    block_urls: bool | None = None
    blacklist_words: list[str] | None = Field(default=None, max_length=500)
    whitelist_words: list[str] | None = Field(default=None, max_length=500)
    spam_max_repetitions: int | None = Field(default=None, ge=1, le=100)
    spam_window_seconds: float | None = Field(default=None, gt=0, le=3600)
    user_cooldown_seconds: float | None = Field(default=None, ge=0, le=3600)


class SettingsStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._lock = RLock()
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self._connection.commit()
        self._ensure_defaults()

    def _ensure_defaults(self) -> None:
        defaults = RuntimeSettings().model_dump()
        with self._lock:
            self._connection.executemany(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                [(key, json.dumps(value)) for key, value in defaults.items()],
            )
            self._connection.commit()

    def get(self) -> RuntimeSettings:
        with self._lock:
            rows = self._connection.execute("SELECT key, value FROM settings").fetchall()
        values = {key: json.loads(value) for key, value in rows}
        return RuntimeSettings.model_validate(values)

    def update(self, update: SettingsUpdate) -> RuntimeSettings:
        changes = update.model_dump(exclude_none=True)
        current = self.get()
        validated = RuntimeSettings.model_validate({**current.model_dump(), **changes})
        with self._lock:
            self._connection.executemany(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                [(key, json.dumps(value)) for key, value in changes.items()],
            )
            self._connection.commit()
        return validated

    def close(self) -> None:
        with self._lock:
            self._connection.close()

