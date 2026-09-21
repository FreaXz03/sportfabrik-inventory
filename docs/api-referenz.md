# API-Referenz

Alle Endpunkte ausser `/login`, `/logout`, `/static/*` und `/db-test`
verlangen eine gültige Anmeldung; die mit 🔒 markierten zusätzlich eine
Filialleiter- oder Admin-Rolle (intern weiterhin `chef`/`admin`). Seiten-Endpunkte
(HTML) leiten bei fehlender Anmeldung zu `/login` um, JSON-Endpunkte antworten
mit HTTP 401 bzw. 403 — siehe `architektur.md`, Abschnitt „Sicherheitsmodell".

Fehlermeldungen (`detail`) sind serverseitig lokalisiert: eingeloggt in der
Kontosprache des Benutzers, sonst (z. B. `/login`) nach dem
`Accept-Language`-Header — siehe `architektur.md`, Abschnitt „Mehrsprachigkeit
(i18n)".

## Anmeldung

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/login` | Login-Seite |
| POST | `/login` | Kassennummer (+ Passwort bei Filialleitern/Admin) prüfen, Session setzen. Antwort `{"requires_password": true}`, wenn eine Filialleiter-/Admin-Kassennummer ohne Passwort gesendet wurde |
| POST | `/logout` | Session beenden, Redirect zu `/login` |
| GET | `/api/me` | Angemeldete Person: `{kassennummer, name, role, role_label, language, lagerort, lagerorte, kann_alle_filialen_waehlen}`. `role_label` und Fehlermeldungen sind in `language` (`de`/`fr`/`en`) übersetzt. `lagerort` ist die aktive Filiale (`{id, code, name}` oder `null` = „alle Filialen", nur für Admin möglich), `lagerorte` die Filialen, zwischen denen gewechselt werden darf (Admin: alle) |
| POST | `/api/active-lagerort` | Aktive Filiale für die Session wechseln. Body `{"lagerort_id": <id oder null>}`; `null` nur für Admin erlaubt (= „alle Filialen"), sonst muss die Filiale dem Benutzer zugewiesen sein (sonst 403) |
| POST | `/api/language` | Sprache des angemeldeten Kontos setzen. Body `{"language": "de"｜"fr"｜"en"}`, sonst HTTP 422. Antwort `{"language": "..."}` |

Der `next`-Parameter von `/login?next=…` (wohin nach dem Login weitergeleitet
wird) wird clientseitig gegen eine Whitelist bekannter Routen geprüft
(`app/static/js/login-redirect.js`) — verhindert, dass ein manipulierter Link
nach dem Login auf eine fremde Seite weiterleitet (offener Redirect).

## Übersicht

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/` | Übersichtsseite (Dashboard) |
| GET | `/api/dashboard` | Kennzahlen (Anzahl Artikel/Rechnungen/Positionen, gelieferte Gesamtmenge) + die letzten 5 importierten Rechnungen |

