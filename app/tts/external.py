from __future__ import annotations

import asyncio
import logging
import os
import platform
import shlex
import tempfile
from pathlib import Path

import httpx

from app.tts.base import TTSEngine, TTSError, VoiceInfo

logger = logging.getLogger(__name__)


class ExternalTTSEngine(TTSEngine):
    """OpenAI-compatible TTS adapter with local audio playback."""

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str,
        player_command: str | None = None,
    ) -> None:
        self.api_key = api_key.strip() if api_key else ""
        self.base_url = base_url.strip().rstrip("/") if base_url else ""
        self.model = model
        self.player_command = player_command.strip() if player_command else ""
        self._process: asyncio.subprocess.Process | None = None

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def list_voices(self) -> list[VoiceInfo]:
        # OpenAI-compatible providers do not expose a standard voice-list route.
        return [{"id": "alloy", "name": "alloy"}] if self.is_available() else []

    async def speak(
        self,
        text: str,
        voice: str | None,
        rate: int,
        volume: int,
        device: str | None,
    ) -> None:
        if not self.is_available():
            raise TTSError(
                "Externe TTS nicht einsatzbereit: API-Schlüssel oder Basisadresse fehlt"
            )

        # Do not add usernames, device details, or any other user data here. The
        # provider receives only the model, selected voice, and text to speak.
        # WAV anfordern: unter Windows ist nur WAV ohne Zusatzplayer abspielbar.
        payload = {
            "model": self.model,
            "voice": voice or "alloy",
            "input": text,
            "response_format": "wav",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/audio/speech",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                )
                response.raise_for_status()
        except asyncio.CancelledError:
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            hint = ""
            if status == 404:
                hint = " — Anbieter kennt /audio/speech nicht (kein TTS-Anbieter?)"
            elif status in (401, 403):
                hint = " — API-Schlüssel ungültig oder ohne Berechtigung"
            raise TTSError(
                f"Externe TTS: HTTP {status} von {self.base_url}/audio/speech{hint}"
            ) from exc
        except httpx.HTTPError as exc:
            raise TTSError(
                f"Externe TTS nicht erreichbar ({type(exc).__name__}): {self.base_url}"
            ) from exc
        except Exception as exc:
            logger.exception("External TTS client failed unexpectedly")
            raise TTSError("Externe TTS: unerwarteter Fehler (siehe Log)") from exc

        if not response.content:
            raise TTSError("Externe TTS: Anbieter lieferte leeres Audio")
        content_type = response.headers.get("content-type", "").partition(";")[0].lower()
        try:
            await self._play(response.content, content_type)
        except (asyncio.CancelledError, TTSError):
            raise
        except Exception as exc:
            logger.exception("External TTS audio playback failed")
            raise TTSError("Externe TTS: Wiedergabe fehlgeschlagen (siehe Log)") from exc

    @staticmethod
    def _is_wav(audio: bytes, content_type: str) -> bool:
        return content_type in {"audio/wav", "audio/x-wav", "audio/wave"} or (
            len(audio) >= 12 and audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
        )

    @staticmethod
    def _suffix(content_type: str, is_wav: bool) -> str:
        if is_wav:
            return ".wav"
        return {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/ogg": ".ogg",
            "audio/opus": ".opus",
            "audio/aac": ".aac",
            "audio/flac": ".flac",
        }.get(content_type, ".audio")

    async def _play(self, audio: bytes, content_type: str) -> None:
        is_wav = self._is_wav(audio, content_type)
        suffix = self._suffix(content_type, is_wav)
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary.write(audio)
                path = Path(temporary.name)
            if platform.system() == "Windows" and is_wav:
                await asyncio.to_thread(self._play_windows_wav, path)
            elif self.player_command:
                await self._play_with_command(path)
            else:
                raise TTSError(
                    "Externe TTS: Audio erhalten, aber kein Abspielweg "
                    f"({content_type or 'unbekanntes Format'}, kein Player konfiguriert)"
                )
        finally:
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove temporary TTS audio file")

    @staticmethod
    def _play_windows_wav(path: Path) -> None:
        import winsound

        winsound.PlaySound(str(path), winsound.SND_FILENAME)

    async def _play_with_command(self, path: Path) -> None:
        command = shlex.split(self.player_command, posix=os.name != "nt")
        if not command:
            raise ValueError("external TTS player command is empty")
        if any("{file}" in argument for argument in command):
            command = [argument.replace("{file}", str(path)) for argument in command]
        else:
            command.append(str(path))
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        self._process = process
        try:
            return_code = await process.wait()
            if return_code != 0:
                logger.error("External TTS player exited with code %s", return_code)
        finally:
            if self._process is process:
                self._process = None

    def stop(self) -> None:
        process = self._process
        if process is not None and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
        if platform.system() == "Windows":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except (ImportError, RuntimeError):
                pass
