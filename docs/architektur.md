# Architektur

## Schichtenmodell

Der Code unter `app/` ist in drei Schichten gegliedert (siehe auch
`README.md`):

```mermaid
flowchart TB
    main["app/main.py<br/>FastAPI-App, Middleware, Router-Registrierung"]
    subgraph routers["app/routers/ — HTTP-Endpunkte"]
        auth["auth.py<br/>Anmeldung, RBAC"]
        catalog["catalog.py<br/>Artikelsuche"]
        dashboard["dashboard.py<br/>Übersicht"]
        history["history.py<br/>Rechnungen, Historie, Löschen"]
        preview["preview.py<br/>Upload, Import"]
    end
    subgraph services["app/services/ — Fachlogik"]
        importer["importer.py<br/>Import/Löschung"]
        parser["parser.py<br/>PDF → Positionen"]
    end
    subgraph core["app/core/ — Fundament"]
        database["database.py<br/>Engine, Session"]
        models["models.py<br/>SQLAlchemy-Modelle"]
        security["security.py<br/>Passwort-Hashing"]
    end

    main --> routers
    routers --> services
    routers --> core
    services --> core
    auth --> core
    preview --> importer
    preview --> parser
    history --> importer
```

Faustregel: HTTP-Endpunkte gehören nach `routers/`, wiederverwendbare
Fachlogik ohne direkten HTTP-Bezug nach `services/`, alles rund um
Datenbank/Modelle/Sicherheit nach `core/`.

## Sicherheitsmodell (Anmeldung & Rechte)

Anmeldung läuft über ein signiertes Session-Cookie (`SessionMiddleware`,
`itsdangerous`), das bis zur manuellen Abmeldung gültig bleibt. Vier
FastAPI-Dependencies in `app/routers/auth.py` setzen die Zugriffsregeln
konsequent auf jedem Endpunkt durch:

| Dependency | Für | Verhalten ohne gültige Anmeldung | Verhalten ohne Chef-Rolle |
|---|---|---|---|
| `require_login_page` | Seiten (HTML) | Redirect zu `/login?next=…` | — |
| `require_login_api` | JSON-Endpunkte | HTTP 401 | — |
| `require_chef_page` | Seiten, nur Chefs | Redirect zu `/login?next=…` | Redirect zu `/` |
| `require_chef_api` | JSON-Endpunkte, nur Chefs | HTTP 401 | HTTP 403 |

Rollen und ihre Rechte:

| Rolle | Anmeldung | Ansehen/Suchen | Hochladen/Importieren | Löschen |
|---|---|---|---|---|
| Mitarbeiter | Kassennummer | ✅ | ❌ | ❌ |
| Chef | Kassennummer + Passwort | ✅ | ✅ | ✅ |

Passwörter werden mit PBKDF2-HMAC-SHA256 (600'000 Iterationen, zufälliges
Salt je Konto) gehasht — siehe `app/core/security.py`. Es existiert kein
Klartext-Passwort in der Datenbank.

## Ablauf: Rechnung hochladen und importieren

```mermaid
sequenceDiagram
    actor Chef
    participant UI as Browser (preview.html)
    participant Preview as POST /upload-preview
    participant Parser as parser.parse_invoice()
    participant Import as POST /import-invoice
    participant Importer as importer.import_invoice()
    participant DB as PostgreSQL

    Chef->>UI: PDF auswählen
    UI->>Preview: Datei hochladen
    Preview->>Parser: PDF-Bytes parsen
    Parser-->>Preview: Positionen + Warnungen + SHA-256-Hash
    Preview-->>UI: Vorschau anzeigen (nichts gespeichert)
    Chef->>UI: Vorschau kontrollieren, Import bestätigen
    UI->>Import: Datei + erwarteter Hash + confirmed=true
    Import->>Import: Hash erneut prüfen (Datei == geprüfte Vorschau?)
    Import->>Importer: import_invoice(...)
    Importer->>DB: Advisory Lock, Duplikatsprüfung,<br/>Artikel anlegen/zusammenführen, Positionen speichern
    DB-->>Importer: Transaktion committet
    Importer-->>Import: Ergebnis (neue/wiederverwendete Artikel)
    Import-->>UI: Erfolgsmeldung
```

Wichtige Absicherungen in diesem Ablauf: `/upload-preview` schreibt nichts
in die Datenbank; der Import verlangt zwingend den Hash der geprüften
Datei; eine `pg_advisory_xact_lock`-Sperre serialisiert gleichzeitige
Importe/Löschungen über alle vier PCs hinweg, damit `first_seen`/`last_seen`
eines Artikels nie inkonsistent werden; bei einem Datenbankfehler wird die
gesamte Transaktion zurückgerollt (kein Teilimport).

## Ablauf: Rechnung löschen

Nur Chefs (`require_chef_api`). `delete_invoice()` läuft unter derselben
Advisory Lock wie der Import, entfernt die Rechnung samt Positionen und
Original-Snapshots und berechnet `first_seen`/`last_seen` der betroffenen
Artikel anschliessend aus den verbleibenden Lieferungen neu, statt veraltete
Werte stehen zu lassen.

## PDF-Parsing

`app/services/parser.py` liest die INTERSPORT-Rechnungstabelle über
Wortkoordinaten aus PyMuPDF aus (kein Layout-Template, keine feste
Spaltenbreite): Kopfzeile wird anhand bekannter Spaltentitel gesucht, Zeilen
werden anhand ihrer vertikalen Position gruppiert, Fortsetzungszeilen einer
Position (z. B. mehrzeilige Bezeichnung, Farbe/Grösse in Klammern) werden
der vorherigen Position zugeordnet. Der Parser selbst schreibt nichts in die
Datenbank und trifft keine automatischen Annahmen bei Unklarheiten — jede
unsichere Zeile bekommt eine Warnung, die den Import blockiert, bis sie
manuell geprüft wurde. Ein unbekanntes Rechnungslayout (fehlender
Tabellenkopf) führt zu einem expliziten Fehler statt zu stillem
Fehlverhalten.

## Fehlerbehandlung

Durchgängiges Prinzip: lieber explizit fehlschlagen mit einer klaren
deutschen Meldung als eine Annahme treffen, die sich später als falsch
herausstellt. Beispiele: unbekanntes Rechnungslayout, passwortgeschützte
PDFs, zu grosse Dateien (> 20 MB), uneindeutige Farbe/Grösse-Angaben, nicht
eindeutig erkanntes Rechnungs-/Belegdatum. Datenbankfehler während eines
Imports oder einer Löschung führen zum vollständigen Rollback der
Transaktion (nie ein Teilimport).
