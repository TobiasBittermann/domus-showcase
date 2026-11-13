# Code-Auszüge

Ausgewählte Dateien aus dem privaten Domus-Repository, unverändert übernommen. Sie zeigen
Code-Stil und Lösungsansätze, ergeben zusammen aber **keine lauffähige Anwendung**. Lizenz siehe
[LICENSE](../LICENSE).

| Datei                                                                                     | Was sie zeigt                                                                                                                                       |
| ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| [backend/services/auth.py](backend/services/auth.py)                                      | Kern der Passkey-Authentifizierung: Registrierung per Einladung, Anmeldung, Wiederherstellung, einmalige Challenges, Sessions mit gleitendem Ablauf |
| [backend/models/user.py](backend/models/user.py), [passkey.py](backend/models/passkey.py) | SQLAlchemy-2-Modelle mit typisierten `Mapped`-Spalten und Beziehungen über mehrere Module                                                           |
| [backend/tests/softauthn.py](backend/tests/softauthn.py)                                  | Software-Authenticator: erzeugt echte, signierte WebAuthn-Antworten (CBOR, COSE-Keys, ECDSA P-256) für automatisierte Tests                         |
| [backend/tests/test_auth.py](backend/tests/test_auth.py)                                  | End-to-End-Tests der Auth-Abläufe inkl. Angriffsszenarien (Replay, falsche Origin, unbekannter Passkey)                                             |
| [frontend/Layout.tsx](frontend/Layout.tsx)                                                | Responsives Layout: feste Sidebar am Desktop, barrierearmes Menü am Handy (ARIA, Escape-Taste)                                                      |
| [scripts/licenses.sh](scripts/licenses.sh)                                                | Automatische Lizenzprüfung und Erzeugung der Lizenzhinweise im Docker-Build                                                                         |
