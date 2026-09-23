# Sport-Fabrik Inventory

Internes Tool für die Sport-Fabrik: Lieferantenrechnungen (PDF) hochladen,
Positionen automatisch auslesen, direkt in der Vorschau korrigieren und in
eine PostgreSQL-Datenbank importieren. Danach lassen sich alle Artikel
durchsuchen, ihre komplette Lieferhistorie inklusive Original-Rechnungstext
und Preisverlauf nachvollziehen, Freitext-Notizen hinterlegen und die
Artikelliste als Excel-Datei exportieren.

Läuft auf einem zentralen Server (Volketswil); die 4 Filialen (SF1 Volketswil,
SF2 Conthey, SF3 Regensdorf, SF4 Hägendorf) sowie die externen Standorte ohne
Verkauf — die Verarbeitungsstellen GEWA und VEBO und das Lager Dietikon —
greifen im internen Netz über den Browser darauf zu. Anmeldung nach
Kassensystem-Muster: Mitarbeiter mit blosser Kassennummer, Filialleiter und
Admin/Zentrale zusätzlich mit Passwort. Mitarbeiter dürfen alles ausser
Dokumente hochladen/bearbeiten/löschen; das bleibt Filialleitern und der
Zentrale vorbehalten. Admin/Zentrale-Konten sind filialübergreifend, alle
anderen Benutzer sind einer oder mehreren Filialen zugeordnet und können in
der Oberfläche zwischen ihren Filialen wechseln.

## Funktionsumfang

- **Rechnungen hochladen** (auch mehrere gleichzeitig als Stapel), Positionen
  automatisch erkennen, in der Vorschau prüfen und bei Bedarf einzelne Felder
  korrigieren — importiert wird erst nach expliziter Bestätigung.
- **Lieferant und Dokumenttyp erkennt das System selbst** anhand von Merkmalen
  im Dokument (ein Parser-Modul je Lieferanten-Layout, siehe
  `app/services/parsers/`); ein noch unbekanntes Layout wird als solches
  gemeldet, statt mit einer irreführenden Fehlermeldung abzubrechen.
- **Ziel-Filiale erkennt das System aus der Lieferadresse** des Belegs und
  schlägt sie beim Import vor (änderbar) — auch Lieferungen an eine andere
  Filiale oder an das externe Lager GEWA landen so am richtigen Ort.
- **Erwartete Lieferungen**: Auftragsbestätigungen und Bestellungen kündigen
  Ware nur an — Bestand entsteht erst, wenn jemand die Ankunft bestätigt.
  Kommt weniger an, bleibt die Restmenge sichtbar offen.
