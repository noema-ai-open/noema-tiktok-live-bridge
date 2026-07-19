# NOEMA TikTok Live Chat Bridge

Phase 1 is a local-only FastAPI bridge with mock and manual fallback inputs. It
normalizes, deduplicates and filters events before exposing them over REST and a
WebSocket. There is deliberately no TikTok connection in this phase.

```bash
python -m pip install -e '.[dev]'
python -m pytest
python -m app.main
```

The server binds only to `127.0.0.1`. Copy `.env.example` to `.env` to adjust
the port and other local settings.

Future phases: real TikTok connector, UI and packaging.

