# API-Referenz

Alle Endpunkte ausser `/login`, `/logout`, `/static/*` und `/db-test`
verlangen eine gültige Anmeldung; die mit 🔒 markierten zusätzlich eine
Chef-Rolle. Seiten-Endpunkte (HTML) leiten bei fehlender Anmeldung zu
`/login` um, JSON-Endpunkte antworten mit HTTP 401 bzw. 403 — siehe
`architektur.md`, Abschnitt „Sicherheitsmodell".

## Anmeldung

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/login` | Login-Seite |
| POST | `/login` | Kassennummer (+ Passwort bei Chefs) prüfen, Session setzen. Antwort `{"requires_password": true}`, wenn eine Chef-Kassennummer ohne Passwort gesendet wurde |
| POST | `/logout` | Session beenden, Redirect zu `/login` |
| GET | `/api/me` | Angemeldete Person: `{kassennummer, name, role}` |

## Übersicht

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/` | Übersichtsseite (Dashboard) |
| GET | `/api/dashboard` | Kennzahlen (Anzahl Artikel/Rechnungen/Positionen) + die letzten 5 importierten Rechnungen |

## Artikel

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/articles` | Artikelsuche-Seite |
| GET | `/api/brands` | Liste aller vorkommenden Marken |
| GET | `/api/articles` | Artikelsuche; Filter: `q`, `brand`, `ean`, `article_no`, `description`; Paginierung `page`/`page_size` |
| GET | `/api/articles/{product_id}/history` | Vollständige Lieferhistorie eines Artikels, neueste Rechnung zuerst |

## Rechnungen

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/invoices` | Rechnungsliste-Seite |
| GET | `/invoices/{id}` | Rechnungsdetail-Seite |
| GET | `/articles/{id}/history` | Artikelhistorie-Seite |
| GET | `/api/invoices` | Rechnungsliste; Filter `q` (Rechnungsnummer), Paginierung |
| GET | `/api/invoices/{invoice_id}` | Rechnungsdetails inkl. aller Positionen |
| DELETE | `/api/invoices/{invoice_id}` | 🔒 Rechnung inkl. Positionen und Original-Snapshots unwiderruflich löschen; betroffene Artikel-Kennzahlen werden neu berechnet |

## Upload & Import

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/preview` | 🔒 Upload-Seite |
| POST | `/upload-preview` | 🔒 PDF hochladen, Positionen als Vorschau zurückgeben (max. 20 MB, keine DB-Änderung) |
| POST | `/import-invoice` | 🔒 Import bestätigen; verlangt `expected_hash` (SHA-256 der geprüften Datei) und `confirmed=true` |

## Sonstiges

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/db-test` | Health-Check: prüft, ob die Datenbankverbindung steht (kein Auth nötig; wird vom Docker-Healthcheck verwendet) |
| GET | `/static/{pfad}` | Statische Dateien: `css/`, `js/`, `fonts/`, `img/` |
| GET | `/docs`, `/redoc`, `/openapi.json` | Automatisch generierte FastAPI-Dokumentation (Swagger/ReDoc) |

## Fehlerformat

JSON-Fehlerantworten folgen dem FastAPI-Standard `{"detail": "<deutsche Meldung>"}`.
Typische Statuscodes: `401` (nicht angemeldet), `403` (falsche Rolle),
`404` (Rechnung/Artikel nicht gefunden), `409` (Import abgelehnt, z. B.
Duplikat oder Hash-Konflikt), `413` (Datei zu gross), `422` (PDF konnte
nicht gelesen/geparst werden), `503` (Datenbank nicht erreichbar).
