from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FallbackMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=10_000)

    @field_validator("message", mode="before")
    @classmethod
    def only_text(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("message must be text")
        return value


class TTSTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=10_000)

    @field_validator("text", mode="before")
    @classmethod
    def only_text(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("text must be text")
        return value


class ConnectionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["mock", "live", "fallback"] | None = None
    tiktok_username: str | None = Field(default=None, max_length=100)
    tts_engine: Literal["sapi", "edge", "dummy", "external", "deepgram"] | None = None
    deepgram_api_key: str | None = Field(default=None, max_length=500)
    eulerstream_api_key: str | None = Field(default=None, max_length=500)
    external_tts_base_url: str | None = Field(default=None, max_length=500)
    external_tts_model: str | None = Field(default=None, max_length=200)
    external_tts_api_key: str | None = Field(default=None, max_length=500)
    tts_voice: str | None = Field(default=None, max_length=200)
