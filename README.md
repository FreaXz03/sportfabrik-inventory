# Sport-Fabrik Inventory

Internes Tool für die Sport-Fabrik: Lieferantenrechnungen (PDF) hochladen,
Positionen automatisch auslesen, direkt in der Vorschau korrigieren und in
eine PostgreSQL-Datenbank importieren. Danach lassen sich alle Artikel
durchsuchen, ihre komplette Lieferhistorie inklusive Original-Rechnungstext
und Preisverlauf nachvollziehen, Freitext-Notizen hinterlegen und die
Artikelliste als Excel-Datei exportieren.

Läuft auf einem Linux-Server im Geschäft; vier Laden-PCs greifen im internen
Netz über den Browser darauf zu. Anmeldung nach Kassensystem-Muster:
Mitarbeiter mit blosser Kassennummer, Filialleiter zusätzlich mit Passwort.
Nur Filialleiter dürfen Rechnungen hochladen, importieren und löschen.

## Funktionsumfang

- **Rechnungen hochladen** (auch mehrere gleichzeitig als Stapel), Positionen
  automatisch erkennen, in der Vorschau prüfen und bei Bedarf einzelne Felder
  korrigieren — importiert wird erst nach expliziter Bestätigung.
- **OCR-Fallback** für die seltenen Fälle, in denen eine Rechnung nur als
  eingescanntes Papier statt als digitales PDF vorliegt.
- **Artikelsuche** über Marke, EAN, Artikelnummer, Bezeichnung, Farbe, Grösse
  und Lieferdatum-Bereich, mit sortierbaren Spalten, Spalten-Auswahl und
  Excel-Export.
- **Lieferhistorie und Preisverlauf** je Artikel (inkl. aller Farb-/
  Grössenvarianten), **Freitext-Notizen** mit Autor und Änderungsverlauf.
- **Rechnungsliste** mit Detailansicht, unwiderruflichem Löschen (inkl.
  korrekter Neuberechnung der Artikel-Kennzahlen) durch Filialleiter.
- **Hell-/Dunkelmodus** seitenübergreifend, grössere Schrift und
  Spalten-Auswahl für Mitarbeitende mit eingeschränktem Sehvermögen.
- **Rollenbasierte Anmeldung** nach Kassensystem-Muster, automatisierte
  geprüfte Backups (Datenbank + Original-PDFs).

## Tech-Stack

- **Backend**: FastAPI + SQLAlchemy 2.0, Python 3.10+
- **Datenbank**: PostgreSQL, Schema-Verwaltung über Alembic-Migrationen
- **PDF-Parsing**: PyMuPDF (wortkoordinatenbasierte Tabellenerkennung)
- **OCR**: Tesseract (über `pytesseract`) als Fallback für eingescannte
  Papierrechnungen ohne Textebene
- **Excel-Export**: openpyxl
- **Frontend**: Vanilla HTML/CSS/JS, kein Framework, keine Build-Pipeline
- **Tests**: pytest (70 bestanden, 19 übersprungen ohne optionale
  Zusatzvoraussetzungen wie Node.js oder eine echte Beispielrechnung — Stand
  dieser Dokumentation)
- **Deployment**: Docker / docker compose (siehe
  [`docs/SERVER-SETUP.md`](docs/SERVER-SETUP.md))

## Dokumentation

Dieses README ist der Schnelleinstieg. Ausführlichere Dokumentation liegt in
[`docs/`](docs/):

- [`docs/planung.md`](docs/planung.md) — Anforderungen, Entwicklungsphasen und
  zentrale Entscheidungen (rückwirkend rekonstruiert)
- [`docs/architektur.md`](docs/architektur.md) — Schichtenmodell,
  Sicherheitsmodell, Ablaufdiagramme für Upload/Korrektur/Import/Löschen
- [`docs/datenmodell.md`](docs/datenmodell.md) — Tabellen, ER-Diagramm,
  Migrationshistorie
- [`docs/api-referenz.md`](docs/api-referenz.md) — alle Endpunkte mit
  Berechtigungen
- [`docs/SERVER-SETUP.md`](docs/SERVER-SETUP.md) — Docker-Build,
  Server-Einrichtung, Datenumzug, Betrieb
- [`docs/BACKUPS.md`](docs/BACKUPS.md) — automatisierte, geprüfte Backups
- [`docs/Sportfabrik-Inventory-Dokumentation.docx`](docs/Sportfabrik-Inventory-Dokumentation.docx) —
  dieselben Inhalte als zusammenhängendes Word-Dokument

## Ordnerstruktur

