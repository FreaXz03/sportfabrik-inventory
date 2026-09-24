# Sicherheit — Prüfung und offene Massnahmen

Stand: Sicherheitsprüfung vom **24.09.2026** (Branch `feature/warenwirtschaft-v2`,
Commit `229e8b6`). Geprüft wurden Geheimnisse (Code und ganzer Git-Verlauf),
Einschleusung (SQL, XSS, Befehle, Pfade, Deserialisierung), Anmeldung und
Rechte, Konfiguration (Docker, Header, Endpunkte), Abhängigkeiten
(`pip-audit`), KI-Nutzung und Datenschutz.

**Ergebnis:** keine kritischen und keine hohen Befunde. Vier mittlere Punkte
sollten **vor dem Einsatz im Laden** (Roadmap Phase F — Betrieb) erledigt
sein, dazu fünf niedrige. Noch ist nichts davon behoben.

Diese Datei wird bei jeder Behebung nachgeführt (Status-Spalte).

## Offene Massnahmen

| # | Stufe | Thema | Massnahme | Status |
|---|---|---|---|---|
| S1 | mittel | Anmeldung über HTTP, Sitzung 5 Jahre | HTTPS über lokalen Reverse-Proxy (z. B. Caddy mit internem Zertifikat), Cookie mit `https_only=True`; Sitzungen bei Passwortwechsel serverseitig ungültig machen | offen — vor Einsatz im Laden |
| S2 | mittel | Login ohne Begrenzung von Fehlversuchen | Fehlversuche je Gerät und Kassennummer begrenzen, einheitliche Fehlermeldung, Mindestlänge Passwort 10 statt 6; Server nur im Laden-Netz erreichbar | offen — **Entscheid nötig** (ändert das Login-Verhalten) |
| S3 | mittel | Pillow 12.2.0 mit 13 bekannten Lücken | Update auf 12.3.0 (`requirements-server.txt`, `requirements.txt`) | offen |
| S4 | mittel | Backups unverschlüsselt | Backup vor dem Kopieren auf den externen Datenträger verschlüsseln (`age` oder `gpg --symmetric`), Schlüssel getrennt aufbewahren | offen |
| S5 | niedrig | API-Doku ohne Anmeldung | `/docs`, `/redoc`, `/openapi.json` im Betrieb abschalten | offen |
| S6 | niedrig | `/db-test` ohne Anmeldung | nur `{"ok": true}` zurückgeben (wird vom Docker-Healthcheck gebraucht) | offen |
| S7 | niedrig | Keine Sicherheits-Header | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'self'` | offen |
| S8 | niedrig | Server-Pakete ohne transitive Pins/Hashes, Images ohne Digest | `pip-compile --generate-hashes`, `pip install --require-hashes`, Images mit `@sha256:` fixieren | offen |
| S9 | niedrig | Übersichtsseiten laden Google Fonts | Links in `docs/aktualisiert/*.html` (und den Vault-Fassungen) entfernen, Systemschrift verwenden | offen |

### Einzelheiten

**S1 — HTTP und lange Sitzung.** Die App läuft heute unter
`http://SERVER-IP:8080` (`docs/SERVER-SETUP.md`). Passwörter der
Filialleiter und das Sitzungs-Cookie gehen damit unverschlüsselt durchs
Netz. Das Cookie gilt 5 Jahre (`SESSION_MAX_AGE` in `app/routers/auth.py`,
bewusst „bis zur Abmeldung" wie an der Kasse) und enthält nur die Benutzer-ID;
eine abgefangene Kopie bleibt darum auch nach Abmelden oder Passwortwechsel
gültig. Mit HTTPS im Laden-Netz ist das Abfangen praktisch ausgeschlossen.

**S2 — Login.** `/login` zählt keine Fehlversuche. Jeder Passwortversuch
kostet den Server wegen PBKDF2 (600 000 Runden) rund eine halbe Sekunde
Rechenzeit, und es läuft nur ein Worker. Die Antworten unterscheiden
„Kassennummer unbekannt" und „Passwort nötig". Mitarbeiter melden sich
bewusst nur mit der Kassennummer an (Kassen-Muster, D8) — der eigentliche
Schutz ist darum, dass nur Laden-PCs den Server erreichen (kein Gäste-WLAN,
keine Portweiterleitung ins Internet).

**S3 — Pillow.** Heute kaum ausnutzbar: `app/services/ocr.py` gibt Pillow nur
rohe Pixel aus PyMuPDF (`Image.frombytes`), die betroffenen Bild-Decoder
werden nicht benutzt. Sobald z. B. JPEG-Uploads direkt mit Pillow geöffnet
werden, wird es relevant. Das Update ist klein.

**S4 — Backups.** `scripts/backup_inventory.py` legt Datenbank-Dump und
`original-pdfs.zip` im Klartext ab, auch auf dem externen Datenträger
(`docs/BACKUPS.md`). Ein verlorener Datenträger enthielte alle
Lieferantenbelege, Einkaufspreise und Konten.

## Hinweise ohne Handlungsbedarf

- `text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})")` setzt nur eine
  feste Zahl ein — keine SQL-Einschleusung.
- Bestandssuche (`app/services/bestand.py`) maskiert `%` und `_` nicht (die
  Artikelsuche schon) — betrifft nur Treffer, nicht die Sicherheit.
- `.gitignore` deckt `.venv-1/`, `.coverage`, `*.pem`, `*.key` und `.env.*`
  noch nicht ab; nichts davon ist versioniert.
- `CLAUDE.md` enthält einen lokalen Pfad mit dem Mac-Benutzernamen.
- Alle Rollen dürfen auf jeden Lagerort buchen, umlagern und stornieren —
  gewollt (D26, Regel 9).
- Testpasswörter stehen nur in den Tests.

## Was gut ist

- Keine Geheimnisse im Code und im Git-Verlauf; `.env.server` ist ignoriert,
  nur für den Besitzer lesbar, beide Geheimnisse sind 64 Zeichen lang.
- Datenbankzugriffe nur über SQLAlchemy mit Parametern; Sortierung als feste
  Auswahl; Artikelsuche maskiert Platzhalter.
- Frontend ohne `innerHTML`/`eval`, Ausgabe über `textContent`, keine
  externen Skripte (per Test erzwungen), Login-Weiterleitung geprüft (Test).
- Alle Daten-Endpunkte verlangen eine Anmeldung; Belege nur Filialleiter und
  Zentrale; Lagerort-Rechte serverseitig geprüft.
- Passwörter mit PBKDF2-SHA256, 600 000 Runden, Salt und zeitkonstantem
  Vergleich; Sitzung wird beim Login neu begonnen; `SameSite=Lax` und strenge
  Inhaltstyp-Prüfung schützen gegen Anfragen von fremden Seiten.
- Excel-Export lässt Formeln als Text; Upload-Grenze 20 MB und 200 Seiten;
  passwortgeschützte PDFs werden abgewiesen.
- Docker: App ohne root, Datenbank von aussen nicht erreichbar, Standard nur
  `127.0.0.1`, kein `--privileged`, keine `:latest`-Images.
- Keine ausgehenden HTTP-Aufrufe, keine KI im Betrieb (Regel 1), keine
  unsichere Deserialisierung, Backup-Skript ohne Shell.

## Laufend

- `pip-audit -r requirements-server.txt` vor jedem Server-Update laufen lassen.
- HTTPS, Netztrennung und verschlüsselte Backups sind Pflichtpunkte für
  Phase F (Betrieb).
