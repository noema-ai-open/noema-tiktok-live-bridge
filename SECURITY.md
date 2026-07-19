# Sicherheitsmodell

## Schutzbereich

Die Anwendung ist für einen einzelnen lokalen Rechner vorgesehen. Geschützt
werden sollen insbesondere:

- Betriebssystem und Benutzerkonto vor Befehls- oder Codeausführung durch Chat
- lokale Dateien und Anmeldedaten
- optionale API-Schlüssel für Signatur- oder TTS-Dienste
- Chatdaten und Nutzerkennungen in Speicher, Oberfläche und SQLite
- Verfügbarkeit der Sprachausgabe trotz Spam oder fehlerhafter Fremddienste

Nicht Teil des Modells ist ein öffentlich erreichbarer Mehrbenutzerdienst. Die
lokale API besitzt keine Authentifizierung.

## Chat ist unvertrauenswürdige Eingabe

Jeder Anzeigename, jede Nutzerkennung, Nachricht und jedes Metadatum aus einem
Livestream oder aus der Fallback-API gilt als fremdgesteuert. Auch Moderatoren
oder Abonnenten werden nicht als vertrauenswürdige Datenquelle behandelt.

Die Pipeline erzwingt ein festes Ereignismodell, erwartet Nachrichten als
Zeichenketten, dedupliziert Ereignisse und wendet konfigurierbare Grenzen an.
URL-, Wortlisten-, Wiederholungs- und Cooldown-Filter reduzieren Missbrauch,
sind aber keine vollständige Inhaltsmoderation. Metadaten werden nicht als
Befehle interpretiert.

## Nur-Text-Prinzip

Chatinhalt darf ausschließlich als Text weitergegeben werden:

- Die API-Schemata akzeptieren für Nachrichten und TTS-Tests nur Strings.
- Die Weboberfläche setzt dynamische Inhalte über `textContent`; Chat wird nicht
  als HTML ausgeführt.
- Vor TTS werden HTML-artiges Markup, spitze Klammern, Steuerzeichen und
  übermäßige Leerzeichen entfernt.
- Windows SAPI erhält das Flag „kein XML“. Dadurch wird Text nicht als
  SSML/XML-Anweisung behandelt.
- Die Anwendung leitet Chat nie an eine Shell weiter. Nur der lokal in `.env`
  konfigurierte externe Audioplayer wird als feste Argumentliste gestartet; der
  Chattext ist kein Teil dieses Befehls.

Das Nur-Text-Prinzip schützt nicht vor beleidigenden, irreführenden oder
unangenehm gesprochenen Inhalten. Dafür sind Filter, geringe Längen und
Cooldowns zu konfigurieren. Der Not-Aus leert die Warteschlange und versucht,
die aktuelle Ausgabe zu stoppen.

## Lokale Bindung

Uvicorn bindet fest an `127.0.0.1`. Dadurch nimmt der Dienst keine Verbindungen
über LAN oder Internet an. Die API hat absichtlich keine Anmeldung und darf
nicht durch Portweiterleitung, Proxy, Container-Portfreigabe oder geänderte
Startbefehle nach außen veröffentlicht werden.

Andere Prozesse und Benutzer mit Zugriff auf denselben Rechner können die
lokale API grundsätzlich erreichen. Auf gemeinsam genutzten Systemen ist daher
zusätzliche Betriebssystem-Isolation erforderlich.

## Secrets, Cookies und Anmeldedaten

Der TikTok-Connector benötigt keinen TikTok-Login und dieses Projekt liest,
importiert oder extrahiert keine TikTok-Cookies, Browserprofile, Tokens oder
Passwörter. Solche Daten dürfen der Anwendung nicht gegeben werden.

Optional können ein Euler-Stream-API-Schlüssel und ein externer TTS-API-Schlüssel
verwendet werden. Diese Werte sind Secrets:

- nur in der lokalen `.env` oder als Prozess-Umgebungsvariable speichern
- `.env` nicht committen, weitergeben oder in Fehlerberichte kopieren
- Schlüssel nicht als Kommandozeilenargument oder in Logs ausgeben
- kompromittierte Schlüssel beim jeweiligen Anbieter widerrufen

`.env` und SQLite-Dateien sind über `.gitignore` ausgeschlossen. Das ersetzt
keine Dateiberechtigungen, Datenträgerverschlüsselung oder sichere Backups.

## Externe Datenflüsse

Im Mock- und Fallback-Modus ist für die Ereignisquelle kein TikTok-Zugriff
nötig. Im Live-Modus kommuniziert die optionale Bibliothek TikTokLive mit TikTok
und für die Erzeugung benötigter Signaturen gegebenenfalls mit Euler Stream. Die
genauen an den Signaturdienst übertragenen Request- beziehungsweise
Signaturdaten hängen von der installierten TikTokLive-Version ab und werden
nicht von diesem Projekt kontrolliert.

Bei externer TTS werden Modell, ausgewählte Stimme und der vorbereitete
Sprechtext an den konfigurierten Anbieter gesendet. Ist „Nutzernamen vorlesen“
aktiviert, kann der Sprechtext auch den TikTok-Anzeigenamen enthalten. Gerätedaten
oder der separate interne Nutzerdatensatz werden nicht absichtlich in das
TTS-Payload aufgenommen. Für sensible Streams sollte Windows SAPI statt externer
TTS verwendet werden.

## Speicherung und Sichtbarkeit

Akzeptierte Ereignisse liegen im Ringpuffer des Prozesses und erscheinen über
Weboberfläche, REST und WebSocket. Die Standardaufbewahrung `none` schreibt keine
Ereignisse dauerhaft und entfernt vorhandene Historieneinträge beim Start
beziehungsweise beim Umschalten auf `none`. Andere Aufbewahrungsmodi speichern
den vollständigen Ereignispayload einschließlich Nachricht, Anzeigename,
Nutzerkennung und Metadaten in SQLite.

Laufzeiteinstellungen werden unabhängig davon in SQLite gespeichert. Wer Zugriff
auf die lokale Datenbank oder die laufende lokale API hat, kann diese Daten
lesen oder verändern.

## Bewusst nicht enthalten

Das Tool tut insbesondere Folgendes nicht:

- TikTok-Anmeldedaten, Cookies oder Browser-Sitzungen lesen
- Prozesse von TikTok LIVE Studio untersuchen oder verändern
- Code, DLLs oder Hooks in andere Prozesse injizieren
- Schutzmechanismen umgehen, Netzwerkverkehr entschlüsseln oder Zertifikate
  austauschen
- Chatnachrichten als HTML, XML, SSML, Skript oder Shell-Befehl ausführen
- Livestreams starten, TikTok LIVE Studio fernsteuern oder Inhalte moderieren
- eine Verfügbarkeit, Vollständigkeit oder offizielle Zulässigkeit des
  inoffiziellen Live-Zugriffs garantieren

Weitere technische Grenzen beschreibt
[TIKTOK_CONNECTOR_LIMITATIONS.md](TIKTOK_CONNECTOR_LIMITATIONS.md).
