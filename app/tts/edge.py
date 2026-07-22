from __future__ import annotations

import logging

from app.tts.base import TTSError, VoiceInfo
from app.tts.external import ExternalTTSEngine

logger = logging.getLogger(__name__)

# Eigener, rechtlich neutraler Klang-Preset. Er imitiert keine konkrete
# Schauspielerstimme, sondern kombiniert eine reguläre Microsoft-Stimme mit
# tieferer Tonlage und ruhigerem Tempo zu einem Bordcomputer-Klang.
KITT_STYLE_VOICE_ID = "noema-kitt-style"
KITT_STYLE_VOICE_NAME = "NOEMA KITT-Stil — tiefer synthetischer Bordcomputer"
KITT_STYLE_BASE_VOICE = "de-DE-ConradNeural"
KITT_STYLE_RATE = "-9%"
KITT_STYLE_PITCH = "-18Hz"

# Kuratierte Auswahl als Rückfallebene, falls die Live-Abfrage aller
# Microsoft-Stimmen (siehe fetch_all_voices) fehlschlägt (z. B. kein Netz).
KNOWN_VOICES = [
    "de-DE-KatjaNeural",
    "de-DE-SeraphinaMultilingualNeural",
    "de-DE-AmalaNeural",
    "de-DE-ConradNeural",
    "de-DE-KillianNeural",
    "de-AT-IngridNeural",
    "de-AT-JonasNeural",
    "de-CH-LeniNeural",
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "it-IT-ElsaNeural",
    "it-IT-DiegoNeural",
]

DEFAULT_VOICE = KNOWN_VOICES[0]

_voice_cache: list[VoiceInfo] | None = None


def kitt_style_voice_info() -> VoiceInfo:
    return {"id": KITT_STYLE_VOICE_ID, "name": KITT_STYLE_VOICE_NAME}


async def fetch_all_voices() -> list[VoiceInfo]:
    """Alle Microsoft-Edge-Stimmen live abfragen (über 300, alle Sprachen).

    Ergebnis wird für die Laufzeit der App zwischengespeichert, damit nicht
    jeder Dropdown-Aufruf im Frontend eine neue Netzabfrage auslöst.
    """
    global _voice_cache
    if _voice_cache is not None:
        return _voice_cache
    try:
        import edge_tts

        raw_voices = await edge_tts.list_voices()
    except Exception:
        logger.exception("Could not fetch Edge voice list, using curated fallback")
        return [{"id": voice, "name": voice} for voice in KNOWN_VOICES]

    def sort_key(voice: dict) -> tuple[int, str]:
        locale = voice.get("Locale", "")
        return (0 if locale.startswith("de") else 1, locale)

    voices: list[VoiceInfo] = [
        {
            "id": voice["ShortName"],
            "name": f"{voice['ShortName']} — {voice.get('FriendlyName', voice['ShortName'])}",
        }
        for voice in sorted(raw_voices, key=sort_key)
        if voice.get("ShortName")
    ]
    _voice_cache = voices
    return voices


class EdgeTTSEngine(ExternalTTSEngine):
    """Microsoft-Edge-Neural-Stimmen (kostenlos, kein API-Schlüssel).

    Nutzt den inoffiziellen Edge-Vorlese-Dienst über die Bibliothek
    edge-tts; Audio kommt als MP3 und wird unter Windows direkt über die
    eingebaute Multimedia-Schnittstelle abgespielt (kein Decoder-Paket
    nötig, siehe ExternalTTSEngine._play_windows_blocking).
    """

    def __init__(self, *, player_command: str | None = None) -> None:
        super().__init__(
            api_key=None,
            base_url=None,
            model="",
            player_command=player_command,
        )

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False
        return True

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
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSError(
                "Edge-TTS nicht installiert (Paket edge-tts fehlt)"
            ) from exc

        selected_voice = voice or DEFAULT_VOICE
        prosody: dict[str, str] = {}
        if selected_voice == KITT_STYLE_VOICE_ID:
            selected_voice = KITT_STYLE_BASE_VOICE
            prosody = {
                "rate": KITT_STYLE_RATE,
                "pitch": KITT_STYLE_PITCH,
            }

        audio = bytearray()
        try:
            communicate = edge_tts.Communicate(text, selected_voice, **prosody)
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    audio.extend(chunk["data"])
        except Exception as exc:
            message = str(exc)
            hint = ""
            if "voice" in message.lower() or "Invalid" in message:
                hint = " — Stimmkennung prüfen (z. B. de-DE-KatjaNeural)"
            raise TTSError(
                f"Edge-TTS fehlgeschlagen ({type(exc).__name__}){hint}"
            ) from exc

        if not audio:
            raise TTSError(
                "Edge-TTS lieferte kein Audio — Stimmkennung prüfen "
                "(z. B. de-DE-KatjaNeural)"
            )

        try:
            await self._play(bytes(audio), "audio/mpeg")
        except TTSError:
            raise
        except Exception as exc:
            logger.exception("Edge TTS audio playback failed")
            raise TTSError("Edge-TTS: Wiedergabe fehlgeschlagen (siehe Log)") from exc