## Artikel

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/articles` | Artikelsuche-Seite |
| GET | `/api/brands` | Liste aller vorkommenden Marken |
| GET | `/api/articles` | Artikelsuche; Filter: `q`, `brand`, `ean`, `supplier_article_no`, `description`, `last_delivery_from`/`last_delivery_to` (Datumsbereich auf die letzte Lieferung); Sortierung `sort_by` (`brand`, `description`, `supplier_article_no`, `ean`, `color`, `size`, `first_seen`, `last_seen`) + `sort_dir` (`asc`/`desc`); Paginierung `page`/`page_size` (max. 100) |
| GET | `/api/articles/export` | Dieselben Filter wie `/api/articles`, aber **ohne** Paginierung: liefert eine fertig formatierte Excel-Datei (`.xlsx`) mit allen Treffern zum Download |
| GET | `/api/articles/{product_id}/history` | Vollständige Lieferhistorie eines Artikels **inkl. aller Farb-/Grössenvarianten mit gleicher Marke + Lieferanten-Artikelnummer**, neueste Rechnung zuerst; sortierbar (`sort_by`/`sort_dir`, siehe unten) |
| GET | `/api/articles/{product_id}/prices` | Preisverlauf (UVP je Rechnung/Einheit) für die Artikelgruppe |
| GET | `/api/articles/{product_id}/notes` | Notizen zur Artikelgruppe, paginiert (`page`, 20 je Seite), neueste zuerst |
| POST | `/api/articles/{product_id}/notes` | Neue Notiz anlegen (`body`, max. 2000 Zeichen) |
| PUT | `/api/articles/{product_id}/notes/{note_id}` | Notiz bearbeiten; verlangt `version` der zuletzt gelesenen Notiz (optimistisches Sperren, sonst HTTP 409); nur eigene Notiz oder als Filialleiter |
| DELETE | `/api/articles/{product_id}/notes/{note_id}` | Notiz löschen; verlangt `version`; nur eigene Notiz oder als Filialleiter |

`sort_by` für Positionslisten (Rechnungsdetail und Artikelhistorie, siehe
unten) akzeptiert: `position`, `invoice_date`, `description`, `ean`,
`article_no`, `color`, `size`, `quantity`, `unit`, `uvp`. Fehlende Werte
werden ans Ende sortiert; `size` erkennt gängige Kleidergrössen (`XS`…`5XL`)
sowie gemischte Zahlen/Text (z. B. Schuhgrössen) und sortiert sie sinnvoll
statt rein alphabetisch. `article_no` (die frühere INTERSPORT-eigene
Artikelnummer) wird seit dem neuen Datenmodell (Phase A Punkt 3) nicht mehr
als eigene Spalte geführt — der Wert kommt hier, sofern vorhanden, aus dem
unveränderten Original-Snapshot der Position.

## Rechnungen

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/invoices` | Rechnungsliste-Seite |
| GET | `/invoices/{id}` | Rechnungsdetail-Seite |
| GET | `/articles/{id}/history` | Artikelhistorie-Seite (inkl. Notizen und Preisverlauf) |
| GET | `/api/invoices` | Rechnungsliste; Filter `q` (Rechnungsnummer), Paginierung |
| GET | `/api/invoices/{invoice_id}` | Rechnungsdetails inkl. aller Positionen; sortierbar (`sort_by`/`sort_dir`, siehe oben) |
| DELETE | `/api/invoices/{invoice_id}` | 🔒 Rechnung inkl. Positionen und Original-Snapshots unwiderruflich löschen; betroffene Artikel-Kennzahlen werden neu berechnet |

