# Datenmodell

Acht Tabellen, verwaltet über SQLAlchemy 2.0 (`app/core/models.py`) und
Alembic-Migrationen (`migrations/`).

```mermaid
erDiagram
    PRODUCTS ||--o{ INVOICE_ITEMS : "wird geliefert in"
    INVOICES ||--o{ INVOICE_ITEMS : "enthält"
    INVOICE_ITEMS ||--o| INVOICE_ITEM_SOURCES : "Original-Snapshot"
    PRODUCTS ||--o{ ARTICLE_NOTES : "hat"
    USERS ||--o{ BENUTZER_LAGERORTE : "zugeordnet zu"
    LAGERORTE ||--o{ BENUTZER_LAGERORTE : "hat Benutzer"

    PRODUCTS {
        int id PK
        string brand
        string supplier_article_no
        string article_no
        string ean UK
        string description
        string color
        string size
        date first_seen
        date last_seen
    }
    INVOICES {
        int id PK
        string invoice_number UK
        date invoice_date
        date document_date
        string supplier
        string filename
        string file_hash UK
        datetime uploaded_at
        string imported_by_kassennummer
        string imported_by_name
        boolean ocr_used
    }
    INVOICE_ITEMS {
        int id PK
        int invoice_id FK
        int product_id FK
        numeric quantity
        string unit
        numeric uvp
    }
    INVOICE_ITEM_SOURCES {
        int item_id PK_FK
        json data
    }
    ARTICLE_NOTES {
        int id PK
        int product_id FK
        string body
        int author_user_id
        string author_name
        string author_number
        string updated_by
        datetime created_at
        datetime updated_at
        int version
    }
    USERS {
        int id PK
        string kassennummer UK
        string name
        string role
        string password_hash
        string language
        datetime created_at
    }
    LAGERORTE {
        int id PK
        string code UK
        string name
        string strasse
        string plz
        string ort
        string telefon
        string email
        boolean verkauf
    }
    BENUTZER_LAGERORTE {
        int user_id PK_FK
        int lagerort_id PK_FK
        boolean ist_primaer
    }
```

`USERS` steht bewusst ohne Verknüpfungslinie zu `INVOICES` oder
`ARTICLE_NOTES`: wer eine Rechnung importiert bzw. eine Notiz verfasst hat,
wird als Momentaufnahme (`imported_by_*` bzw. `author_name`/`author_number`)
direkt gespeichert, nicht als Fremdschlüssel — siehe Entscheidung E5 in
`planung.md`. `article_notes.author_user_id` ist zwar eine Nutzer-ID, aber
absichtlich ohne Fremdschlüssel-Constraint auf `users.id`: eine Notiz bleibt
so lesbar und ihrem ursprünglichen Autor zuordenbar, selbst wenn das
zugehörige Benutzerkonto später entfernt wird.

## Tabellen im Detail

### `products`
Ein Datensatz je eindeutigem Artikel (Schlüssel: `ean`). Wird bei jedem
Import wiederverwendet, wenn die EAN bereits bekannt ist — Marke,
Artikelnummer usw. stammen dann von der ersten Lieferung, spätere
Lieferungen liefern nur neue Mengen/Preise. `first_seen`/`last_seen` werden
bei jedem Import und jeder Löschung neu berechnet.

Für Notizen, Preisverlauf und Lieferhistorie werden **Varianten desselben
Artikels** (gleiche Marke + gleiche Lieferanten-Artikelnummer, z. B.
verschiedene Farben/Grössen) serverseitig zu einer Gruppe zusammengefasst
(`app/services/article_groups.py`) — Artikel ohne Lieferanten-Artikelnummer
bleiben einzeln. Das ist eine reine Abfrage-Gruppierung zur Anzeige; in der
Tabelle bleibt jede EAN-Variante ein eigener `products`-Datensatz.

### `invoices`
Ein Datensatz je importierter Rechnung. `invoice_number` und `file_hash`
sind eindeutig — verhindert Doppelimporte derselben Rechnung. `supplier`
ist aktuell immer `"INTERSPORT Schweiz AG"` (siehe offener Punkt: weitere
Lieferanten). `imported_by_kassennummer`/`imported_by_name` sind nullable,
weil sie erst nachträglich eingeführt wurden — vor September 2026
importierte Rechnungen zeigen hier „—". `ocr_used` markiert Rechnungen, die
mangels Textebene per Tesseract-OCR statt direkt aus dem PDF gelesen wurden
(siehe `architektur.md`, Abschnitt OCR-Fallback).

### `invoice_items`
Eine Zeile je Position einer Rechnung (kann mehrfach dieselbe `product_id`
referenzieren, z. B. Farbvarianten oder Nachlieferungen). `quantity` und
`uvp` als `Numeric(10, 2)` für exakte Dezimalwerte statt Fliesskomma.

