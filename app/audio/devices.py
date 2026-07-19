from typing import TypedDict

from app.tts.sapi import SAPIEngine


class AudioDevice(TypedDict):
    id: str
    name: str


def list_audio_devices() -> list[AudioDevice]:
    """List SAPI output devices; token IDs remain stable across API calls."""
    return SAPIEngine.list_audio_outputs()
