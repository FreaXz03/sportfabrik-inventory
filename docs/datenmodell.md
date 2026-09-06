# Datenmodell

Fünf Tabellen, verwaltet über SQLAlchemy 2.0 (`app/core/models.py`) und
Alembic-Migrationen (`migrations/`).

```mermaid
erDiagram
    PRODUCTS ||--o{ INVOICE_ITEMS : "wird geliefert in"
    INVOICES ||--o{ INVOICE_ITEMS : "enthält"
    INVOICE_ITEMS ||--o| INVOICE_ITEM_SOURCES : "Original-Snapshot"

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
    USERS {
        int id PK
        string kassennummer UK
        string name
        string role
        string password_hash
        datetime created_at
    }
```

`USERS` steht bewusst ohne Verknüpfungslinie zu `INVOICES`: wer eine
Rechnung importiert hat, wird als Momentaufnahme (`imported_by_*`) direkt
auf `INVOICES` gespeichert, nicht als Fremdschlüssel — siehe Entscheidung
E5 in `planung.md`.

## Tabellen im Detail

### `products`
Ein Datensatz je eindeutigem Artikel (Schlüssel: `ean`). Wird bei jedem
Import wiederverwendet, wenn die EAN bereits bekannt ist — Marke,
Artikelnummer usw. stammen dann von der ersten Lieferung, spätere
Lieferungen liefern nur neue Mengen/Preise. `first_seen`/`last_seen` werden
bei jedem Import und jeder Löschung neu berechnet.

### `invoices`
Ein Datensatz je importierter Rechnung. `invoice_number` und `file_hash`
sind eindeutig — verhindert Doppelimporte derselben Rechnung. `supplier`
ist aktuell immer `"INTERSPORT Schweiz AG"` (siehe Anforderung F-offen:
weitere Lieferanten). `imported_by_kassennummer`/`imported_by_name` sind
nullable, weil sie erst nachträglich eingeführt wurden — vor September 2026
importierte Rechnungen zeigen hier „—".

### `invoice_items`
Eine Zeile je Position einer Rechnung (kann mehrfach dieselbe `product_id`
referenzieren, z. B. Farbvarianten oder Nachlieferungen). `quantity` und
`uvp` als `Numeric(10, 2)` für exakte Dezimalwerte statt Fliesskomma.

### `invoice_item_sources`
Ein optionaler 1:1-Datensatz je `invoice_items`-Zeile mit den kompletten,
unveränderten Originaldaten der Position (inkl. Rohtext, Seiten-/Zeilennummer,
etwaige Parser-Warnungen) als JSON. Bleibt erhalten, auch wenn sich die
`products`-Stammdaten später ändern — Grundlage des Audit-Trails.

### `users`
Ein Datensatz je Kassennummer. Zwei Check-Constraints erzwingen auf
Datenbankebene, dass `role` nur `mitarbeiter` oder `chef` sein kann und dass
ausschliesslich Chefs einen `password_hash` besitzen (Mitarbeiter: immer
`NULL`).

## Migrationshistorie

| Revision | Beschreibung |
|---|---|
| `5ce94c6a96e3` | Baseline: `products`, `invoices`, `invoice_items`, `invoice_item_sources` |
| `7129c5082ac9` | `users`-Tabelle inkl. beider Check-Constraints |
| `246c67c1d45e` | `imported_by_kassennummer`/`imported_by_name` auf `invoices` |

Schema-Änderungen laufen ausschliesslich über Alembic
(`alembic revision --autogenerate`); der Container führt beim Start
automatisch `alembic upgrade head` aus (siehe `SERVER-SETUP.md`).