- **Bestand je Filiale** (Seite „Bestand"): aktueller Bestand pro Variante
  und Lagerort, mit Suche, Filiale-Filter und ältestem Eingangsdatum. Lesen
  darf jede Anmeldung alle Filialen; Ware an einem externen Standort ist als
  solche erkennbar, weil sie noch kein Eingangsdatum hat.
- **Ausbuchen per Scan** (Seite „Ausbuchen"): jeder Scan bucht sofort ein
  Stück aus — Verkauf, Bruch/Defekt, Diebstahl/Schwund, Eigenbedarf, Retoure
  oder Sonstiges. Reicht der Bestand nicht, warnt die Seite und bucht
  trotzdem; ein Fehlscan lässt sich per Gegenbuchung rückgängig machen.
- **Umlagern** (Seite „Umlagern"): die empfangende Filiale bucht Ware aus
  einem anderen Lagerort in einem Schritt — per Scan oder aus dem Bestand der
  Quelle. Ware aus GEWA, VEBO oder Dietikon bekommt dabei ihr Eingangsdatum;
  zwischen Filialen behält sie ihr Datum.
- **Ware von Hand erfassen** (Seite „Erfassen"): scannen oder eintippen,
  ohne Beleg und ohne Parser — für Ware ohne Dokument und für Lieferanten,
  deren Layout noch nicht erkannt wird. Pflicht sind nur Marke, Bezeichnung,
  Menge und UVP; die Kassenkategorie lässt sich freiwillig mitgeben. Gebucht
  wird alles auf einmal als ein Wareneingang.
- **Artikel ohne Barcode** sind kein Sonderfall: eine Position ohne EAN läuft
  mit Hinweis durch (Schlüssel ist dann Lieferant + Artikelnummer + Farbe +
  Grösse); eine unleserliche EAN blockiert den Import dagegen weiterhin.
- **Interne EAN auf Knopfdruck**: Artikel ohne Hersteller-Barcode bekommen
  eine hauseigene EAN-13 (GS1-Bereich 20–29, mit Prüfziffer) und werden damit
  an der Kasse scannbar.
- **Preisetikett als PDF** in Etikettengrösse für den Etikettendrucker: mit
  Jahrgang, Lieferant, UVP, Reduktionsstufe und EAN-Strichcode — einzeln oder
  für einen ganzen Wareneingang auf einmal.
- **OCR-Fallback** für die seltenen Fälle, in denen eine Rechnung nur als
  eingescanntes Papier statt als digitales PDF vorliegt.
- **Artikelsuche** über Marke, EAN, Lieferanten-Artikelnummer, Bezeichnung,
  Farbe, Grösse, Kategorie und Lieferdatum-Bereich, mit sortierbaren Spalten,
  Spalten-Auswahl und Excel-Export.
- **Lieferhistorie und Preisverlauf** je Artikel (inkl. aller Farb-/
  Grössenvarianten), **Freitext-Notizen** mit Autor und Änderungsverlauf.
- **Rechnungsliste** mit Detailansicht, unwiderruflichem Löschen (inkl.
  korrekter Neuberechnung der Artikel-Kennzahlen) durch Filialleiter.
- **Hell-/Dunkelmodus** seitenübergreifend, grössere Schrift und
  Spalten-Auswahl für Mitarbeitende mit eingeschränktem Sehvermögen.
- **Mehrsprachig DE/FR/EN**: Oberfläche und Fehlermeldungen vollständig
  übersetzt (Deutsch Standard), Sprache jederzeit pro Benutzer umstellbar.
- **Rollenbasierte Anmeldung** nach Kassensystem-Muster, automatisierte
  geprüfte Backups (Datenbank + Original-PDFs).
- **Bestand je Filiale**: jede importierte Rechnungsposition bucht einen
  Wareneingang gegen die aktive Filiale des hochladenden Kontos, als
  Bewegung im append-only-Journal `lagerbewegungen` (siehe
  `docs/datenmodell.md`) — Wareneingänge werden nie direkt überschrieben.
- **FEDAS-Kategorievorschlag**: erkennt der Lieferant eine passende
  FEDAS-Warengruppe, wird die Kassenkategorie beim Import automatisch
  vorgeschlagen (aktuell mit einer Teilmenge bestätigter Codes, siehe
  `app/core/fedas.py`).
- **Kategorie von Hand wählen**, wenn der FEDAS-Code fehlt oder noch nicht
  zugeordnet ist — auf der Artikelseite oder gleich beim Erfassen. Die
  Oberfläche sagt dazu, ob die Kategorie vorgeschlagen oder von Hand gewählt
  wurde; eine Wahl von Hand überschreibt kein späterer Import. Der Filter
  „Ohne Kategorie" in der Artikelsuche zeigt, wo noch etwas fehlt.

## Tech-Stack

- **Backend**: FastAPI + SQLAlchemy 2.0, Python 3.10+
- **Datenbank**: PostgreSQL, Schema-Verwaltung über Alembic-Migrationen
- **PDF-Parsing**: PyMuPDF (wortkoordinatenbasierte Tabellenerkennung), ein Modul je Lieferanten-Layout mit automatischer Erkennung (`app/services/parsers/`)
- **OCR**: Tesseract (über `pytesseract`) als Fallback für eingescannte
  Papierrechnungen ohne Textebene
- **Excel-Export**: openpyxl
- **Frontend**: Vanilla HTML/CSS/JS, kein Framework, keine Build-Pipeline;
  eine Stildatei (`app/static/css/app.css`) mit Design-Tokens für Hell- und
  Dunkelmodus, lokal eingebundene Schrift, keine externen CDNs
- **i18n**: eigener, schlanker Katalog (JSON-Dateien + `translate()`/`i18n.js`,
  siehe `docs/architektur.md` Abschnitt „Mehrsprachigkeit"), keine zusätzliche
  Abhängigkeit
- **Tests**: pytest (488 bestanden, 20 übersprungen ohne optionale
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
- [`docs/obsidian-graphify.md`](docs/obsidian-graphify.md) — Wissensgraph
  des Codes mit Graphify erzeugen und in Obsidian öffnen; warum
  `graphify-out/` nicht ins Repo gehört
- [`docs/claude-cloud-setup.md`](docs/claude-cloud-setup.md) — Claude-Code-
  Cloud-Sessions einrichten: Plugins über das Setup-Skript der Umgebung,
  Projekt-Abhängigkeiten über einen SessionStart-Hook
- [`docs/Sportfabrik-Inventory-Uebersicht-Geschaeftsleitung.docx`](docs/Sportfabrik-Inventory-Uebersicht-Geschaeftsleitung.docx) —
  kurze, nicht-technische Zusammenfassung für die Geschäftsleitung (kein
  Ersatz für die obigen technischen Dokumente)
- `docs/Sportfabrik-Inventory-Dokumentation.docx` — dieselben Inhalte wie
  oben als ein zusammenhängendes Word-Dokument; bewusst **nicht** im Repo
  (siehe `.gitignore`), da es bei jeder grösseren Änderung neu aus den
  Markdown-Dokumenten oben generiert statt manuell gepflegt wird

## Ordnerstruktur

```
app/
  main.py            Einstiegspunkt: FastAPI-App, Middleware, Router-Registrierung
  core/              Datenbankverbindung, Modelle, Passwort-Hashing
    database.py
    models.py          SQLAlchemy-Modelle des neuen Datenmodells (siehe docs/datenmodell.md)
    security.py
    lagerorte.py       Seed-Daten SF1-SF4 + GEWA/VEBO/DIETIKON (siehe app/services/lagerorte.py für Lesezugriffe)
    lieferanten.py     Seed-Daten Lieferanten (aktuell nur INTERSPORT; parser_key = Modul in app/services/parsers/)
    kategorien.py      Seed-Daten Kassenkategorien (Hauptgruppe x Sportbereich, 35 Kombinationen)
    fedas.py           FEDAS-Code -> Kassenkategorie-Vorschlag (Phase B, siehe docs/projekt-kontext.md)
                       -> von Hand gewaehlt wird in app/services/kategorien.py
    i18n.py            translate()/normalize_language(): Katalog aus app/static/i18n/*.json lesen
  routers/           HTTP-Endpunkte (Seiten + JSON-API), gruppiert nach Thema
    auth.py            Anmeldung/Abmeldung, RBAC-Dependencies, Filialwechsel, Sprachwahl (/api/me, /api/active-lagerort, /api/language)
    catalog.py         Artikelsuche, Excel-Export
    dashboard.py       Übersichtsseite
    history.py         Rechnungsliste, -details, Artikelhistorie, Löschen
    article_details.py Notizen und Preisverlauf je Artikel
    preview.py         Upload-Vorschau, Korrekturvalidierung, Importbestätigung
    wareneingang.py    Erwartete Lieferungen ansehen und ihre Ankunft bestätigen
    erfassung.py       Ware von Hand erfassen (Scanner-Nachschlag über die EAN, Buchen ohne Beleg)
    etiketten.py       EAN nachtragen/erzeugen und Etiketten als PDF drucken
    kategorien.py      Kassenkategorie ansehen und von Hand waehlen (/api/kategorien)
    bestand.py         Bestand je Filiale ansehen (/bestand, /api/bestand)
    ausbuchung.py      Ausbuchen per Scan, ein Stueck je Scan, Rueckgaengig (/ausbuchen, /api/ausbuchen)
    umlagerung.py      Ware beim Empfang umlagern (/umlagern, /api/umlagerung)
  services/          Fachlogik ohne HTTP-Bezug, wiederverwendbar
    importer.py        Transaktionaler Import/Löschung von Rechnungen (bucht Wareneingang + Bestand gegen die aktive Filiale)
    parsers/           Ein Modul je Lieferanten-Layout + Registry (siehe docs/architektur.md)
      __init__.py        Registry: Layout/Lieferant erkennen (parse_document, UnknownLayoutError)
      base.py            Gemeinsame Bausteine: PDF einmal einlesen (inkl. OCR), Zeilen/Zahlen
      intersport.py      INTERSPORT-Rechnungen (auch ECOM) in Positionen umwandeln (inkl. FEDAS-Code)
    ocr.py              OCR-Fallback (Tesseract) für gescannte Seiten ohne Textebene
    corrections.py      Manuelle Korrekturen in der Vorschau validieren
    article_groups.py  Farb-/Grössenvarianten desselben Artikels über die echte artikel_id-Beziehung gruppieren
    article_export.py  Artikelliste als formatierte .xlsx-Datei
    lagerorte.py        Lagerort-Zuordnung eines Benutzers lesen (Filialwechsel, Ziel eines Wareneingangs)
    lieferadresse.py    Lagerort aus der Lieferadresse eines Dokuments erkennen (Vorschlag)
    wareneingang.py     Erwartete Lieferungen, Ankunft bestaetigen, Zugang buchen
    manuelle_erfassung.py Ware ohne Beleg direkt einbuchen (D23/D27)
    artikel.py          Artikel- und Variantenregeln (Regel 4/5) fuer Import und Erfassung gemeinsam
    ean.py              Pruefziffer, Pruefung und interne EAN-13 (GS1 20-29)
    barcode.py          EAN-13/EAN-8 als Strichmuster (ohne Zusatzbibliothek)
    etikett.py          Etikett als PDF in Etikettengroesse (PyMuPDF)
    reduktion.py        Lagerdauer und Reduktionsstufe nach Regel 6
    kategorien.py       Kassenkategorie: Auswahlliste, von Hand setzen, nie ueberschreiben (B8)
    bestand.py          Bestand lesen: Menge je Variante x Lagerort, Filter und Kennzahlen (C2)
    ausbuchung.py       Verkauf/Abgang buchen und per Gegenbuchung aufheben (C3)
    umlagerung.py       Umlagerung mit Datumsregeln D13/D17/F10/F11 (C4)
  templates/         HTML-Seiten (von den Routern per FileResponse ausgeliefert)
  static/
    css/, js/          Stylesheet und Frontend-Skripte (Theme, Session, i18n, Vorschau, Artikeldetails)
    js/i18n.js           Katalog laden, data-i18n anwenden, window.SportfabrikI18n.t()
    i18n/{de,fr,en}.json Übersetzungs-Katalog (einzige Quelle, auch vom Backend gelesen)
    fonts/, img/        Selbst gehostete Schriftart, Logo
    BRAND-SOURCES.md    Herkunft von Logo/Schriftart, Markenfarben

migrations/          Alembic-Migrationen (siehe docs/SERVER-SETUP.md für den Ablauf)
scripts/
  manage_users.py    CLI zum Anlegen/Entfernen von Benutzern (Mitarbeiter/Filialleiter/Admin) und ihrer Filialzuordnung
  backup_inventory.py Geprüftes Backup von Datenbank und Original-PDFs (siehe docs/BACKUPS.md)
  claude-cloud-setup.sh   Plugins für Claude-Code-Cloud-Sessions (siehe docs/claude-cloud-setup.md)
  claude-session-deps.sh  Projekt-Abhängigkeiten in Cloud-Sessions (siehe docs/claude-cloud-setup.md)
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

Erstes Filialleiter-Konto anlegen, damit überhaupt eine Anmeldung möglich ist
(Lagerort-Codes: SF1-SF4 für die Filialen, GEWA/VEBO/DIETIKON für die externen
Standorte; der erste
angegebene Code wird als primäre Filiale gesetzt):

```powershell
python scripts/manage_users.py add-chef <kassennummer> "<Name>" SF1
```

(Der CLI-Befehl und die interne Rollenbezeichnung heissen weiterhin
`chef`/`add-chef` — nur die Oberfläche zeigt dafür „Filialleiter" an. Für ein
filialübergreifendes Admin-/Zentrale-Konto `add-admin <kassennummer> "<Name>"`
ohne Lagerort-Angabe verwenden.)

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
