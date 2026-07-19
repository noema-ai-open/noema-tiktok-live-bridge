from __future__ import annotations

import asyncio
import logging

import httpx

from app.tts.base import VoiceInfo
from app.tts.external import ExternalTTSEngine

logger = logging.getLogger(__name__)

DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"

# Auswahl gängiger Aura-Stimmen; das Feld ist Freitext, jede gültige
# Deepgram-Modellkennung funktioniert.
KNOWN_VOICES = [
    "aura-2-thalia-en",
    "aura-2-andromeda-en",
    "aura-asteria-en",
    "aura-orion-en",
]


class DeepgramTTSEngine(ExternalTTSEngine):
    """Deepgram-Aura-Adapter (eigenes API-Format, kein OpenAI-Schema).

    Fordert WAV (linear16) an, damit die Wiedergabe unter Windows ohne
    zusätzlichen Player über winsound funktioniert.
    """

    def __init__(self, *, api_key: str | None, player_command: str | None = None) -> None:
        super().__init__(
            api_key=api_key,
            base_url=DEEPGRAM_SPEAK_URL,
            model="",
            player_command=player_command,
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

    def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        return [{"id": voice, "name": voice} for voice in KNOWN_VOICES]

    async def speak(
        self,
        text: str,
        voice: str | None,
        rate: int,
        volume: int,
        device: str | None,
    ) -> None:
        if not self.is_available():
            logger.error("Deepgram TTS is unavailable: API key is missing")
            return
        params = {
            "model": voice or KNOWN_VOICES[0],
            "encoding": "linear16",
            "container": "wav",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    DEEPGRAM_SPEAK_URL,
                    params=params,
                    headers={"Authorization": f"Token {self.api_key}"},
                    json={"text": text},
                )
                response.raise_for_status()
        except asyncio.CancelledError:
            raise
        except httpx.HTTPError as exc:
            logger.error("Deepgram TTS request failed (%s)", type(exc).__name__)
            return
        except Exception:
            logger.exception("Deepgram TTS client failed unexpectedly")
            return

        if not response.content:
            logger.error("Deepgram TTS returned empty audio")
            return
        content_type = response.headers.get("content-type", "audio/wav")
        content_type = content_type.partition(";")[0].lower()
        try:
            await self._play(response.content, content_type)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Deepgram TTS audio playback failed")
