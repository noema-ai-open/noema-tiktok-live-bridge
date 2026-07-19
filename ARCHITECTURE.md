# Architektur

## Ziel und Grenzen

Die Anwendung ist ein einzelner lokaler Python-Prozess. Sie trennt die
plattformabhängige Ereignisquelle von Normalisierung, Moderationsfiltern,
Verteilung, Speicherung und Sprachausgabe. Dadurch kann der unzuverlässige
Live-Zugriff ausfallen, ohne dass Mock-Modus, Fallback, Oberfläche oder die
interne Pipeline grundsätzlich davon abhängen.

## Komponenten

### Prozess und Konfiguration

`app/main.py` erstellt FastAPI, startet und stoppt den `BridgeService` und bindet
Uvicorn fest an `127.0.0.1`. `AppConfig` liest Prozessparameter aus Umgebung und
`.env`. Der Betriebsmodus und die TTS-Engine werden beim Start ausgewählt.

`BridgeService` verdrahtet alle Komponenten. Änderungen aus der Weboberfläche
aktualisieren Laufzeiteinstellungen, Filterkette, Aufbewahrung und TTS-Worker;
ein Wechsel von Betriebsmodus oder TTS-Engine erfordert dagegen einen Neustart.

### Eingabe-Connectoren

- `MockConnector` erzeugt kontinuierlich repräsentative Testereignisse.
- `TikTokLiveConnector` kapselt die optionale inoffizielle Abhängigkeit,
  Ereigniszuordnung, Statusmeldungen, Offline-Polling und Wiederverbindung.
- Im Modus `fallback` gibt es keinen Connector. `POST /fallback/message` speist
  manuell erzeugte Chatereignisse ein.

Alle Quellen liefern ein Mapping an denselben Callback. TikTokLive wird erst zur
Laufzeit importiert, damit die Anwendung ohne das optionale Extra funktioniert.

### Ereignispipeline

Der `EventNormalizer` überführt Rohdaten in das strikte Pydantic-Modell `Event`.
Der `EventDeduplicator` verwirft innerhalb eines Zeitfensters wiederholte
Ereignis-IDs. Danach verarbeitet eine geordnete Filterkette Chatnachrichten:

1. Steuerzeichen bereinigen
2. URLs optional blockieren
3. Maximallänge prüfen
4. Blacklist und Whitelist anwenden
5. wiederholte identische Nachrichten je Nutzer begrenzen
6. nutzerbezogenen Cooldown anwenden

Akzeptierte Ereignisse gelangen in den In-Memory-Ringpuffer, abhängig von der
Aufbewahrung in SQLite und anschließend auf den `EventBus`. Blockierte
Ereignisse werden nur an Bus-Abonnenten gesendet, die sie ausdrücklich
anfordern; die WebSocket-Route tut dies für das Diagnoseprotokoll.

### API und Weboberfläche

`app/api/router.py` stellt Status, aktuelle Ereignisse, Einstellungen,
TTS-Steuerung, Audiogeräte, Fallback-Eingabe und den Ereignis-WebSocket bereit.
Die statische Weboberfläche unter `frontend/` verwendet ausschließlich diese
lokalen Schnittstellen. Dynamische Inhalte werden im Browser als Text gesetzt,
nicht als HTML interpretiert.

### TTS

Der `TTSQueueWorker` abonniert nur akzeptierte `chat_message`-Ereignisse. Er kann
den Anzeigenamen voranstellen, reduziert Markup und Steuerzeichen auf einzeiligen
Text, kürzt auf die konfigurierte TTS-Länge und erzwingt Cooldown,
Warteschlangenlimit und Timeout.

`TTSEngine` definiert die austauschbare Schnittstelle:

- `SAPIEngine`: Windows SAPI, Stimme und SAPI-Ausgabegerät wählbar
- `DummyEngine`: lautlose, stets verfügbare Test- und Ersatzimplementierung
- `ExternalTTSEngine`: OpenAI-kompatibler HTTP-Endpunkt plus lokale Wiedergabe

### Speicherung

`SettingsStore` speichert Laufzeiteinstellungen in SQLite. `EventHistory`
speichert Ereignispayloads nur bei einer Aufbewahrung ungleich `none` und löscht
je nach Einstellung sitzungsfremde beziehungsweise abgelaufene Datensätze. Der
REST-Endpunkt `/events` liest den aktuellen Ringpuffer, nicht die persistente
Historie.

## Pipeline

```text
 MockConnector ----+
                   |
 TikTokLive --------+--> Rohereignis
                   |         |
 Fallback-API ------+         v
                        Normalisierung
                              |
                              v
                        Deduplizierung ---- blockiert ----+
                              |                            |
                              v                            |
                         Filterkette ------ blockiert -----+--> WebSocket-Diagnose
                              |
                         akzeptiert
                              |
              +---------------+----------------+
              |               |                |
              v               v                v
        Ringpuffer       SQLite-Historie     EventBus
              |          (optional)            |
              v                                +--> WebSocket / Weboberfläche
        GET /events                            |
                                               +--> TTSQueueWorker
                                                        |
                                                        v
                                                  TTSEngine
                                             (SAPI/Dummy/extern)
```

## Austauschbarkeit des Connectors

Ein neuer Connector erbt von `BaseConnector` und implementiert:

- `status`
- `connect()`
- `disconnect()`

Der Konstruktor erhält einen asynchronen `on_event`-Callback. Rohereignisse
müssen so abgebildet werden, dass der `EventNormalizer` daraus das interne
`Event`-Modell erzeugen kann: insbesondere `event_type`, eine stabile
`event_id`, Zeitstempel, Nutzerobjekt und bei `chat_message` eine Zeichenkette in
`message`.

Die Austauschbarkeit endet bewusst an der Verdrahtung: `BridgeService` wählt die
derzeit unterstützten Connectoren explizit anhand von `NOEMA_MODE`. Das
Hinzufügen eines weiteren Modus ist daher eine kleine Codeänderung und kein
dynamisches Plugin-Laden. Nach der Auswahl bleibt die restliche Pipeline vom
konkreten Connector unabhängig.
