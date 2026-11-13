# Designentscheidungen

Kurze Begründungen für die wichtigsten technischen Entscheidungen.

## Passkeys statt Passwörtern

**Entscheidung:** Anmeldung ausschließlich mit Passkeys.

**Warum:** Passkeys sind phishing-resistent, es gibt keine Passwort-Datenbank, die geleakt werden
kann, und auf dem Handy ist die Anmeldung bequemer (Biometrie). Für eine kleine Nutzergruppe
(ein Haushalt) ist der Verzicht auf einen Passwort-Fallback vertretbar, wenn es einen sicheren
Wiederherstellungsweg gibt.

**Konsequenzen:** HTTPS mit fester Domain ist Pflicht (Passkeys sind an die RP-ID gebunden; ein
späterer Domainwechsel würde alle Passkeys ungültig machen). Wiederherstellung über
CLI-Links und mehrere Passkeys pro Person.

## Serverseitige Sessions statt JWT

**Entscheidung:** Zufälliges Session-Token im `HttpOnly`-Cookie, Hash in PostgreSQL.

**Warum:** Sessions lassen sich sofort widerrufen (Abmelden, Passkey verloren), es gibt keinen
Token-Inhalt, der im Browser gelesen werden kann, und bei einer einzigen API ohne Drittanbieter
bringt JWT keinen Vorteil.

## Eine Origin für Frontend und API

**Entscheidung:** Ein Reverse Proxy liefert Frontend und `/api` unter derselben Domain aus.

**Warum:** Keine CORS-Konfiguration, Cookies mit `SameSite=Lax` funktionieren ohne Ausnahmen, und
die WebAuthn-Origin ist eindeutig.

## FastAPI + SQLAlchemy 2 (synchron) + PostgreSQL

**Entscheidung:** FastAPI mit synchronen Datenbankzugriffen über SQLAlchemy 2 und psycopg 3.

**Warum:** FastAPI liefert Validierung (Pydantic) und eine OpenAPI-Spezifikation ohne Mehraufwand.
Synchrone Datenbankzugriffe sind für die erwartete Last (ein Haushalt) mehr als ausreichend und
deutlich einfacher zu testen und zu debuggen als Async-Code. PostgreSQL ist robust und läuft
problemlos auf ARM64.

## Generierte API-Typen im Frontend

**Entscheidung:** TypeScript-Typen werden aus der OpenAPI-Spezifikation des Backends erzeugt.

**Warum:** Backend und Frontend können nicht unbemerkt auseinanderlaufen – eine geänderte API
führt zu Compilerfehlern statt zu Laufzeitfehlern.

## Tests gegen echte PostgreSQL-Datenbank

**Entscheidung:** Keine In-Memory-SQLite-Datenbank für Tests.

**Warum:** Unterschiede zwischen SQLite und PostgreSQL (Enums, Constraints, Zeitzonen) würden
Fehler verdecken. Die Testdatenbank läuft im selben Docker-Compose-Setup.

## Konto und Mitglied getrennt

**Entscheidung:** Personen im Haushalt (`HouseholdMember`) und Login-Konten (`User`) sind eigene
Tabellen; ein Konto wird per Einladungslink mit einem Mitglied verknüpft.

**Warum:** Ein Haushalt soll sofort nutzbar sein, auch wenn nicht alle ein Konto anlegen
(z. B. Kinder). Ausgaben und Fixkosten verweisen auf Mitglieder, nicht auf Konten. Später kann ein
Konto mehreren Haushalten angehören, ohne das Datenmodell umzubauen.

## Anmeldung fertig gebaut, aber per Schalter abgeschaltet

**Entscheidung:** Die Passkey-Anmeldung ist vollständig implementiert und getestet, wird aber erst
mit `AUTH_ENABLED=true` erzwungen. Bis dahin handelt jede Anfrage als ältestes Mitglied.

**Warum:** Passkeys brauchen HTTPS mit fester Domain – das gibt es erst im Betrieb auf dem Pi.
Die Fachfunktionen sollten aber schon jetzt im Alltag erprobt werden. Weil die gesamte Fachlogik
nur das „aktuelle Mitglied“ kennt (eine FastAPI-Dependency), ändert das Umlegen des Schalters
nichts an Services oder Tests der Fachbereiche.

## Geldbeträge als ganze Cent

**Entscheidung:** Alle Beträge sind `int` in Cent – in der Datenbank, in der API und im Frontend.
Formatiert wird erst bei der Anzeige.

**Warum:** Gleitkommazahlen können Beträge wie 0,10 € nicht exakt darstellen. Mit ganzen Cent
geht beim Aufteilen nichts verloren: Restcents werden gezielt verteilt
(`split_evenly(701, 2) == [351, 350]`).

## Salden berechnen statt speichern

**Entscheidung:** Schulden, Salden und Fixkosten-Fälligkeiten werden bei jeder Abfrage aus den
Buchungen berechnet. Gespeichert werden nur Fakten: Ausgaben, Ausgleichszahlungen, bestätigte
Überweisungen.

**Warum:** Gespeicherte Summen können durch Fehler oder spätere Korrekturen auseinanderlaufen;
berechnete nicht. Für die Datenmenge eines Haushalts ist das Rechnen bei jeder Abfrage
problemlos schnell.

## Historie bei Preisänderungen erhalten

**Entscheidung:** Eine bestätigte Fixkosten-Zahlung speichert den Betrag zum Zeitpunkt der
Bestätigung.

**Warum:** Ändert sich z. B. der Stromabschlag, gilt der neue Betrag für alle offenen Monate,
während bereits bezahlte Monate unverändert bleiben – genau wie auf dem Kontoauszug.

## Eigene Diagramme statt Chart-Bibliothek

**Entscheidung:** Die Ringdiagramme der Startseite sind eine eigene, kleine SVG-Komponente.

**Warum:** Für zwei Diagrammtypen lohnt keine große Abhängigkeit (Bundle-Größe, Lizenzprüfung).
Eine eigene Komponente gibt volle Kontrolle über Barrierefreiheit (Legende als Tabelle,
Textalternative), konsistente Farben pro Geschäft und den Dunkelmodus.

## Selbst gehostet auf dem Raspberry Pi

**Entscheidung:** Betrieb per Docker Compose auf eigener Hardware.

**Warum:** Haushaltsdaten (Ausgaben, Einkäufe) bleiben im eigenen Netz. Docker sorgt dafür, dass
Entwicklung auf dem PC und Betrieb auf dem Pi identisch sind.

## Lizenz-Compliance im Build

**Entscheidung:** Die Lizenzen aller Abhängigkeiten werden bei jedem Build gegen eine Positivliste
geprüft; Lizenzhinweise werden automatisch erzeugt.

**Warum:** Domus ist nicht Open Source. Copyleft-Lizenzen (GPL/AGPL) könnten das Projekt zwingen,
den gesamten Code offenzulegen – deshalb werden sie automatisch erkannt, bevor sie ins Projekt
gelangen.
