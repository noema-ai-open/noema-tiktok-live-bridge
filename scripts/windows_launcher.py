r"""Startprogramm für die installierte Windows-Version.

Arbeitsverzeichnis ist %LOCALAPPDATA%\NOEMA\TikTokBridge, damit Datenbank
und .env nie im Programmordner (schreibgeschützt) landen.
"""

import os
import shutil
import sys
import threading
import webbrowser
from pathlib import Path
from typing import TextIO


def _data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    directory = Path(base) / "NOEMA" / "TikTokBridge"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def _ensure_output_streams(data_dir: Path) -> TextIO | None:
    """Ersetzt fehlende Konsolen-Streams durch eine lokale UTF-8-Logdatei.

    PyInstaller setzt bei ``--noconsole`` unter Windows ``sys.stdout`` und
    ``sys.stderr`` auf ``None``. Uvicorn prüft diese Streams beim Aufbau seiner
    Logger mit ``isatty()`` und würde ohne Ersatz bereits vor dem Serverstart
    abbrechen.
    """

    if sys.stdout is not None and sys.stderr is not None:
        return None

    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stream = (log_dir / "bridge.log").open(
        "a", encoding="utf-8", buffering=1, errors="backslashreplace"
    )
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
    return stream


def main() -> None:
    data_dir = _data_dir()
    _ensure_output_streams(data_dir)

    env_file = data_dir / ".env"
    if not env_file.exists():
        example = _bundle_root() / ".env.example"
        if example.exists():
            shutil.copyfile(example, env_file)
    os.chdir(data_dir)

    from app.config import AppConfig  # noqa: PLC0415 — erst nach chdir laden (.env)
    from app.main import create_app
    from app.version import __version__

    import uvicorn

    config = AppConfig()
    frontend_url = f"http://127.0.0.1:{config.port}/?v={__version__}"
    threading.Timer(1.5, webbrowser.open, args=(frontend_url,)).start()
    uvicorn.run(
        create_app(config),
        host="127.0.0.1",
        port=config.port,
        use_colors=False,
    )


if __name__ == "__main__":
    main()
