# NOEMA TikTok Live Chat Bridge

The bridge is a local-only FastAPI service with mock and manual fallback inputs. It
normalizes, deduplicates and filters events before exposing them over REST and a
WebSocket. Phase 2 adds queued text-to-speech with a test engine and optional
Windows SAPI output. There is deliberately no TikTok connection yet.

```bash
python -m pip install -e '.[dev]'
# On Windows, install SAPI support with: python -m pip install -e '.[dev,windows]'
python -m pytest
python -m app.main
```

The server binds only to `127.0.0.1`. Copy `.env.example` to `.env` to adjust
the port and other local settings.

Future phases: real TikTok connector, UI and packaging.
