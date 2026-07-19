# NOEMA TikTok Live Chat Bridge

The bridge is a local-only FastAPI service with mock, TikTok LIVE and manual
fallback inputs. It normalizes, deduplicates and filters events before exposing
them over REST and a WebSocket. It includes queued text-to-speech with a test
engine, optional Windows SAPI output, an optional OpenAI-compatible external TTS
provider, and a local German web control surface.

```bash
python -m pip install -e '.[dev]'
# For the unofficial live connector: python -m pip install -e '.[dev,live]'
# On Windows, install SAPI support with: python -m pip install -e '.[dev,windows]'
python -m pytest
python -m app.main
```

Open `http://127.0.0.1:8765/` after starting the service. The server binds only to
`127.0.0.1`. Copy `.env.example` to `.env` to adjust the port and other local
settings.

Set `NOEMA_MODE=live` and `NOEMA_TIKTOK_USERNAME` for live mode. TikTokLive is an
unofficial reverse-engineering project and can stop working when TikTok or its
third-party signature service changes. Offline channels are polled every 60
seconds by default rather than aggressively.

For external TTS, set `NOEMA_TTS_ENGINE=external` plus
`EXTERNAL_TTS_API_KEY`, `EXTERNAL_TTS_BASE_URL`, and `EXTERNAL_TTS_MODEL`. WAV
audio uses Windows playback directly; other combinations require
`EXTERNAL_TTS_PLAYER_COMMAND` (the optional `{file}` placeholder receives a
temporary audio path).
