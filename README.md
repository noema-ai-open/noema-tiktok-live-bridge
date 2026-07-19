# NOEMA TikTok Live Chat Bridge

> **Hinweis / Disclaimer:** Community-Projekt ohne jede Garantie. Die TikTok-Anbindung nutzt eine inoffizielle Bibliothek und kann jederzeit brechen — Details in [TIKTOK_CONNECTOR_LIMITATIONS.md](TIKTOK_CONNECTOR_LIMITATIONS.md). Kein offizielles TikTok-Produkt.


Lokale Brücke für Chat- und Interaktionsereignisse eines TikTok-Livestreams. Der
Dienst nimmt Ereignisse aus einer Simulation, dem experimentellen
TikTok-LIVE-Connector oder einem manuellen Fallback entgegen, vereinheitlicht und
filtert sie und stellt sie über eine lokale Weboberfläche, REST und WebSocket
bereit. Chatnachrichten können über eine begrenzte Warteschlange vorgelesen
werden.

Das Projekt ist kein offizielles TikTok-Produkt. Der Live-Connector basiert auf
der inoffiziellen Bibliothek TikTokLive und kann ohne Vorankündigung ausfallen.
Siehe [Grenzen des TikTok-Connectors](TIKTOK_CONNECTOR_LIMITATIONS.md).

## Funktionsumfang

- lokaler FastAPI-Dienst und deutschsprachige Weboberfläche
- einheitliches Ereignismodell für Chat, Beitritt, Like, Follow, Share,
  Geschenk, Abo und Verbindungsstatus
- Deduplizierung sowie Filter für Steuerzeichen, URLs, Länge, Wortlisten,
  Wiederholungen und nutzerbezogene Cooldowns
- flüchtiger Ringpuffer und optionale SQLite-Aufbewahrung (`none`, `session`,
  `24h` oder `7d`); Standard ist `none`
- REST-Endpunkte und WebSocket für lokale Verbraucher
- geordnete TTS-Warteschlange mit Maximallänge, Cooldown, Timeout und Not-Aus
- Windows SAPI, lautlose Dummy-Engine für Tests und optionaler
  OpenAI-kompatibler externer TTS-Anbieter

Der HTTP-Server bindet fest an `127.0.0.1`. Es gibt keine Anmeldung, weil die
API nicht für ein Netzwerk oder einen Reverse Proxy vorgesehen ist.

## Schnellstart unter Windows

Voraussetzungen für die manuelle Variante sind Windows 10 oder 11, Python 3.12
oder neuer und PowerShell. Im Projektverzeichnis:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[windows]"
Copy-Item .env.example .env
python -m app.main
```

Danach `http://127.0.0.1:8765/` öffnen. Der voreingestellte Mock-Modus erzeugt
Testereignisse ohne TikTok-Verbindung. TTS ist anfangs deaktiviert und wird in
der Weboberfläche eingeschaltet.

Für den Live-Modus zusätzlich installieren:

```powershell
python -m pip install -e ".[live,windows]"
```

Anschließend in `.env` mindestens `NOEMA_MODE=live` und
`NOEMA_TIKTOK_USERNAME=<Kanalname>` setzen und den Prozess neu starten. In der
Datei wird der Kanalname ohne führendes `@` erwartet; ein vorhandenes `@` wird
beim Start entfernt.

Die ausführliche Anleitung einschließlich Installer-Hinweis, VB-CABLE und
TikTok LIVE Studio steht in [SETUP_WINDOWS.md](SETUP_WINDOWS.md).

## Schnellstart für die Entwicklung

Python 3.12 oder neuer wird vorausgesetzt. Auf Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python -m pytest
python -m app.main
```

Unter PowerShell werden die Extras mit doppelten Anführungszeichen angegeben,
zum Beispiel `python -m pip install -e ".[dev,live,windows]"`.

Die optionalen Extras sind:

- `dev`: Testwerkzeuge
- `live`: inoffizielle Bibliothek TikTokLive
- `windows`: `pywin32` für Windows SAPI

## Betriebsmodi

Der Modus wird in `.env` über `NOEMA_MODE` gesetzt und erfordert einen Neustart.

| Modus | Eingabe | Zweck und Verhalten |
| --- | --- | --- |
| `mock` | intern erzeugte Testereignisse | Standard für Oberfläche, Filter und Integrationstests; keine TikTok-Verbindung |
| `live` | inoffizieller TikTokLive-Connector | experimenteller Empfang eines laufenden öffentlichen LIVE-Kanals; benötigt `.[live]` und `NOEMA_TIKTOK_USERNAME` |
| `fallback` | `POST /fallback/message` | manuelle Textzufuhr ohne TikTok-Verbindung; der Endpunkt ist nur in diesem Modus aktiv |

`fallback` liest nicht selbst aus TikTok LIVE Studio. Ein lokaler Aufrufer muss
Nachrichten mit `display_name` und `message` als JSON anliefern. Diese Eingabe
durchläuft dieselbe Pipeline wie Connector-Ereignisse.

## TTS-Modi

`NOEMA_TTS_ENGINE` wählt `sapi`, `dummy` oder `external`:

- `sapi` verwendet Windows SAPI. Ist SAPI oder `pywin32` nicht verfügbar, wird
  die lautlose Dummy-Engine verwendet.
- `dummy` erzeugt keinen Ton und dient Entwicklung und Tests.
- `external` sendet den zu sprechenden Text an einen konfigurierten
  OpenAI-kompatiblen Endpunkt. Dafür sind `EXTERNAL_TTS_API_KEY` und
  `EXTERNAL_TTS_BASE_URL` erforderlich. WAV wird unter Windows direkt
  abgespielt; für andere Formate beziehungsweise Betriebssysteme ist
  `EXTERNAL_TTS_PLAYER_COMMAND` nötig. `{file}` kann als Platzhalter für die
  temporäre Audiodatei verwendet werden.

Die Auswahl eines Audiogeräts in der Weboberfläche wirkt auf Windows SAPI. Bei
externer TTS bestimmt der konfigurierte Player beziehungsweise das Betriebssystem
die Ausgabe.

## Lokale Schnittstellen

Wichtige Endpunkte:

- `GET /health` und `GET /status`
- `GET /events?limit=100`
- `GET /settings` und `POST /settings`
- `GET /tts/voices`, `GET /audio/devices`
- `POST /tts/test` und `POST /tts/stop`
- `POST /fallback/message`
- `WS /ws/events`

FastAPI stellt außerdem unter `http://127.0.0.1:8765/docs` eine interaktive
Beschreibung der REST-Schnittstellen bereit.

## Konfiguration und Daten

`.env.example` enthält alle Prozessparameter. `.env` und `*.sqlite3` sind von
Git ausgeschlossen. Laufzeiteinstellungen aus der Weboberfläche liegen in der
konfigurierten SQLite-Datei; Ereignisse werden nur entsprechend der gewählten
Aufbewahrung gespeichert.

Optionale API-Schlüssel sind Geheimnisse und gehören ausschließlich in die
lokale `.env`, nie in Commits oder Logs. Weitere Hinweise stehen in
[SECURITY.md](SECURITY.md).

## Weitere Dokumentation

- [Architektur](ARCHITECTURE.md)
- [Windows-Einrichtung](SETUP_WINDOWS.md)
- [Sicherheitsmodell](SECURITY.md)
- [Grenzen des TikTok-Connectors](TIKTOK_CONNECTOR_LIMITATIONS.md)
- [Fehlerbehebung](TROUBLESHOOTING.md)
