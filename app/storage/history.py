import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Literal
from uuid import uuid4

from app.events.models import Event

RetentionMode = Literal["none", "session", "24h", "7d"]


class EventHistory:
    def __init__(self, database_path: str | Path, retention: RetentionMode = "none") -> None:
        self.retention = retention
        self._session_id = str(uuid4())
        self._lock = RLock()
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS event_history (
                event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        self.cleanup()

    def set_retention(self, retention: RetentionMode) -> None:
        self.retention = retention
        self.cleanup()

    def append(self, event: Event) -> None:
        if self.retention == "none":
            return
        with self._lock:
            self._connection.execute(
                "INSERT INTO event_history(event_id, timestamp, session_id, payload) "
                "VALUES (?, ?, ?, ?)",
                (
                    event.event_id,
                    event.timestamp.isoformat(),
                    self._session_id,
                    json.dumps(event.json_payload()),
                ),
            )
            self._connection.commit()
        self.cleanup()

    def cleanup(self) -> None:
        with self._lock:
            if self.retention == "none":
                self._connection.execute("DELETE FROM event_history")
            elif self.retention == "session":
                self._connection.execute(
                    "DELETE FROM event_history WHERE session_id != ?", (self._session_id,)
                )
            else:
                duration = timedelta(hours=24) if self.retention == "24h" else timedelta(days=7)
                cutoff = (datetime.now(timezone.utc) - duration).isoformat()
                self._connection.execute(
                    "DELETE FROM event_history WHERE timestamp < ?", (cutoff,)
                )
            self._connection.commit()

    def latest(self, limit: int = 100) -> list[Event]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM event_history ORDER BY rowid DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Event.model_validate(json.loads(payload)) for (payload,) in reversed(rows)]

    def close(self) -> None:
        with self._lock:
            if self.retention == "session":
                self._connection.execute(
                    "DELETE FROM event_history WHERE session_id = ?", (self._session_id,)
                )
                self._connection.commit()
            self._connection.close()
