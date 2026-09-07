# API-Referenz

Alle Endpunkte ausser `/login`, `/logout`, `/static/*` und `/db-test`
verlangen eine gültige Anmeldung; die mit 🔒 markierten zusätzlich eine
Filialleiter-Rolle (intern weiterhin `chef`). Seiten-Endpunkte (HTML) leiten
bei fehlender Anmeldung zu `/login` um, JSON-Endpunkte antworten mit
HTTP 401 bzw. 403 — siehe `architektur.md`, Abschnitt „Sicherheitsmodell".

## Anmeldung

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/login` | Login-Seite |
| POST | `/login` | Kassennummer (+ Passwort bei Filialleitern) prüfen, Session setzen. Antwort `{"requires_password": true}`, wenn eine Filialleiter-Kassennummer ohne Passwort gesendet wurde |
| POST | `/logout` | Session beenden, Redirect zu `/login` |
| GET | `/api/me` | Angemeldete Person: `{kassennummer, name, role}` |

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
| GET | `/api/articles` | Artikelsuche; Filter: `q`, `brand`, `ean`, `article_no`, `description`, `last_delivery_from`/`last_delivery_to` (Datumsbereich auf die letzte Lieferung); Sortierung `sort_by` (`brand`, `description`, `article_no`, `supplier_article_no`, `ean`, `color`, `size`, `first_seen`, `last_seen`) + `sort_dir` (`asc`/`desc`); Paginierung `page`/`page_size` (max. 100) |
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
statt rein alphabetisch.

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
| POST | `/upload-preview` | 🔒 Eine PDF hochladen, Positionen als Vorschau zurückgeben (max. 20 MB, keine DB-Änderung) |
| POST | `/validate-preview` | 🔒 Manuell korrigierte Positionen (siehe `corrections`) gegen dieselbe Datei erneut validieren, bevor importiert wird; verlangt `expected_hash` |
| POST | `/import-invoice` | 🔒 Import bestätigen; verlangt `expected_hash` (SHA-256 der geprüften Datei), `confirmed=true` und optional `corrections` (JSON, siehe unten) |
| GET | `/invoice-import-status` | 🔒 Prüft per Datei-Hash oder Rechnungsnummer, ob eine Rechnung bereits importiert ist — wird von der Stapel-Import-Warteschlange genutzt, um bereits importierte Dateien zu überspringen |

**Korrekturen (`corrections`)**: JSON-Objekt `{"<Positionsnummer>": {"<Feld>": "<neuer Wert>"}}`.
Erlaubte Felder: `brand`, `supplier_article_no`, `article_no`, `ean`,
`description`, `color`, `size`, `quantity`, `unit`, `uvp`. Der Server
validiert jede Position vollständig neu (Pflichtfelder, EAN-Format,
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

## Sonstiges

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/db-test` | Health-Check: prüft, ob die Datenbankverbindung steht (kein Auth nötig; wird vom Docker-Healthcheck verwendet) |
| GET | `/static/{pfad}` | Statische Dateien: `css/`, `js/`, `fonts/`, `img/` |
| GET | `/docs`, `/redoc`, `/openapi.json` | Automatisch generierte FastAPI-Dokumentation (Swagger/ReDoc) |

## Fehlerformat

JSON-Fehlerantworten folgen dem FastAPI-Standard `{"detail": "<deutsche Meldung>"}`.
Typische Statuscodes: `401` (nicht angemeldet), `403` (falsche Rolle),
`404` (Rechnung/Artikel/Notiz nicht gefunden), `409` (Import abgelehnt, z. B.
Duplikat oder Hash-Konflikt; oder Notiz wurde zwischenzeitlich geändert),
`413` (Datei zu gross), `422` (PDF konnte nicht gelesen/geparst werden, oder
ungültige Korrekturdaten), `503` (Datenbank nicht erreichbar).