```
app/
  main.py            Einstiegspunkt: FastAPI-App, Middleware, Router-Registrierung
  core/              Datenbankverbindung, Modelle, Passwort-Hashing
    database.py
    models.py
    security.py
  routers/           HTTP-Endpunkte (Seiten + JSON-API), gruppiert nach Thema
    auth.py            Anmeldung/Abmeldung, RBAC-Dependencies
    catalog.py         Artikelsuche, Excel-Export
    dashboard.py       Übersichtsseite
    history.py         Rechnungsliste, -details, Artikelhistorie, Löschen
    article_details.py Notizen und Preisverlauf je Artikel
    preview.py         Upload-Vorschau, Korrekturvalidierung, Importbestätigung
  services/          Fachlogik ohne HTTP-Bezug, wiederverwendbar
    importer.py        Transaktionaler Import/Löschung von Rechnungen
    parser.py          PDF-Rechnungen in strukturierte Positionen umwandeln
    ocr.py              OCR-Fallback (Tesseract) für gescannte Seiten ohne Textebene
    corrections.py      Manuelle Korrekturen in der Vorschau validieren
    article_groups.py  Farb-/Grössenvarianten desselben Artikels gruppieren
    article_export.py  Artikelliste als formatierte .xlsx-Datei
  templates/         HTML-Seiten (von den Routern per FileResponse ausgeliefert)
  static/
    css/, js/          Stylesheet und Frontend-Skripte (Theme, Session, Vorschau, Artikeldetails)
    fonts/, img/        Selbst gehostete Schriftart, Logo
    BRAND-SOURCES.md    Herkunft von Logo/Schriftart, Markenfarben

migrations/          Alembic-Migrationen (siehe docs/SERVER-SETUP.md für den Ablauf)
scripts/
  manage_users.py    CLI zum Anlegen/Entfernen von Kassennummern und Filialleiter-Konten
  backup_inventory.py Geprüftes Backup von Datenbank und Original-PDFs (siehe docs/BACKUPS.md)
docs/                Ausführliche Dokumentation (siehe oben) und Deployment-Anleitungen
tests/               pytest-Suite, ein Testmodul je Fachbereich
```

Faustregel für neuen Code: HTTP-Endpunkte gehören nach `routers/`,
wiederverwendbare Fachlogik ohne direkten HTTP-Bezug nach `services/`,
und alles rund um Datenbank/Modelle/Sicherheit nach `core/`.

## Lokales Setup (Windows-Entwicklungsrechner)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Für den OCR-Fallback bei eingescannten Papierrechnungen zusätzlich
Tesseract OCR installieren — das ist ein externes Programm, kein
Python-Paket, deshalb nicht in `requirements.txt` enthalten:
Windows-Installer von
[github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
herunterladen, bei den "Additional language data" die Sprachpakete
Deutsch (`deu`) und Ausrichtungserkennung (`osd`) mit auswählen, und den
Installationsordner (Standard `C:\Program Files\Tesseract-OCR`) zum
`PATH` hinzufügen. Ohne Tesseract läuft die App normal weiter — nur
eingescannte (nicht digital per Mail erhaltene) Rechnungen können dann
nicht hochgeladen werden. Auf dem Linux-Server ist Tesseract bereits im
Docker-Image enthalten, dort ist kein zusätzlicher Schritt nötig.

`.env` anlegen (nicht eingecheckt) mit mindestens:

```
DATABASE_URL=postgresql+psycopg://<user>:<passwort>@localhost:5432/inventory_db
SESSION_SECRET=<per "python -c "import secrets; print(secrets.token_hex(32))"" erzeugen>
```

Datenbankschema anlegen bzw. aktuell halten:

```powershell
alembic upgrade head
```

Erstes Filialleiter-Konto anlegen, damit überhaupt eine Anmeldung möglich ist:

```powershell
python scripts/manage_users.py add-chef <kassennummer> "<Name>"
```

(Der CLI-Befehl und die interne Rollenbezeichnung heissen weiterhin
`chef`/`add-chef` — nur die Oberfläche zeigt dafür „Filialleiter" an.)

App starten:

```powershell
fastapi dev app/main.py
```

## Tests

```powershell
pip install pytest
pytest
```

Einige Tests werden automatisch übersprungen, wenn eine optionale
Voraussetzung fehlt: eine echte INTERSPORT-Beispielrechnung
(Umgebungsvariable `INTERSPORT_TEST_PDF` auf den Pfad setzen), ein lokal
installiertes Tesseract, oder Node.js (für ein paar Frontend-Logik-Tests,
die reines JavaScript ausserhalb des Browsers prüfen).

## Backups

Siehe [`docs/BACKUPS.md`](docs/BACKUPS.md): geprüftes, automatisiertes
Backup von Datenbank und Original-PDFs (`scripts/backup_inventory.py`).

## Deployment

Siehe [`docs/SERVER-SETUP.md`](docs/SERVER-SETUP.md) für Docker-Build,
Server-Einrichtung, Datenumzug und den Ablauf bei künftigen Schemaänderungen.
