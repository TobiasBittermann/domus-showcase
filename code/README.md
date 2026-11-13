# Code-Auszüge

Ausgewählte Dateien aus dem privaten Domus-Repository, unverändert übernommen. Sie zeigen
Code-Stil und Lösungsansätze, ergeben zusammen aber **keine lauffähige Anwendung**. Lizenz siehe
[LICENSE](../LICENSE).

| Datei                                                                                         | Was sie zeigt                                                                                                                                                |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [backend/services/auth.py](backend/services/auth.py)                                          | Kern der Passkey-Authentifizierung: Registrierung per Einladung, Anmeldung, Wiederherstellung, einmalige Challenges, Sessions mit gleitendem Ablauf          |
| [backend/services/dashboard.py](backend/services/dashboard.py)                                | Salden aus Ausgaben und Ausgleichszahlungen, Cent-genaues Aufteilen, minimale Überweisungen (Greedy), Kennzahlen der Startseite per SQL-Aggregation          |
| [backend/services/fixed_costs.py](backend/services/fixed_costs.py)                            | Fixkosten: berechnete Fälligkeiten pro Person und Monat, Bestätigen und Zurücknehmen von Zahlungen, Preisänderungen ohne Verlust der Historie                |
| [backend/api/deps.py](backend/api/deps.py)                                                    | FastAPI-Dependencies: aktuelles Konto und Haushaltsmitglied, Anmeldung per Schalter (`AUTH_ENABLED`)                                                         |
| [backend/models/](backend/models/)                                                            | SQLAlchemy-2-Modelle mit typisierten `Mapped`-Spalten, `CHECK`-Constraints und Beziehungen über mehrere Module: Konto, Mitglied, Passkey, Ausgabe, Fixkosten |
| [backend/tests/softauthn.py](backend/tests/softauthn.py)                                      | Software-Authenticator: erzeugt echte, signierte WebAuthn-Antworten (CBOR, COSE-Keys, ECDSA P-256) für automatisierte Tests                                  |
| [backend/tests/test_auth.py](backend/tests/test_auth.py)                                      | End-to-End-Tests der Auth-Abläufe inkl. Angriffsszenarien (Replay, falsche Origin, unbekannter Passkey)                                                      |
| [backend/tests/test_dashboard.py](backend/tests/test_dashboard.py)                            | Tests der Abrechnung: Kassenzettel-Beispiel, Ausgleich, später eingezogene Mitglieder, Kennzahlen, Fixkosten-Schulden                                        |
| [frontend/Layout.tsx](frontend/Layout.tsx)                                                    | Responsives Layout: feste Sidebar am Desktop, barrierearmes Menü am Handy (ARIA, Escape-Taste)                                                               |
| [frontend/ExpenseModal.tsx](frontend/ExpenseModal.tsx)                                        | Formular für Kassenzettel im Stapel: Live-Berechnung des geteilten Betrags, Validierung, TanStack-Query-Mutation                                             |
| [frontend/DonutChart.tsx](frontend/DonutChart.tsx), [storeColors.ts](frontend/storeColors.ts) | Eigenes SVG-Ringdiagramm ohne Bibliothek: Legende als Tabelle, Textalternative, gleiche Farbe pro Geschäft in allen Diagrammen                               |
| [scripts/licenses.sh](scripts/licenses.sh)                                                    | Automatische Lizenzprüfung und Erzeugung der Lizenzhinweise im Docker-Build                                                                                  |
