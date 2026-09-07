# Architektur

## Schichtenmodell

Der Code unter `app/` ist in drei Schichten gegliedert (siehe auch
`README.md`):

```mermaid
flowchart TB
    main["app/main.py<br/>FastAPI-App, Middleware, Router-Registrierung"]
    subgraph routers["app/routers/ — HTTP-Endpunkte"]
        auth["auth.py<br/>Anmeldung, RBAC"]
        catalog["catalog.py<br/>Artikelsuche, Excel-Export"]
        dashboard["dashboard.py<br/>Übersicht"]
        history["history.py<br/>Rechnungen, Historie, Löschen"]
        article_details["article_details.py<br/>Notizen, Preisverlauf"]
        preview["preview.py<br/>Upload, Validierung, Import"]
    end
    subgraph services["app/services/ — Fachlogik"]
        importer["importer.py<br/>Import/Löschung"]
        parser["parser.py<br/>PDF → Positionen"]
        ocr["ocr.py<br/>OCR-Fallback für Scans ohne Textebene"]
        corrections["corrections.py<br/>Manuelle Korrekturen validieren"]
        article_groups["article_groups.py<br/>Varianten gruppieren"]
        article_export["article_export.py<br/>Artikelliste als .xlsx"]
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
    preview --> corrections
    importer --> corrections
    parser --> ocr
    history --> importer
    history --> article_groups
    article_details --> article_groups
    catalog --> article_export
```

Faustregel: HTTP-Endpunkte gehören nach `routers/`, wiederverwendbare
Fachlogik ohne direkten HTTP-Bezug nach `services/`, alles rund um
Datenbank/Modelle/Sicherheit nach `core/`.

## Sicherheitsmodell (Anmeldung & Rechte)

Anmeldung läuft über ein signiertes Session-Cookie (`SessionMiddleware`,
`itsdangerous`), das bis zur manuellen Abmeldung gültig bleibt. Vier
FastAPI-Dependencies in `app/routers/auth.py` setzen die Zugriffsregeln
konsequent auf jedem Endpunkt durch:

| Dependency | Für | Verhalten ohne gültige Anmeldung | Verhalten ohne Filialleiter-Rolle |
|---|---|---|---|
| `require_login_page` | Seiten (HTML) | Redirect zu `/login?next=…` | — |
| `require_login_api` | JSON-Endpunkte | HTTP 401 | — |
| `require_chef_page` | Seiten, nur Filialleiter | Redirect zu `/login?next=…` | Redirect zu `/` |
| `require_chef_api` | JSON-Endpunkte, nur Filialleiter | HTTP 401 | HTTP 403 |

