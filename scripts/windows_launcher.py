"""Startprogramm für die installierte Windows-Version.

Arbeitsverzeichnis ist %LOCALAPPDATA%\\NOEMA\\TikTokBridge, damit Datenbank
und .env nie im Programmordner (schreibgeschützt) landen.
"""

import os
import shutil
import sys
import threading
import webbrowser
from pathlib import Path


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    directory = Path(base) / "NOEMA" / "TikTokBridge"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def main() -> None:
    data_dir = _data_dir()
    env_file = data_dir / ".env"
    if not env_file.exists():
        example = _bundle_root() / ".env.example"
        if example.exists():
            shutil.copyfile(example, env_file)
    os.chdir(data_dir)

    from app.config import AppConfig  # noqa: PLC0415 — erst nach chdir laden (.env)
    from app.main import create_app

    import uvicorn

    config = AppConfig()
    threading.Timer(
        1.5, webbrowser.open, args=(f"http://127.0.0.1:{config.port}/",)
    ).start()
    uvicorn.run(create_app(config), host="127.0.0.1", port=config.port)


if __name__ == "__main__":
    main()
