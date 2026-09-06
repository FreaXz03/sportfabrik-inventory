# Sport-Fabrik Inventory

Internes Tool für die Sport-Fabrik: Lieferantenrechnungen (PDF) hochladen,
Positionen automatisch auslesen, prüfen und in eine PostgreSQL-Datenbank
importieren. Danach lassen sich alle Artikel durchsuchen und ihre komplette
Lieferhistorie inklusive Original-Rechnungstext nachvollziehen.

Läuft auf einem Linux-Server im Geschäft; vier Laden-PCs greifen im internen
Netz über den Browser darauf zu. Anmeldung nach Kassensystem-Muster:
Mitarbeiter mit blosser Kassennummer, Chefs zusätzlich mit Passwort. Nur
Chefs dürfen Rechnungen hochladen, importieren und löschen.

## Tech-Stack

- **Backend**: FastAPI + SQLAlchemy 2.0, Python 3.10+
- **Datenbank**: PostgreSQL, Schema-Verwaltung über Alembic-Migrationen
- **PDF-Parsing**: PyMuPDF (wortkoordinatenbasierte Tabellenerkennung)
- **Frontend**: Vanilla HTML/CSS/JS, kein Framework, keine Build-Pipeline
- **Tests**: pytest
- **Deployment**: Docker / docker compose (siehe [`SERVER-SETUP.md`](SERVER-SETUP.md))

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
    catalog.py         Artikelsuche
    dashboard.py       Übersichtsseite
    history.py         Rechnungsliste, -details, Löschen
    preview.py         Upload-Vorschau + Importbestätigung
  services/          Fachlogik ohne HTTP-Bezug, wiederverwendbar
    importer.py        Transaktionaler Import/Löschung von Rechnungen
    parser.py          PDF-Rechnungen in strukturierte Positionen umwandeln
  templates/         HTML-Seiten (von den Routern per FileResponse ausgeliefert)
  static/
    css/, js/          Stylesheet und Frontend-Skript
    fonts/, img/        Selbst gehostete Schriftart, Logo
    BRAND-SOURCES.md    Herkunft von Logo/Schriftart, Markenfarben

migrations/          Alembic-Migrationen (siehe SERVER-SETUP.md für den Ablauf)
scripts/
  manage_users.py    CLI zum Anlegen/Entfernen von Kassennummern und Chef-Konten
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

`.env` anlegen (nicht eingecheckt) mit mindestens:

```
DATABASE_URL=postgresql+psycopg://<user>:<passwort>@localhost:5432/inventory_db
SESSION_SECRET=<per "python -c "import secrets; print(secrets.token_hex(32))"" erzeugen>
```

Datenbankschema anlegen bzw. aktuell halten:

```powershell
alembic upgrade head
```

Erstes Chef-Konto anlegen, damit überhaupt eine Anmeldung möglich ist:

```powershell
python scripts/manage_users.py add-chef <kassennummer> "<Name>"
```

App starten:

```powershell
fastapi dev app/main.py
```

## Tests

```powershell
pip install pytest
pytest
```

Für den vollständigen Parser-Test (gegen eine echte INTERSPORT-Rechnung)
zusätzlich die Umgebungsvariable `INTERSPORT_TEST_PDF` auf den Pfad einer
Beispielrechnung setzen; ohne sie wird dieser Test übersprungen.

## Deployment

Siehe [`SERVER-SETUP.md`](SERVER-SETUP.md) für Docker-Build, Server-Einrichtung,
Datenumzug und den Ablauf bei künftigen Schemaänderungen.
