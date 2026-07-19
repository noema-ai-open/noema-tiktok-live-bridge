from datetime import datetime, timezone

from app.storage.history import EventHistory
from app.storage.settings import SettingsStore, SettingsUpdate


def test_settings_store_has_defaults_and_persists_partial_update(tmp_path) -> None:
    path = tmp_path / "settings.sqlite3"
    store = SettingsStore(path)
    assert store.get().retention == "none"
    updated = store.update(SettingsUpdate(max_message_length=42, block_urls=False))
    assert updated.max_message_length == 42
    assert updated.block_urls is False
    assert updated.spam_max_repetitions == 2
    store.close()

    reopened = SettingsStore(path)
    assert reopened.get().max_message_length == 42
    reopened.close()


def test_history_none_does_not_persist_and_session_is_cleared(tmp_path, event_factory) -> None:
    path = tmp_path / "history.sqlite3"
    none_history = EventHistory(path, "none")
    none_history.append(event_factory())
    assert none_history.latest() == []
    none_history.close()

    session_history = EventHistory(path, "session")
    session_history.append(event_factory(event_id="session-event"))
    assert [event.event_id for event in session_history.latest()] == ["session-event"]
    session_history.close()

    reopened = EventHistory(path, "session")
    assert reopened.latest() == []
    reopened.close()

