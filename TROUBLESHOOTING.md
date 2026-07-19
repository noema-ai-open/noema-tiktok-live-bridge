# Fehlerbehebung

## Schnelle Diagnose

1. Prüfen, ob der Prozess noch läuft und welches Terminalprotokoll er ausgibt.
2. `http://127.0.0.1:8765/health` öffnen. Erwartet wird `{"status":"ok"}`.
3. `http://127.0.0.1:8765/status` öffnen und `mode` sowie
   `connector_status` prüfen.
4. In der Weboberfläche „Log / Ereignisse“ und den WebSocket-Status prüfen.
5. Zum Eingrenzen vorübergehend `NOEMA_MODE=mock` verwenden und neu starten.

Die Browseranzeige enthält Ereignisse und Filtergründe, aber nicht jede
Python-Ausnahme. Für Connector-, TTS- und Wiedergabefehler ist das Terminal, aus
dem `python -m app.main` gestartet wurde, die maßgebliche Logquelle. Secrets und
vollständige Chatdaten vor dem Teilen eines Logs entfernen.

## Stream ist nicht live oder wird nicht gefunden

Symptome sind `offline`, dauerhaft `connecting` oder wiederholtes
`reconnecting`.

- `NOEMA_MODE=live` und `NOEMA_TIKTOK_USERNAME` in der tatsächlich verwendeten
  `.env` prüfen. Den sichtbaren Kanalnamen, nicht eine vollständige URL,
  eintragen.
- Sicherstellen, dass der Kanal öffentlich live und vom Rechner aus erreichbar
  ist.
- Nach Änderungen an `.env` den Prozess neu starten.
- Bei `offline` das Standardintervall von 60 Sekunden abwarten. Häufiges
  manuelles Neustarten verbessert die Erkennung nicht.
- Bei einer installierten Variante liegt `.env` gegebenenfalls unter
  `%LOCALAPPDATA%\NOEMA\TikTokBridge`, nicht im Programmordner.

TikTok LIVE Studio muss für die Audioeinspeisung eingerichtet sein, ist aber
nicht die Quelle der Connector-Verbindung. Die Bridge steuert LIVE Studio nicht.

## TikTokLive fehlt oder ist nach einem Update inkompatibel

Bei `connector_status: "unavailable"` und einem Hinweis auf TikTokLive zunächst
im aktivierten virtuellen Environment installieren:

```powershell
python -m pip install -e ".[live,windows]"
```

Version und Import prüfen:

```powershell
python -m pip show TikTokLive
python -c "import TikTokLive; print(TikTokLive.__file__)"
```

Wenn die Bibliothek importiert wird, aber Verbindungen nach einer TikTok- oder
TikTokLive-Änderung brechen:

- Terminalfehler notieren, dabei Schlüssel und Chatdaten entfernen.
- Nicht wiederholt im Sekundentakt neu starten; der Connector besitzt bereits
  Backoff und Offline-Polling.
- Prüfen, ob ein kompatibles Projekt-Update vorliegt.
- Bis zur Klärung `NOEMA_MODE=mock` oder `NOEMA_MODE=fallback` verwenden.

Keine Cookies, Zugangsdaten oder Browserprofile als vermeintliche Reparatur
bereitstellen. Die grundsätzliche Bruchgefahr ist in
[TIKTOK_CONNECTOR_LIMITATIONS.md](TIKTOK_CONNECTOR_LIMITATIONS.md) beschrieben.

## Kein Ton

- In der Weboberfläche TTS aktivieren, Einstellungen speichern und erst dann
  eine Testnachricht einreihen.
- Prüfen, ob der Test mit „TTS engine is unavailable“ abgelehnt wird.
- `NOEMA_TTS_ENGINE=sapi` und die Installation des Extras `windows` prüfen.
- Lautstärke in der Bridge, im Windows-Lautstärkemixer und am Zielgerät prüfen.
- Eine verfügbare Stimme und zunächst „Standardausgabe“ wählen.
- Nach einer Konfigurationsänderung die Testwarteschlange mit „NOT-AUS“ leeren
  und erneut testen.

Wenn SAPI nicht verfügbar ist, fällt die Anwendung auf die Dummy-Engine zurück.
Sie nimmt Texte an, erzeugt aber absichtlich keinen Ton. Das kann insbesondere
bei fehlendem `pywin32` oder außerhalb von Windows auftreten.

Bei `NOEMA_TTS_ENGINE=external` müssen API-Schlüssel, Basis-URL und Modell gesetzt
sein. WAV kann Windows direkt wiedergeben. Für Nicht-WAV-Antworten ist ein
funktionierender `EXTERNAL_TTS_PLAYER_COMMAND` erforderlich. Die Geräteauswahl
der Weboberfläche steuert den externen Player nicht.