## Upload & Import

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/preview` | 🔒 Upload-Seite (unterstützt mehrere PDFs gleichzeitig, siehe „Stapel-Import" unten) |
| POST | `/upload-preview` | 🔒 Eine PDF hochladen, Lieferant/Dokumenttyp erkennen und Positionen als Vorschau zurückgeben (max. 20 MB, keine DB-Änderung) |
| POST | `/validate-preview` | 🔒 Manuell korrigierte Positionen (siehe `corrections`) gegen dieselbe Datei erneut validieren, bevor importiert wird; verlangt `expected_hash` |
| POST | `/import-invoice` | 🔒 Import bestätigen; verlangt `expected_hash` (SHA-256 der geprüften Datei), `confirmed=true`, optional `corrections` (JSON, siehe unten) und optional `lagerort_id` (Ziel des Wareneingangs, siehe unten). Ohne `lagerort_id` wird gegen die aktive Filiale des Kontos gebucht (`GET /api/me`, `lagerort`) — ohne gewählte Filiale (nur für Admin möglich, alle Filialen) HTTP 400 |
| GET | `/invoice-import-status` | 🔒 Prüft per Datei-Hash (`file_hash`) oder per Belegnummer **beim erkannten Lieferanten** (`invoice_number` **und** `parser_key`, beide aus der Vorschau-Antwort), ob eine Rechnung bereits importiert ist — wird von der Stapel-Import-Warteschlange genutzt, um bereits importierte Dateien zu überspringen. Ohne `parser_key` zählt nur der Datei-Hash: dieselbe Belegnummer kann bei einem anderen Lieferanten eine völlig andere Rechnung sein |

**Warnungen und Hinweise je Position**: Jede Position der Antwort hat zwei
Listen — `warnings` (blockiert den Import, bis geprüft/korrigiert) und `hints`
(nicht blockierend, aktuell: Position ohne EAN, Regel 5). Dazu die Zähler
`rows_with_warnings` und `rows_with_hints`. `/import-invoice` weist ein
Dokument nur wegen `warnings` ab, nie wegen `hints`.

**Ziel-Lagerort (`/upload-preview`, `/validate-preview`, `/import-invoice`)**:
Die Vorschau liefert `lagerort_suggestion` (aus der Lieferadresse erkannt, mit
`code`, `name`, `from_delivery_address` und den getroffenen Merkmalen — `null`,
wenn nichts Eindeutiges gefunden wurde), `lagerort_options` (worauf dieses
Konto buchen darf, eigene Filiale zuerst) und `lagerort_active` (aktive
Filiale). `/import-invoice` nimmt dazu das Formularfeld `lagerort_id`; fehlt
es, wird gegen die aktive Filiale gebucht. Ein unbekannter Lagerort ergibt
HTTP 403 (D19, siehe docs/architektur.md).

**Erkannter Lieferant (`/upload-preview`, `/validate-preview`)**: Die Antwort
enthält neben den Positionen `parser_key` (zuständiges Parser-Modul, =
`lieferanten.parser_key`), `supplier_name` (Anzeige in der Vorschau) und
`document_type` (`rechnung`, `lieferschein`, `auftragsbestaetigung`,
`bestellung` — `null`, wenn der Typ im Dokument nicht erkennbar ist). Ist das
Layout unbekannt, antwortet der Upload mit HTTP 422 und der Meldung, dass das
Dokumentlayout noch nicht bekannt ist (siehe docs/architektur.md, „PDF-Parsing").

**Korrekturen (`corrections`)**: JSON-Objekt `{"<Positionsnummer>": {"<Feld>": "<neuer Wert>"}}`.
Erlaubte Felder: `brand`, `supplier_article_no`, `article_no`, `ean`,
`description`, `color`, `size`, `quantity`, `unit`, `uvp` — `ean`, `color` und
`size` dürfen leer bleiben (Regel 5). Der Server validiert jede Position
vollständig neu (Pflichtfelder, EAN-Format sofern eine EAN eingetragen ist,
Zahlenformat) statt der übermittelten Werte blind zu vertrauen; jede
tatsächliche Änderung wird als `correction_audit` (vorher/nachher, wer, wann)
dauerhaft mit der Position gespeichert.

**Stapel-Import**: Die Upload-Seite erlaubt die Auswahl mehrerer PDFs auf
einmal. Jede Datei durchläuft einzeln Vorschau → Prüfung → Bestätigung; der
Browser verarbeitet die Warteschlange automatisch weiter, sobald eine Datei
importiert ist, und markiert bereits importierte oder fehlerhafte Dateien
sichtbar (Zustände: wartend, bereit, Duplikat, Fehler, importiert). Serverseitig
ist das keine Sonderfunktion — jede Datei läuft durch denselben
Upload/Validierungs-/Import-Ablauf wie ein Einzel-Upload.

## Erwartete Lieferungen (Wareneingang)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/wareneingaenge` | Seite „Erwartete Lieferungen" (jede Anmeldung) |
| GET | `/api/wareneingaenge` | Offene (erwartete) Lieferungen der aktiven Filiale samt Positionen; ohne aktive Filiale (Admin) alle |
| POST | `/api/wareneingaenge/{id}/ankunft` | Ankunft bestätigen: `{"mengen": {"<positions-id>": "<menge>"}, "eingangsdatum": "YYYY-MM-DD"}`. Bucht den Zugang, setzt das Eingangsdatum (rückwirkend möglich) und schliesst die Lieferung, sobald keine Position mehr offen ist |

