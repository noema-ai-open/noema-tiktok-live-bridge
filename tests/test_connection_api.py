from pathlib import Path

from fastapi.testclient import TestClient

from app.config import AppConfig
from app.main import create_app


def _make_app(tmp_path: Path, mode: str = "mock"):
    return create_app(
        AppConfig(mode=mode, tts_engine="dummy", database_path=tmp_path / "c.sqlite3")
    )


def test_get_connection_defaults(tmp_path):
    with TestClient(_make_app(tmp_path)) as client:
        data = client.get("/connection").json()
        assert data["mode"] == "mock"
        assert data["has_deepgram_key"] is False


def test_post_connection_switches_mode_and_persists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with TestClient(_make_app(tmp_path)) as client:
        response = client.post(
            "/connection",
            json={
                "mode": "fallback",
                "tiktok_username": "@Testname",
                "tts_engine": "dummy",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["mode"] == "fallback"
        assert data["tiktok_username"] == "Testname"
        env_text = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "NOEMA_MODE=fallback" in env_text
        assert "NOEMA_TIKTOK_USERNAME=Testname" in env_text
        assert client.get("/status").json()["mode"] == "fallback"


def test_post_connection_rejects_unknown_fields(tmp_path):
    with TestClient(_make_app(tmp_path)) as client:
        response = client.post("/connection", json={"mode": "mock", "evil": "x"})
        assert response.status_code == 422