## Audiogerät fehlt oder ist verschwunden

- Prüfen, ob Windows das Gerät in den Soundeinstellungen anzeigt.
- Bridge nach Anschluss, Treiberinstallation, Umbenennung oder Neustart des
  Geräts neu starten.
- Für VB-CABLE prüfen, ob sowohl `CABLE Input` als Wiedergabe- als auch
  `CABLE Output` als Aufnahmegerät vorhanden und aktiviert sind.
- In der Bridge das SAPI-Ziel `CABLE Input` wählen; in TikTok LIVE Studio als
  Quelle `CABLE Output` wählen.
- Ist ein gespeichertes Gerät nicht mehr verfügbar, „Standardausgabe“ oder ein
  aktuell gelistetes Gerät wählen und speichern.

Geräte-IDs stammen von Windows SAPI. Treiberupdates oder Neuinstallationen
können sie ändern.

## TikTok LIVE Studio empfängt keinen Pegel

- Zuerst mit einer TTS-Testnachricht prüfen, ob die Bridge grundsätzlich Ton
  erzeugt.
- Bridge-Ausgabe auf `CABLE Input` und LIVE-Studio-Eingang auf `CABLE Output`
  kontrollieren; die ähnlich klingenden Namen bezeichnen entgegengesetzte
  Seiten des virtuellen Kabels.
- Quelle in LIVE Studio entstummen und dort den Eingangspegel prüfen.
- Doppelte Quellen oder Windows-„Abhören“ deaktivieren, falls Echo entsteht.
- Mock-Modus für Audiotests verwenden, damit Connectorfehler den Test nicht
  beeinflussen.

## Firewall, Proxy oder Sicherheitssoftware

Für Zugriffe auf `127.0.0.1` ist normalerweise keine eingehende
Firewallfreigabe nötig. Keine Portfreigabe für `8765` anlegen und den Dienst
nicht auf `0.0.0.0` starten.

Der Live-Modus benötigt ausgehende HTTPS-/WebSocket-Verbindungen der
Python-Anwendung zu TikTok sowie durch TikTokLive zum Signaturdienst. Externe TTS
benötigt eine ausgehende HTTPS-Verbindung zum konfigurierten Anbieter.

- Prüfen, ob Proxy, VPN, DNS-Filter, TLS-Inspektion oder Sicherheitssoftware
  diese ausgehenden Verbindungen blockieren.
- Nur die konkret benötigte ausgehende Anwendung beziehungsweise Ziele
  freigeben; keine pauschale eingehende Regel erstellen.
- Bei Unternehmensnetzen die lokale Administration einbeziehen. Zertifikats- oder
  Schutzmechanismen nicht umgehen.

Wenn bereits `/health` lokal nicht erreichbar ist, liegt das Problem nicht an
TikTok: Prozess, Port, `.env` und Terminalfehler prüfen. Ein belegter Port kann
über `NOEMA_PORT` geändert werden; danach die neue lokale URL verwenden.

## Ereignisse werden blockiert oder nicht vorgelesen

Das Webprotokoll zeigt blockierte Ereignisse mit einem Grund wie `duplicate`,
`url`, `max_length`, `blacklist`, `repetition_spam` oder `user_cooldown`.
Filtereinstellungen in der Weboberfläche prüfen.

Nur akzeptierte `chat_message`-Ereignisse gelangen zur TTS. Likes, Geschenke und
andere Ereignistypen werden angezeigt, aber nicht vorgelesen. Zusätzlich können
TTS-Maximallänge, TTS-Cooldown und Warteschlangenlimit Nachrichten kürzen,
überspringen oder bei voller Warteschlange ältere Einträge verdrängen.

## Logs für einen Fehlerbericht

Hilfreich sind:

- Betriebssystem- und Python-Version
- gewählter Modus und TTS-Engine
- Ausgabe von `python -m pip show TikTokLive`, falls Live betroffen ist
- `mode` und `connector_status` aus `/status`
- der relevante kurze Terminalausschnitt und die ungefähre Uhrzeit
- ob der Fehler auch im Mock-Modus auftritt

Vor dem Teilen entfernen:

- Inhalte aus `.env`
- API-Schlüssel, Tokens und Cookies
- Anzeigenamen, Nutzerkennungen, Chattexte und andere personenbezogene Daten
- lokale Benutzer- und Verzeichnispfade, soweit sie für die Diagnose nicht
  erforderlich sind
