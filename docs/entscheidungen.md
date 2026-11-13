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