(Intern heisst die Rolle weiterhin `chef` — Datenbankwert, Funktionsnamen
und CLI-Befehl `add-chef` sind unverändert; nur die Oberfläche zeigt dafür
„Filialleiter" an, siehe `app/routers/auth.py`.)

Rollen und ihre Rechte:

| Rolle | Anmeldung | Ansehen/Suchen | Notizen | Hochladen/Importieren | Löschen |
|---|---|---|---|---|---|
| Mitarbeiter | Kassennummer | ✅ | nur eigene bearbeiten/löschen | ❌ | ❌ |
| Filialleiter | Kassennummer + Passwort | ✅ | alle bearbeiten/löschen | ✅ | ✅ |

Passwörter werden mit PBKDF2-HMAC-SHA256 (600'000 Iterationen, zufälliges
Salt je Konto) gehasht — siehe `app/core/security.py`. Es existiert kein
Klartext-Passwort in der Datenbank.

Der `next`-Parameter beim Login (`/login?next=/artikel/...`) wird im Browser
gegen eine feste Whitelist bekannter Routen geprüft
(`app/static/js/login-redirect.js`), bevor er als Weiterleitungsziel genutzt
wird — ein manipulierter Link kann so nicht auf eine externe Seite
umleiten (offener Redirect).

## Ablauf: Rechnung hochladen und importieren

```mermaid
sequenceDiagram
    actor Filialleiter
    participant UI as Browser (preview.html)
    participant Preview as POST /upload-preview
    participant Parser as parser.parse_invoice()
    participant Validate as POST /validate-preview
    participant Import as POST /import-invoice
    participant Importer as importer.import_invoice()
    participant DB as PostgreSQL

    Filialleiter->>UI: Eine oder mehrere PDFs auswählen
    UI->>Preview: Datei hochladen
    Preview->>Parser: PDF-Bytes parsen
    Parser-->>Preview: Positionen + Warnungen + SHA-256-Hash
    Preview-->>UI: Vorschau anzeigen (nichts gespeichert)
    opt Filialleiter korrigiert einzelne Felder
        UI->>Validate: Datei + Korrekturen erneut prüfen
        Validate-->>UI: Neu bewertete Positionen/Warnungen
    end
    Filialleiter->>UI: Vorschau kontrollieren, Import bestätigen
    UI->>Import: Datei + erwarteter Hash + confirmed=true (+ Korrekturen)
    Import->>Import: Hash erneut prüfen (Datei == geprüfte Vorschau?)
    Import->>Importer: import_invoice(...)
    Importer->>DB: Advisory Lock, Duplikatsprüfung,<br/>Artikel anlegen/zusammenführen, Positionen speichern
    DB-->>Importer: Transaktion committet
    Importer-->>Import: Ergebnis (neue/wiederverwendete Artikel)
    Import-->>UI: Erfolgsmeldung
    Note over UI: Bei mehreren Dateien: automatisch<br/>zur nächsten Datei in der Warteschlange
```

Wichtige Absicherungen in diesem Ablauf: `/upload-preview` schreibt nichts
in die Datenbank; der Import verlangt zwingend den Hash der geprüften
Datei; eine `pg_advisory_xact_lock`-Sperre serialisiert gleichzeitige
Importe/Löschungen über alle vier PCs hinweg, damit `first_seen`/`last_seen`
eines Artikels nie inkonsistent werden; bei einem Datenbankfehler wird die
gesamte Transaktion zurückgerollt (kein Teilimport); der Import bleibt
gesperrt, solange irgendeine Warnung offen ist — das gilt serverseitig,
nicht nur als Browser-Prüfung.

## Korrekturen in der Vorschau

Erkennt der Parser eine Position falsch oder unvollständig (z. B. Farbe und
Grösse nicht eindeutig getrennt, EAN fehlt), kann der Filialleiter das
betroffene Feld direkt in der Vorschau-Tabelle korrigieren, statt die ganze
Rechnung abzulehnen. `app/services/corrections.py` wendet diese Korrekturen
serverseitig auf die frisch geparsten Daten an (nie auf clientseitig
mitgeschickte Rohdaten) und validiert jede Position komplett neu:
Pflichtfelder, EAN-Format (8/12/13/14 Ziffern), Zahlenformat für Menge/UVP.
Jede tatsächliche Änderung wird als `correction_audit`
(Ausgangswert, neuer Wert, wer, wann) in `invoice_item_sources` gespeichert
— nachvollziehbar, auch nachdem die Rechnung importiert wurde. `/validate-preview`
lässt eine Korrektur vor dem eigentlichen Import gegenprüfen;
`/import-invoice` wendet dieselbe Validierung noch einmal serverseitig an,
bevor irgendetwas gespeichert wird.

## Stapel-Import (mehrere Rechnungen nacheinander)

Die Upload-Seite akzeptiert mehrere PDFs gleichzeitig. Jede Datei bekommt
einen eigenen Warteschlangen-Eintrag mit Status (wartend, bereit, Duplikat,
Fehler, importiert); der Browser prüft neue Dateien automatisch per
`/invoice-import-status` auf bereits importierte Duplikate, bevor sie in die
Warteschlange aufgenommen werden, und springt nach jedem erfolgreichen
Import selbstständig zur nächsten offenen Datei. Korrekturen an einer Datei
sind vollständig von den anderen Dateien in der Warteschlange isoliert.
Serverseitig gibt es keinen eigenen „Batch"-Endpunkt: jede Datei durchläuft
einzeln denselben Vorschau-/Validierungs-/Import-Ablauf wie ein Einzel-Upload
— die Warteschlange ist reine Frontend-Logik (`app/static/js/preview.js`).

## Artikelgruppierung, Notizen und Preisverlauf

Verschiedene Farben/Grössen eines Artikels haben unterschiedliche EANs und
damit unterschiedliche `products`-Datensätze. Für Historie, Notizen und
Preisverlauf werden diese Varianten serverseitig zu einer Gruppe
zusammengefasst (`app/services/article_groups.py`): gleiche Marke **und**
gleiche Lieferanten-Artikelnummer zählen als eine Gruppe; fehlt die
Lieferanten-Artikelnummer, bleibt der Artikel allein. So zeigt die
Artikeldetailseite (`/articles/{id}/history`) automatisch die Lieferhistorie,
den Preisverlauf und die Notizen aller Varianten eines Artikels an einem
Ort, ohne dass jemand die Gruppierung manuell pflegen muss.

Notizen (`article_notes`, siehe `datenmodell.md`) sind Freitext zu einer
Artikelgruppe, z. B. Beobachtungen zum Verkauf oder Hinweise für die nächste
Bestellung. Bearbeiten/Löschen verlangt die zuletzt gelesene `version`
(optimistisches Sperren): Hat eine andere Person die Notiz inzwischen
geändert, schlägt die Anfrage mit HTTP 409 fehl, statt die fremde Änderung
stillschweigend zu überschreiben. Mitarbeiter dürfen nur eigene Notizen
bearbeiten/löschen, Filialleiter alle.

## Artikelliste als Excel-Export

`/api/articles/export` liefert dieselbe gefilterte/sortierte Artikelliste wie
`/api/articles`, aber ohne Paginierung und als fertig formatierte `.xlsx`-Datei
(`app/services/article_export.py`, via `openpyxl`): fette Kopfzeile,
sinnvolle Spaltenbreiten, Zahlen-/Datumsformate, eingefrorene Kopfzeile und
Auto-Filter. Gedacht zum Weitergeben/Ausdrucken ausserhalb der App, z. B. für
eine Bestellliste.

## Ablauf: Rechnung löschen

Nur Filialleiter (`require_chef_api`). `delete_invoice()` läuft unter
derselben Advisory Lock wie der Import, entfernt die Rechnung samt
Positionen und Original-Snapshots und berechnet `first_seen`/`last_seen` der
betroffenen Artikel anschliessend aus den verbleibenden Lieferungen neu,
statt veraltete Werte stehen zu lassen.

## PDF-Parsing

`app/services/parser.py` liest die INTERSPORT-Rechnungstabelle über
Wortkoordinaten aus PyMuPDF aus (kein Layout-Template, keine feste
Spaltenbreite): Kopfzeile wird anhand bekannter Spaltentitel gesucht, Zeilen
werden anhand ihrer vertikalen Position gruppiert, Fortsetzungszeilen einer
Position (z. B. mehrzeilige Bezeichnung, Farbe/Grösse in Klammern) werden
der vorherigen Position zugeordnet. Der Parser selbst schreibt nichts in die
Datenbank und trifft keine automatischen Annahmen bei Unklarheiten — jede
unsichere Zeile bekommt eine Warnung, die den Import blockiert, bis sie
manuell geprüft (oder korrigiert, siehe oben) wurde. Ein unbekanntes
Rechnungslayout (fehlender Tabellenkopf) führt zu einem expliziten Fehler
statt zu stillem Fehlverhalten.

## OCR-Fallback für gescannte Papierrechnungen

Ganz selten kommt eine Rechnung nicht digital per Mail, sondern nur als
Papier im Paket. Ein Scan davon ist eine PDF ohne Textebene (reines
Rasterbild je Seite) und würde beim normalen Parsing sofort mit
„Tabellenkopf fehlt" scheitern. `parser.page_content()` prüft deshalb je
Seite zuerst `page.get_text("words")`; liefert das nichts, übernimmt
`app/services/ocr.py` die Seite:

1. Seite mit PyMuPDF als Bild rendern (300 DPI); Tesseracts
   Ausrichtungserkennung (OSD) korrigiert eine noch falsche Drehung, falls
   der Scan sie nicht schon selbst im PDF vermerkt hat.
2. Tesseract liest Wörter samt Positionen aus dem Bild.
3. Die Pixel-Koordinaten werden in PDF-Punkte umgerechnet und je
   erkannter Textzeile auf eine gemeinsame Höhe normalisiert, sodass das
   Ergebnis exakt wie PyMuPDFs eigene `words`-Liste aussieht — die
   bestehende Tabellenerkennung in `parser.py` (Kopfzeilensuche,
   Spaltengrenzen, Zeilengruppierung) läuft danach unverändert weiter,
   ganz gleich ob die Wörter aus der Textebene oder per OCR stammen.

OCR-Seiten und die daraus gelesenen Positionen werden mit `ocr_used`
markiert (bis in die Datenbank, `Invoice.ocr_used`); die Vorschau zeigt
dafür einen eigenen Hinweis, der zu besonders sorgfältiger Kontrolle rät,
blockiert den Import über diese Markierung allein aber nicht — nur
echte Datenprobleme (fehlende Pflichtfelder, uneindeutige Farbe/Grösse
usw.) tun das, genau wie bei digital erhaltenen Rechnungen. Ist
Tesseract auf dem Rechner nicht installiert, meldet der Upload einen
klaren Fehler statt eines stillen Fehlschlags (siehe `README.md` fürs
lokale Setup; im Docker-Image ist Tesseract bereits enthalten).

## Frontend: kein Framework, aber ein gemeinsames Theme

`app/static/js/` bleibt bewusst ohne Build-Pipeline (siehe Entscheidung E8),
zwei Skripte werden aber seitenübergreifend eingebunden:

- `theme.js` verwaltet Hell-/Dunkelmodus über CSS-Custom-Properties in
  `app.css` (folgt standardmässig der Systemeinstellung, manuell
  umschaltbar, per `localStorage` gemerkt) und liefert den Umschalt-Knopf
  als Factory-Funktion.
- `session.js` baut daraus auf jeder Seite mit aktiver Anmeldung die
  Kopfzeile (Name/Kassennummer, „Abmelden", Einstellungen-Menü mit dem
  Hell/Dunkel-Umschalter) und blendet für Mitarbeiter die Upload-Funktionen
  aus.

Für ältere oder sehbeeinträchtigte Mitarbeitende bietet die Artikelsuche
zusätzlich eine Spalten-Auswahl (einzelne Spalten ausblenden) und grössere
Schrift in der Ergebnistabelle, ebenfalls per `localStorage` gemerkt.

## Fehlerbehandlung

Durchgängiges Prinzip: lieber explizit fehlschlagen mit einer klaren
deutschen Meldung als eine Annahme treffen, die sich später als falsch
herausstellt. Beispiele: unbekanntes Rechnungslayout, passwortgeschützte
PDFs, zu grosse Dateien (> 20 MB), uneindeutige Farbe/Grösse-Angaben, nicht
eindeutig erkanntes Rechnungs-/Belegdatum, widersprüchliche Korrekturwerte,
gleichzeitig bearbeitete Notizen (HTTP 409). Datenbankfehler während eines
Imports oder einer Löschung führen zum vollständigen Rollback der
Transaktion (nie ein Teilimport).
