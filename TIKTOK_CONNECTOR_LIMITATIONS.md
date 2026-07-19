# Grenzen des TikTok-Connectors

## Status der Unterstützung

**Von TikTok offiziell für diese Anbindung unterstützt: nichts.**

Dieses Projekt verwendet keine dokumentierte offizielle TikTok-LIVE-Chat-API
und ist weder von TikTok freigegeben noch mit einer Verfügbarkeitszusage
versehen. Der Connector ist technisch möglich, aber experimentell. Dass eine
Verbindung heute funktioniert, ist keine Zusage für den nächsten Stream oder
eine spätere Bibliotheksversion.

Nutzung, Umfang und Häufigkeit müssen eigenverantwortlich mit den jeweils
geltenden Plattformbedingungen und rechtlichen Anforderungen abgeglichen
werden.

## Inoffizielle Bibliothek TikTokLive

Der optionale Modus `live` lädt zur Laufzeit die Python-Bibliothek TikTokLive.
Sie bildet nicht öffentlich stabilisierte Web- und Ereignisprotokolle nach. Der
Projektcode registriert, soweit die installierte Version sie bereitstellt,
Listener für:

- Connect und Disconnect
- Kommentar
- Beitritt
- Like
- Follow
- Share
- Geschenk
- Abo

Die Datenfelder werden defensiv auf ein kleines internes Modell abgebildet.
Fehlende oder umbenannte Felder können dennoch zu unvollständigen Metadaten,
falscher Zuordnung oder einem Verbindungsfehler führen. Es gibt keine Garantie,
dass jedes Ereignis empfangen wird, in der richtigen Reihenfolge ankommt oder
eine dauerhaft stabile ID besitzt.

## Signatur über Euler Stream und Datenfluss

TikTokLive benötigt für bestimmte TikTok-Webanfragen eine gültige Signatur und
verwendet dafür einen Drittanbieter-Signaturdienst von Euler Stream. Optional
kann `NOEMA_EULERSTREAM_API_KEY` an die Bibliothek übergeben werden.

Vereinfachter Datenfluss:

```text
Bridge
  |
  +--> TikTokLive
          |
          +--> Euler Stream: Request-/Signaturkontext, optional API-Schlüssel
          |         |
          |         +--> erzeugte Signatur zurück
          |
          +--> TikTok: signierte Web-/LIVE-Anfragen und Ereignisverbindung
                    |
                    +--> LIVE-Ereignisse zurück zur Bridge
```

Welche Felder TikTokLive im Signaturkontext konkret überträgt, hängt von der
installierten Bibliotheksversion und dem Dienst ab. Dieses Projekt erstellt oder
prüft diese Drittanbieteranfragen nicht selbst. Vor dem Live-Einsatz sind daher
die Datenschutz- und Nutzungsbedingungen beider Fremdkomponenten zu bewerten.
TikTok-Anmeldedaten oder Browser-Cookies werden vom Projekt nicht angefordert.

## Rate Limits und Wiederverbindung

TikTok und der Signaturdienst können Anfragen drosseln, ablehnen oder blockieren.
Veröffentlichte, für diesen inoffiziellen Zugriff verlässlich geltende Grenzwerte
sind hier nicht vorausgesetzt. Der Connector versucht Last zu begrenzen:

- Ein ausdrücklich als offline gemeldeter Kanal wird standardmäßig alle 60
  Sekunden erneut geprüft (`NOEMA_LIVE_OFFLINE_POLL_SECONDS`).
- Andere Abbrüche verwenden exponentielle Wartezeiten mit Zufallskomponente,
  beginnend ungefähr bei 5 Sekunden und gedeckelt bei 300 Sekunden.
- Nach einer stabilen Verbindung wird die Fehlerfolge zurückgesetzt.

Diese Mechanismen garantieren weder die Einhaltung unbekannter Limits noch eine
erfolgreiche Wiederverbindung. Ein kürzeres Offline-Intervall erhöht die Last und
kann Sperren oder Kosten beim Drittanbieter begünstigen.

## Typische Bruchursachen

- TikTok ändert Webendpunkte, Signaturanforderungen, Ereignisschemata oder
  Bot-Schutz.
- TikTokLive ändert öffentliche Python-Klassen, Importpfade oder Feldnamen.
- Euler Stream ändert Dienst, Schlüsselanforderungen, Kontingente oder
  Verfügbarkeit.
- Netzwerk, DNS, TLS-Prüfung, Proxy oder lokale Firewall blockieren ausgehende
  Verbindungen.
- Der Kanal ist nicht live, eingeschränkt, regional nicht erreichbar oder unter
  dem konfigurierten Namen nicht auffindbar.

Ein Update von TikTokLive kann ein Problem beheben, aber auch Inkompatibilitäten
erzeugen. Updates sollten deshalb zuerst im Mock-Modus und anschließend mit
einem unkritischen Live-Test geprüft werden.

## Technisch möglich, aber experimentell

Bei kompatibler Bibliotheks- und Plattformversion kann der Connector öffentliche
LIVE-Ereignisse empfangen, normalisieren und über die lokale Pipeline
bereitstellen. Statuswechsel, Offline-Polling und Wiederverbindung sind
fehlertolerant ausgelegt. Diese Eigenschaften machen den Betrieb robuster, aber
nicht offiziell unterstützt oder dauerhaft zuverlässig.

## Bewusst ausgeschlossen

Zur Stabilisierung oder Erweiterung des Live-Zugriffs setzt dieses Projekt
bewusst nicht ein:

- TikTok-Login, Credential-Zugriff oder Passwortspeicherung
- Lesen oder Extrahieren von Cookies, Tokens oder Browserprofilen
- Prozessinjektion, DLL-Injektion oder DLL-Hooking
- Memory-Patching, API-Hooking oder Manipulation von TikTok LIVE Studio
- TLS-Interception, Zertifikatsaustausch oder Umgehung von Schutzmechanismen
- automatisierte Interaktion im Namen eines Kontos, Chatversand oder Moderation
- Umgehung von Rate Limits, Sperren, Regionen- oder Zugriffsbeschränkungen

Wenn der inoffizielle Connector nicht vertretbar oder nicht funktionsfähig ist,
bleiben `mock` für Tests und `fallback` für eine bewusst manuelle lokale
Textzufuhr verfügbar.
