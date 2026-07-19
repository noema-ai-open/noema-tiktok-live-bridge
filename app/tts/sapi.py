import asyncio
import platform
from threading import Event as ThreadEvent
from threading import RLock
from typing import Any

from app.tts.base import TTSEngine, VoiceInfo


class SAPIEngine(TTSEngine):
    """Windows SAPI adapter with no import-time dependency on pywin32."""

    # SpeechVoiceSpeakFlags: async playback, input is explicitly plain text.
    _SVSFLAGS_ASYNC = 1
    _SVSFPURGE_BEFORE_SPEAK = 2
    _SVSF_IS_NOT_XML = 16

    def __init__(self) -> None:
        self._voice: Any | None = None
        self._stop_event: ThreadEvent | None = None
        self._lock = RLock()

    @staticmethod
    def _client() -> Any | None:
        if platform.system() != "Windows":
            return None
        try:
            import win32com.client
        except (ImportError, OSError):
            return None
        return win32com.client

    def is_available(self) -> bool:
        client = self._client()
        if client is None:
            return False
        try:
            client.Dispatch("SAPI.SpVoice")
        except Exception:
            return False
        return True

    def list_voices(self) -> list[VoiceInfo]:
        client = self._client()
        if client is None:
            return []
        try:
            voice = client.Dispatch("SAPI.SpVoice")
            return [
                {"id": str(token.Id), "name": str(token.GetDescription())}
                for token in voice.GetVoices()
            ]
        except Exception:
            return []

    @classmethod
    def list_audio_outputs(cls) -> list[dict[str, str]]:
        client = cls._client()
        if client is None:
            return []
        try:
            voice = client.Dispatch("SAPI.SpVoice")
            return [
                {"id": str(token.Id), "name": str(token.GetDescription())}
                for token in voice.GetAudioOutputs()
            ]
        except Exception:
            return []

    @staticmethod
    def _find_token(tokens: Any, selected: str) -> Any | None:
        for token in tokens:
            if str(token.Id) == selected or str(token.GetDescription()) == selected:
                return token
        return None

    def _speak_sync(
        self,
        text: str,
        voice_id: str | None,
        rate: int,
        volume: int,
        device_id: str | None,
    ) -> None:
        client = self._client()
        if client is None:
            raise RuntimeError("Windows SAPI is unavailable")
        import pythoncom

        pythoncom.CoInitialize()
        stop_event = ThreadEvent()
        sapi_voice: Any | None = None
        try:
            sapi_voice = client.Dispatch("SAPI.SpVoice")
            with self._lock:
                self._voice = sapi_voice
                self._stop_event = stop_event
            if voice_id:
                voice_token = self._find_token(sapi_voice.GetVoices(), voice_id)
                if voice_token is not None:
                    sapi_voice.Voice = voice_token
            if device_id:
                output_token = self._find_token(sapi_voice.GetAudioOutputs(), device_id)
                if output_token is not None:
                    sapi_voice.AudioOutput = output_token
            sapi_voice.Rate = max(-10, min(10, rate))
            sapi_voice.Volume = max(0, min(100, volume))
            sapi_voice.Speak(text, self._SVSF_IS_NOT_XML | self._SVSFLAGS_ASYNC)
            while sapi_voice.Status.RunningState == 2:
                if stop_event.wait(0.01):
                    sapi_voice.Speak(
                        "", self._SVSFLAGS_ASYNC | self._SVSFPURGE_BEFORE_SPEAK
                    )
                    break
        finally:
            with self._lock:
                if sapi_voice is not None and self._voice is sapi_voice:
                    self._voice = None
                    self._stop_event = None
            pythoncom.CoUninitialize()

    async def speak(
        self,
        text: str,
        voice: str | None,
        rate: int,
        volume: int,
        device: str | None,
    ) -> None:
        await asyncio.to_thread(self._speak_sync, text, voice, rate, volume, device)

    def stop(self) -> None:
        with self._lock:
            stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()


SapiEngine = SAPIEngine
