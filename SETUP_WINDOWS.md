# Einrichtung unter Windows

## Variante A: bereitgestellter Installer

Falls zu einer Version ein fertiges Windows-Paket veröffentlicht wurde, sollte
dieses aus den [Releases des Projekt-Repositorys](https://github.com/noema-ai-open/noema-tiktok-live-bridge/releases)
bezogen und nach den Hinweisen des jeweiligen Releases installiert werden. Ein
Installer ist kein Bestandteil des Python-Quellpakets und seine Verfügbarkeit
wird hier nicht vorausgesetzt.

Der im Repository enthaltene Launcher-Quelltext ist allein noch kein Installer.
Ein darauf basierendes Paket legt veränderliche Daten unter
`%LOCALAPPDATA%\NOEMA\TikTokBridge` ab, erzeugt dort beim ersten Start eine
`.env` aus dem Beispiel und öffnet die lokale Oberfläche. Die konkrete
Paketierung und Deinstallation richtet sich nach dem jeweiligen Release.

Wenn kein passendes Release-Artefakt vorhanden ist, die folgende manuelle
Variante verwenden.

## Variante B: manuelle Installation

### Voraussetzungen

- Windows 10 oder 11
- Python 3.12 oder neuer einschließlich `py`-Launcher und `pip`
- das lokal entpackte oder geklonte Projektverzeichnis
- für Live-Betrieb eine ausgehende Internetverbindung

PowerShell im Projektverzeichnis öffnen und eine virtuelle Umgebung anlegen:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[windows]"
Copy-Item .env.example .env
```

Falls PowerShell lokale Aktivierungsskripte blockiert, kann jeder Befehl auch
direkt über `.\.venv\Scripts\python.exe` ausgeführt werden. Eine dauerhafte
Lockerung der systemweiten Ausführungsrichtlinie ist nicht erforderlich.

Zum ersten Test den voreingestellten Mock-Modus beibehalten:

```powershell
python -m app.main
```

Im Browser `http://127.0.0.1:8765/` öffnen. Unter „Verbindung“ sollte der
Mock-Connector als verbunden erscheinen und nach kurzer Zeit sollten simulierte
Ereignisse eintreffen.

### Live-Modus aktivieren

Den Prozess beenden und das Live-Extra installieren:

```powershell
python -m pip install -e ".[live,windows]"
```

In `.env` ändern:

```dotenv
NOEMA_MODE=live
NOEMA_TIKTOK_USERNAME=<Kanalname>
```

`NOEMA_EULERSTREAM_API_KEY` ist optional und nur zu setzen, wenn ein eigener
Schlüssel für den von TikTokLive verwendeten Signaturdienst eingesetzt werden
soll. Er ist ein Secret und darf nicht in Logs, Screenshots oder Commits
gelangen.

Anschließend `python -m app.main` erneut starten. Ein nicht laufender Kanal wird
standardmäßig erst nach 60 Sekunden erneut geprüft. Der Live-Modus ist
experimentell; Details stehen in
[TIKTOK_CONNECTOR_LIMITATIONS.md](TIKTOK_CONNECTOR_LIMITATIONS.md).

## Windows SAPI prüfen

`NOEMA_TTS_ENGINE=sapi` ist voreingestellt. Dafür muss das Extra `windows`
installiert sein. In der Weboberfläche:

1. Unter „Stimme“ eine verfügbare Systemstimme wählen oder die Standardstimme
   belassen.
2. Unter „Audiogerät“ zunächst die Standardausgabe wählen.
3. „Text-to-Speech“ aktivieren und Einstellungen speichern.
4. Unter „Testnachricht“ einen kurzen Text abspielen.

Erscheinen keine Stimmen oder Geräte, den Dienst nach der Installation von
`pywin32` beziehungsweise eines Audiotreibers neu starten. Eine lautlose
Dummy-Engine kann aktiv sein, wenn SAPI beim Prozessstart nicht verfügbar war.

## VB-CABLE einrichten

VB-CABLE ist Fremdsoftware und nicht Bestandteil dieses Projekts. Es wird nur
benötigt, wenn die TTS-Ausgabe als Audioquelle in TikTok LIVE Studio eingespeist
werden soll.

1. VB-CABLE von der offiziellen Herstellerseite beziehen und entsprechend der
   Herstelleranleitung installieren. Die Treiberinstallation kann
   Administratorrechte und einen Neustart erfordern.
2. Die Bridge nach Installation oder Neustart neu starten, damit SAPI die neue
   Geräteliste einliest.
3. In der Weboberfläche als Audiogerät `CABLE Input (VB-Audio Virtual Cable)`
   wählen. Trotz des Namens ist dies die Wiedergabeseite, an die die Bridge Ton
   sendet.
4. TTS aktivieren, speichern und eine Testnachricht abspielen.
5. In TikTok LIVE Studio eine Mikrofon- beziehungsweise Audioeingangsquelle für
   `CABLE Output (VB-Audio Virtual Cable)` hinzufügen. Dies ist die Aufnahmeseite,
   von der LIVE Studio den Ton empfängt.
6. Die Pegelanzeige in LIVE Studio prüfen und Lautstärke dort sowie in der
   Bridge vorsichtig einstellen.

Die exakten Bezeichnungen können je nach VB-CABLE- und Windows-Version leicht
abweichen. Windows-Optionen wie „Dieses Gerät als Wiedergabequelle verwenden“
oder „Dieses Gerät abhören“ sind für die reine Einspeisung nicht erforderlich.
Monitoring kann Rückkopplung oder doppelte Ausgabe verursachen.

## Zusammenspiel mit TikTok LIVE Studio

Bridge und LIVE Studio sind zwei getrennte Programme:

- Die Bridge empfängt im Modus `live` öffentliche Ereignisse über TikTokLive.
- Die Bridge erzeugt TTS-Audio und gibt es an SAPI beziehungsweise VB-CABLE aus.
- LIVE Studio nimmt `CABLE Output` als Audioquelle auf und mischt es in den
  Stream.
- LIVE Studio wird von der Bridge weder gestartet noch gesteuert. Es gibt keine
  Prozessintegration, DLL-Injektion oder Übergabe von TikTok-Anmeldedaten.

Für einen vollständigen Test zuerst die Bridge im Mock-Modus und die
VB-CABLE-Pegel prüfen. Erst danach in den Live-Modus wechseln. So lassen sich
Audioprobleme von Connector-Problemen trennen.

## Start bei späteren Sitzungen

Bei manueller Installation:

```powershell
Set-Location <Projektverzeichnis>
.\.venv\Scripts\Activate.ps1
python -m app.main
```

Die Konfiguration liegt in `.env`, Laufzeiteinstellungen und je nach
Aufbewahrung Ereignisdaten in `noema_bridge.sqlite3`. Beide Dateien enthalten
lokale Daten und sollten nicht unkontrolliert weitergegeben werden.

Bei Problemen hilft [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