Auch **Mitarbeiter** dürfen bestätigen (D21) — das ist Lagerarbeit, kein
Dokumentrecht. Unplausible Mengen, fremde Positionen oder eine bereits
vollständig eingetroffene Lieferung ergeben HTTP 409, ein ungültiges Datum
HTTP 422; gebucht wird in beiden Fällen nichts.

## Ware von Hand erfassen (ohne Beleg)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/erfassen` | Seite „Ware erfassen" (jede Anmeldung) |
| GET | `/api/erfassen/stammdaten` | Auswahllisten: buchbare Lagerorte (eigene zuerst, D26), bekannte Lieferanten, heutiges Datum vom Server |
| GET | `/api/erfassen/variante?ean=<ean>` | Nachschlag für den Scanner: `{"gefunden": true, "variante": {…}}` mit Marke, Bezeichnung, Farbe, Grösse, Einheit und letztem UVP/EK als Vorschlag; unbekannte EAN ergibt `{"gefunden": false, "variante": null}` |
| POST | `/api/erfassen` | Alle Positionen als **einen** Wareneingang ohne Beleg buchen (D27) |

Rumpf von `POST /api/erfassen`:

```json
{
  "positionen": [
    {"marke": "Nike", "bezeichnung": "Poloshirt Court", "menge": "3", "uvp": "39.90",
     "ean": "4006632041234", "farbe": "Weiss", "groesse": "M", "einheit": "Stk",
     "lieferanten_artikelnr": "A1", "ek": "19.95"}
  ],
  "lagerort_id": 1,
  "lieferant_id": null,
  "eingangsdatum": "2026-09-21"
}
```

Pflicht sind nur `marke`, `bezeichnung`, `menge` und `uvp` (D23); alles andere
darf fehlen (Regel 5/10). Mengen und Preise sind **Text**, damit nichts über
`float` läuft (Komma wird akzeptiert). Unbekannte Felder werden abgewiesen
(HTTP 422). Ohne `lagerort_id` gilt die aktive Filiale, `eingangsdatum` ist
ohne Angabe heute — in einem Lager ohne Verkauf bleibt es leer (Regel 6).

Antwort: `{"wareneingang_id": …, "lagerort": {…}, "positionen": 2,
"neue_varianten": 1, "bekannte_varianten": 1, "eingangsdatum": "2026-09-21"}`.

Auch **Mitarbeiter** dürfen erfassen (Regel 9/D21) — es entsteht kein
Dokument. Unplausible Eingaben (fehlendes Pflichtfeld, Menge ≤ 0, ungültige
EAN, Datum in der Zukunft) ergeben HTTP 409 und buchen **nichts**; ein
Lagerort ohne Zugriff ergibt HTTP 403, ein ungültiges Datumsformat HTTP 422.

## Sonstiges

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/db-test` | Health-Check: prüft, ob die Datenbankverbindung steht (kein Auth nötig; wird vom Docker-Healthcheck verwendet) |
| GET | `/static/{pfad}` | Statische Dateien: `css/`, `js/`, `fonts/`, `img/` |
| GET | `/docs`, `/redoc`, `/openapi.json` | Automatisch generierte FastAPI-Dokumentation (Swagger/ReDoc) |

## Fehlerformat

JSON-Fehlerantworten folgen dem FastAPI-Standard `{"detail": "<deutsche Meldung>"}`.
Typische Statuscodes: `400` (z. B. Import ohne gewählte Filiale), `401`
(nicht angemeldet), `403` (falsche Rolle oder keine Filialzuweisung),
`404` (Rechnung/Artikel/Notiz nicht gefunden), `409` (Import abgelehnt, z. B.
Duplikat oder Hash-Konflikt; oder Notiz wurde zwischenzeitlich geändert),
`413` (Datei zu gross), `422` (PDF konnte nicht gelesen/geparst werden, oder
ungültige Korrekturdaten), `503` (Datenbank nicht erreichbar).
