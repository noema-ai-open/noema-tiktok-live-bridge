from __future__ import annotations

import asyncio
import logging

import httpx

from app.tts.base import TTSError, VoiceInfo
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
            raise TTSError("Deepgram-TTS nicht einsatzbereit: API-Schlüssel fehlt")
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
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            hint = ""
            if status in (401, 403):
                hint = " — API-Schlüssel ungültig oder ohne Berechtigung"
            elif status == 400:
                hint = " — Stimme/Modellkennung prüfen (z. B. aura-2-thalia-en)"
            raise TTSError(f"Deepgram-TTS: HTTP {status}{hint}") from exc
        except httpx.HTTPError as exc:
            raise TTSError(
                f"Deepgram-TTS nicht erreichbar ({type(exc).__name__})"
            ) from exc
        except Exception as exc:
            logger.exception("Deepgram TTS client failed unexpectedly")
            raise TTSError("Deepgram-TTS: unerwarteter Fehler (siehe Log)") from exc

        if not response.content:
            raise TTSError("Deepgram-TTS: Anbieter lieferte leeres Audio")
        content_type = response.headers.get("content-type", "audio/wav")
        content_type = content_type.partition(";")[0].lower()
        try:
            await self._play(response.content, content_type)
        except (asyncio.CancelledError, TTSError):
            raise
        except Exception as exc:
            logger.exception("Deepgram TTS audio playback failed")
            raise TTSError("Deepgram-TTS: Wiedergabe fehlgeschlagen (siehe Log)") from exc
