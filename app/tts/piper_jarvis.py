from __future__ import annotations

import asyncio
import os
import tempfile
import wave
from pathlib import Path

import httpx

from app.tts.base import TTSEngine, TTSError, VoiceInfo

JARVIS_MEDIUM_MODEL_URL = (
    "https://huggingface.co/jgkawell/jarvis/resolve/main/"
    "en/en_GB/jarvis/medium/jarvis-medium.onnx"
)
JARVIS_MEDIUM_CONFIG_URL = (
    "https://huggingface.co/jgkawell/jarvis/resolve/main/"
    "en/en_GB/jarvis/medium/jarvis-medium.onnx.json"
)


class PiperJarvisEngine(TTSEngine):
    """Local Piper TTS using the community JARVIS-style British voice."""

    def __init__(self, model_dir: str | Path | None = None) -> None:
        base = (
            Path(model_dir)
            if model_dir
            else Path(os.environ.get("LOCALAPPDATA") or Path.home())
            / "NOEMA"
            / "TikTokBridge"
            / "voices"
            / "jarvis"
        )
        self.model_dir = base
        self.model_path = base / "jarvis-medium.onnx"
        self.config_path = base / "jarvis-medium.onnx.json"
        self._voice = None
        self._download_lock = asyncio.Lock()

    def is_available(self) -> bool:
        try:
            import piper  # noqa: F401
        except Exception:
            return False
        return True

    def list_voices(self) -> list[VoiceInfo]:
        if not self.is_available():
            return []
        return [
            {
                "id": "jarvis-medium",
                "name": "JARVIS (Piper, lokal, Englisch/British)",
            }
        ]

    async def _download_if_needed(self) -> None:
        if self.model_path.exists() and self.config_path.exists():
            return
        async with self._download_lock:
            if self.model_path.exists() and self.config_path.exists():
                return
            self.model_dir.mkdir(parents=True, exist_ok=True)
            try:
                async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                    for url, target in (
                        (JARVIS_MEDIUM_MODEL_URL, self.model_path),
                        (JARVIS_MEDIUM_CONFIG_URL, self.config_path),
                    ):
                        if target.exists():
                            continue
                        tmp = target.with_suffix(target.suffix + ".download")
                        async with client.stream("GET", url) as response:
                            response.raise_for_status()
                            with tmp.open("wb") as handle:
                                async for chunk in response.aiter_bytes():
                                    handle.write(chunk)
                        tmp.replace(target)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                raise TTSError(
                    "Piper JARVIS: Stimmmodell konnte nicht heruntergeladen werden"
                ) from exc

    async def _load_voice(self):
        if self._voice is not None:
            return self._voice
        await self._download_if_needed()
        try:
            from piper import PiperVoice

            self._voice = await asyncio.to_thread(
                PiperVoice.load,
                str(self.model_path),
                config_path=str(self.config_path),
            )
            return self._voice
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise TTSError("Piper JARVIS: Modell konnte nicht geladen werden") from exc

    async def speak(
        self,
        text: str,
        voice: str | None,
        rate: int,
        volume: int,
        device: str | None,
    ) -> None:
        cleaned = " ".join(text.split()).strip()
        if not cleaned:
            raise TTSError("Piper JARVIS: kein Text zum Sprechen")
        model = await self._load_voice()
        path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary:
                path = Path(temporary.name)
            def synthesize() -> None:
                with wave.open(str(path), "wb") as wav_file:
                    model.synthesize_wav(cleaned, wav_file)

            await asyncio.to_thread(synthesize)
            if os.name != "nt":
                raise TTSError("Piper JARVIS: lokale Wiedergabe ist aktuell für Windows gebaut")
            import winsound

            await asyncio.to_thread(
                winsound.PlaySound,
                str(path),
                winsound.SND_FILENAME,
            )
        except asyncio.CancelledError:
            raise
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError("Piper JARVIS: Synthese oder Wiedergabe fehlgeschlagen") from exc
        finally:
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass

    def stop(self) -> None:
        if os.name == "nt":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except RuntimeError:
                pass
