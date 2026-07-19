"""Aktualisiert Schlüssel in der lokalen .env, ohne fremde Zeilen anzufassen."""

from pathlib import Path


def update_env_file(path: Path, values: dict[str, str]) -> None:
    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(values)
    for index, line in enumerate(lines):
        stripped = line.strip()
        key = stripped.lstrip("#").split("=", 1)[0].strip()
        if key in remaining and ("=" in stripped):
            lines[index] = f"{key}={remaining.pop(key)}"
    for key, value in remaining.items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