### `invoice_item_sources`
Ein optionaler 1:1-Datensatz je `invoice_items`-Zeile mit den kompletten,
unveränderten Originaldaten der Position (inkl. Rohtext, Seiten-/Zeilennummer,
etwaige Parser-Warnungen sowie ein `correction_audit`-Feld, falls die Position
vor dem Import manuell korrigiert wurde — siehe `architektur.md`, Abschnitt
„Korrekturen in der Vorschau") als JSON. Bleibt erhalten, auch wenn sich die
`products`-Stammdaten später ändern — Grundlage des Audit-Trails.

### `article_notes`
Freitext-Notizen zu einem Artikel bzw. einer Artikelgruppe (z. B. „Grösse M
läuft schlecht, wenig nachbestellen"). Jede Notiz trägt eine Autor-Momentaufnahme
(`author_name`, `author_number`) und ein `version`-Feld für optimistisches
Sperren: Bearbeiten/Löschen verlangt die zuletzt gelesene `version`, sonst
schlägt die Anfrage mit HTTP 409 fehl (verhindert, dass zwei Personen
gleichzeitig dieselbe Notiz widersprüchlich ändern). Mitarbeiter dürfen nur
eigene Notizen bearbeiten/löschen, Filialleiter alle.

### `users`
Ein Datensatz je Kassennummer. Drei Check-Constraints erzwingen auf
Datenbankebene, dass `role` nur `mitarbeiter`, `chef` oder `admin` sein kann,
dass ausschliesslich Chefs/Admins (intern weiterhin als Rolle `chef`
gespeichert, in der Oberfläche als „Filialleiter" beschriftet, bzw. `admin`
als „Zentrale") einen `password_hash` besitzen (Mitarbeiter: immer `NULL`),
und dass `language` nur `de`, `fr` oder `en` sein kann (Default `de`, Regel 7:
Deutsch ist Standard, jederzeit pro Benutzer umstellbar über
`POST /api/language` — siehe `app/core/i18n.py`, `app/static/js/i18n.js`).
Rechte gemäss CLAUDE.md Regel 9: Mitarbeiter alles ausser Dokumente
hochladen/bearbeiten/löschen, Filialleiter zusätzlich Dokumente,
Admin/Zentrale filialübergreifend (siehe `app/routers/auth.py`).

### `lagerorte`
Die 4 Filialen (SF1 Volketswil, SF2 Regensdorf, SF3 Hägendorf, SF4 Conthey,
`verkauf = true`) sowie das externe Aufbereitungslager GEWA (`verkauf =
false`, kein Verkauf). Seed-Daten in `app/core/lagerorte.py`, per
Alembic-Migration `a1b2c3d4e5f6` eingefügt. `strasse`/`plz`/`ort` dienen
später auch der automatischen Filial-Erkennung aus der Lieferadresse eines
hochgeladenen Dokuments (Phase B).

### `benutzer_lagerorte`
Ordnet einen Benutzer einer oder mehreren Filialen zu (m:n, z. B. Aushilfe an
mehreren Standorten). `ist_primaer` markiert die nach dem Login vorausgewählte
Filiale; darüber hinaus kann in der Oberfläche jederzeit zwischen den
zugewiesenen Filialen gewechselt werden (`/api/active-lagerort`,
Session-Feld `active_lagerort_id`). Admin-Konten (Rolle `admin`) haben
keinen Eintrag hier — sie gelten als filialübergreifend und können
zusätzlich „Alle Filialen" wählen (kein aktiver Lagerort). Bestehende
Benutzer wurden bei der Migration auf SF1 (Volketswil) als primäre Filiale
gesetzt.

## Migrationshistorie

| Revision | Beschreibung |
|---|---|
| `5ce94c6a96e3` | Baseline: `products`, `invoices`, `invoice_items`, `invoice_item_sources` |
| `7129c5082ac9` | `users`-Tabelle inkl. beider Check-Constraints |
| `246c67c1d45e` | `imported_by_kassennummer`/`imported_by_name` auf `invoices` |
| `d567ef887517` | `ocr_used` (Boolean, Default `false`) auf `invoices` |
| `e901abc23456` | Neue Tabelle `article_notes` inkl. Autor-Snapshot und Versionsfeld |
| `a1b2c3d4e5f6` | Neue Tabellen `lagerorte` (SF1-SF4 + GEWA, Seed-Daten) und `benutzer_lagerorte` (m:n); `users.role` um `admin` erweitert; bestehende Benutzer auf SF1 zugeordnet |
| `b2c3d4e5f6a7` | `users.language` (DE/FR/EN, Default `de`) inkl. Check-Constraint |

Schema-Änderungen laufen ausschliesslich über Alembic
(`alembic revision --autogenerate`); der Container führt beim Start
automatisch `alembic upgrade head` aus (siehe `SERVER-SETUP.md`).
