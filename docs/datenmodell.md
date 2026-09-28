# Data model

Managed via SQLAlchemy 2.0 (`app/core/models.py`) and Alembic migrations
(`migrations/`). Since migration `c3d4e5f6a7b8` (Phase A, item 3), the data
model from `projekt-kontext.md` section 8.2 applies: item master shared
across branches, stock/goods receipts/markdowns are branch-specific, stock
is never overwritten directly but kept as a `lagerbewegungen` journal
(rule 2).

## Old tables (`products`, `invoices`, `invoice_items`,
`invoice_item_sources`)

Stay untouched in the database (no `DROP`, "never discard"), but are
**no longer mapped** — the app has not read/written them since
`c3d4e5f6a7b8`. Their data was fully migrated into the new tables (see
"Migrating the legacy data" below). One exception:
`products.article_no` (the INTERSPORT-internal item number per variant) is
**not** carried over — the new model only keeps the supplier item number
(`artikel.lieferanten_artikelnr`) as the item key (rule 5); the historical
value remains visible in the old, untouched `products` table.

## New tables

```mermaid
erDiagram
    LIEFERANTEN ||--o{ ARTIKEL : "supplies"
    KATEGORIEN ||--o{ ARTIKEL : "categorizes"
    ARTIKEL ||--o{ VARIANTEN : "has"
    VARIANTEN ||--o{ PREISE : "price history"
    VARIANTEN ||--o{ WARENEINGANG_POSITIONEN : "line in"
    VARIANTEN ||--o{ LAGERBEWEGUNGEN : "affects"
    VARIANTEN ||--o{ BESTAND : "stock per branch"
    ARTIKEL ||--o{ ARTICLE_NOTES : "has notes"
    LIEFERANTEN ||--o{ DOKUMENTE : "sender"
    LAGERORTE ||--o{ DOKUMENTE : "target branch"
    DOKUMENTE ||--o{ WARENEINGAENGE : "creates"
    LAGERORTE ||--o{ WARENEINGAENGE : "branch"
    WARENEINGAENGE ||--o{ WARENEINGANG_POSITIONEN : "contains"
    WARENEINGANG_POSITIONEN ||--o| WARENEINGANG_POSITIONEN_QUELLE : "original snapshot"
    DOKUMENTE ||--o{ PREISE : "source"
    LAGERORTE ||--o{ LAGERBEWEGUNGEN : "branch"
    LAGERORTE ||--o{ BESTAND : "branch"
    WARENEINGANG_POSITIONEN ||--o| LAGERBEWEGUNGEN : "creates receipt"

    LIEFERANTEN {
        int id PK
        string name UK
        string typ
        string parser_key
    }
    KATEGORIEN {
        int id PK
        string hauptgruppe
        string sportbereich
    }
    ARTIKEL {
        int id PK
        int lieferant_id FK
        string marke
        string lieferanten_artikelnr
        string bezeichnung
        int kategorie_id FK
        bool kategorie_manuell
        string fedas_code
    }
    VARIANTEN {
        int id PK
        int artikel_id FK
        string farbe
        string groesse
        string ean UK
        boolean ean_intern
        date first_seen
        date last_seen
    }
    PREISE {
        int id PK
        int varianten_id FK
        numeric uvp
        numeric ek
        date datum
        int dokument_id FK
    }
    DOKUMENTE {
        int id PK
        int lieferant_id FK
        int lagerort_id FK
        string typ
        string dokumentnummer UK
        date dokumentdatum
        date belegdatum
        string dateiname
        string datei_hash UK
        datetime hochgeladen_am
        string hochgeladen_von_kassennummer
        string hochgeladen_von_name
        boolean ocr_verwendet
    }
    WARENEINGAENGE {
        int id PK
        int dokument_id FK
        int lagerort_id FK
        string status
        date eingangsdatum
    }
    WARENEINGANG_POSITIONEN {
        int id PK
        int wareneingang_id FK
        int varianten_id FK
        numeric menge
        string einheit
        numeric uvp
        numeric ek
    }
    WARENEINGANG_POSITIONEN_QUELLE {
        int position_id PK_FK
        json data
    }
    LAGERBEWEGUNGEN {
        int id PK
        int lagerort_id FK
        int varianten_id FK
        string typ
        numeric menge
        string grund
        date eingangsdatum
        int wareneingang_position_id FK
        string benutzer_kassennummer
        string benutzer_name
        datetime zeitpunkt
    }
    BESTAND {
        int varianten_id PK_FK
        int lagerort_id PK_FK
        numeric menge
        date aeltestes_eingangsdatum
    }
    ARTICLE_NOTES {
        int id PK
        int artikel_id FK
        string body
        int author_user_id
        string author_name
        string author_number
        string updated_by
        datetime created_at
        datetime updated_at
        int version
    }
```

`article_notes.artikel_id` (before `c3d4e5f6a7b8`: `product_id`), like
`dokumente`/`lagerbewegungen`, deliberately has no foreign key to
`users.id` for the author — see the rationale further below under `users`.

## Tables in detail

### `lieferanten`
One row per supplier. `typ` (`intersport`/`ecom`/`drittanbieter`/
`extern`/`intern`) is also the **supplier group**, from which the label
code follows (Intersport 111, ECOM 555, dealer = `extern` 333,
third-party dealer = `drittanbieter` 999, internal = Nike/adidas/The North
Face 444; since 2026-09-24, migration `f2a3b4c5d6e7`). `typ` and
`parser_key` (points to the matching parser module in
`app/services/parsers/`, currently only `intersport`) drive automatic
supplier detection on document upload: the registry recognizes the layout
and the importer looks up the supplier via the same `parser_key`
(Phase B, subtask B1 — see `docs/architektur.md`, "PDF parsing"). A
supplier without a matching parser module (or vice versa) makes the
import fail, which is why `tests/test_parser.py` checks both sides
against each other. Seed data in `app/core/lieferanten.py`.

### `kategorien`
POS categories: main group (textile, hardware, footwear, bike, food) ×
sport area (rule 8) — bike and food have no sport area. 35 fixed
combinations, seed data in `app/core/kategorien.py`. A FEDAS→category
mapping: `app/core/fedas.py` (Phase B, see `projekt-kontext.md` for Phase
B details), currently only the codes confirmed from real invoices.
Anything missing there is chosen manually (`app/services/kategorien.py`,
subtask B8); the selection list comes via `GET /api/kategorien` in the
till's order.

### `artikel`
Model level, shared across branches (rule 4): brand + supplier item
number identify a model across all colors/sizes. If the supplier item
number is missing, every occurrence stays its own item (a real foreign
key relationship instead of the former runtime grouping in
`app/services/article_groups.py`, which now only queries
`varianten.artikel_id`). `fedas_code` is recorded during import if the
invoice provides it. `kategorie_id` is automatically suggested when a new
item is created, from the FEDAS code (`app/core/fedas.py` +
`app/services/importer.py`), if the combination is known — otherwise it
stays empty and is chosen manually (subtask B8, see below). A value that
has been set is never overwritten; one still empty is filled in
retroactively if a later invoice has a known code.

`kategorie_manuell` (migration `c9d0e1f2a3b4`) says where the category
came from: `false` = suggested from the FEDAS code, `true` = chosen
manually (item page or manual entry, `app/services/kategorien.py`). The
UI shows the difference — the FEDAS table is not yet fully confirmed.
Clearing it resets both: the item is open again, and a later document
with a known code may suggest again.

`lieferant_id` may be **empty** since migration `a7b8c9d0e1f2`: manually
entered goods don't need a supplier (D23) — one coming from a supplier
document always has one, though. Items without a supplier are merged
among themselves, but never mixed with a supplier's items (shared rules:
`app/services/artikel.py`).

### `varianten`
Color/size/EAN of an item (rule 5: EAN optional — the key without an EAN
is supplier + item number + color + size via `artikel_id`). Since
subtask B3 this also applies on upload: a line without an EAN goes
through with a note and ends up as a variant with an empty EAN. Several
such variants don't conflict, because NULL doesn't collide in the unique
index. `ean_intern` marks EANs generated by the system (EAN-13 in the
GS1 range 20–29, D10). Since subtask B7 this is set: if the
manufacturer's EAN is missing, `app/services/ean.py` generates an
internal number on demand following the pattern `20` + ten-digit variant
id + check digit. An existing EAN is never overwritten.
`first_seen`/`last_seen` as before on `products`, recalculated on every
import/deletion.

### `preise`
UVP (RRP)/EK (cost) history per variant (rule 10: EK optional, never
mandatory), with date and the referencing document. Replaces the former
implicit price history via `invoice_items.uvp` + `invoices.invoice_date`.

### `dokumente`
Generalizes the former `invoices` table to all document types from D6
(invoice, delivery note, order confirmation, purchase order). `typ` has
come from the document itself since subtask B1 (the recognized parser
module supplies it) instead of being fixed as `rechnung`; without a
recognized type, nothing is imported. `datei_hash` is globally unique
(the same file is the same document, no matter who uploads it), while
the document number is unique only **per supplier**:
`UNIQUE (lieferant_id, dokumentnummer)` since migration `e5f6a7b8c9d0`
(Phase B, subtask B2). Document numbers are a supplier matter and
overlap freely — previously, a new supplier's invoice would have counted
as a duplicate for no reason other than INTERSPORT already having used
that number. If `lieferant_id` is empty, uniqueness doesn't apply (NULL
counts as different from everything); however, the importer rejects a
document with no recognized supplier, so this case doesn't occur. The
understandable message ("Invoice … has already been imported") comes
from the importer; the constraint is the fallback for two simultaneous
imports. `lagerort_id` is the target branch: since subtask B4 it is the
storage location chosen at import, suggested from the document's
delivery address (`app/services/lieferadresse.py`, D19), otherwise the
active branch. A document has exactly one storage location (D20).
`ocr_verwendet` marks documents that were read via Tesseract OCR for
lack of a text layer.

### `wareneingaenge`
One goods receipt per document (currently 1:1; the schema allows several
per document later, e.g. for partial deliveries) — or **without** a
document: manually entered goods are a direct goods receipt without a
document (D27), `dokument_id` then stays empty (migration
`a7b8c9d0e1f2`, subtask B6). Such a goods receipt is immediately
`eingetroffen` (arrived). `status` distinguishes `erwartet` (expected —
only for order confirmations, no stock booking yet, rule 3) from
`eingetroffen` (arrived — goods are here, `lagerbewegungen`/`bestand`
are written). Invoices and delivery notes are immediately `eingetroffen`,
order confirmations and purchase orders start as `erwartet` (subtask
B5). `eingangsdatum` (receipt date) is set on first receipt —
retroactively if needed (D13), and not at all in a storage location
without sale (rule 6).

`eingangsdatum` follows rule 6: at a branch (`lagerorte.verkauf = true`)
it is the invoice date; at a location without sale it stays **empty**
and is only set on arrival at a branch — the markdown clock (18/36
months) should not already be running externally. This applies to all
three external locations: the processing sites GEWA and VEBO as well as
the DIETIKON warehouse. What always matters is `lagerorte.verkauf`,
never the individual code — this means a further external location is
picked up automatically. The same applies to
`bestand.aeltestes_eingangsdatum`.

### `wareneingang_positionen` (+ `wareneingang_positionen_quelle`)
One row per line of a goods receipt — generalizes the former
`invoice_items` table. `wareneingang_positionen_quelle` is the optional
1:1 original snapshot (raw text, page/line number, parser warnings,
`correction_audit`) as JSON, just like `invoice_item_sources` before —
also preserved if `varianten`/`artikel` change later. For manual entry
it holds the unchanged input along with the person who entered it and
the timestamp (`quelle: "manuelle-erfassung"`). `menge` is the quantity
per the document (expected), `menge_eingetroffen` the quantity actually
arrived; the difference is the open remaining quantity (D22, migration
`f6a7b8c9d0e1`). For invoices/delivery notes both are equal from the
start.

### `lagerbewegungen`
Append-only journal of every stock change (rule 2): `typ` is `zugang`
(receipt), `verkauf` (sale), `ausbuchung` (write-off), `korrektur`
(correction), or `umlagerung` (transfer). So far `zugang` is written;
since C3 also `verkauf` and `ausbuchung` (quantity −1 per scan, reason
in `grund`, e.g. `defekt` or `sonstiges: …`), plus `korrektur` as a
counter-booking when reversing (`grund = 'storno:<id>'`); since C4
`umlagerung` (two rows per variant: `−menge` at the source with
`grund = 'nach:<target>'`, `+menge` at the target with
`grund = 'von:<source>'`). Since C5 also general `korrektur` rows: the
difference to the counted quantity is booked, reason `inventur`
(stock-take), `falsch_gebucht` (booked wrong), `gefunden` (found), or
`sonstiges: …`.

`eingangsdatum` is set only on the target row of a transfer, which
starts the markdown clock there — external location → branch (D13), or
a branch that never had the item before (F11); otherwise empty. The
clock (`reduktion.letzter_wareneingang()`) takes the later date from
goods receipts and such transfers. Every imported invoice line creates
exactly one movement of type `zugang`; manually entered goods likewise,
with `grund = 'manuelle-erfassung'` there (a fixed key, not UI text —
translation only happens at display time). The user is stored as a
snapshot (as with `dokumente`/`article_notes`), not as a foreign key.

### `bestand`
Current stock per variant × branch (composite primary key), derived from
`lagerbewegungen` and also kept in sync there (never written directly
except to update the running total). `aeltestes_eingangsdatum` (oldest
receipt date) later serves the markdown logic (Phase D, 18/36 months
from the last goods receipt of the same supplier item number at that
branch). Stock has been read on the `/bestand` page since Phase C,
subtask C2 (`app/services/bestand.py`).

A **negative** stock is possible: when writing off manually, the system
warns but still books it (since C3) (confirmed 2026-09-22). The view
therefore never hides it.

**Known limitation after the migration:** since the old system never
recorded sales/write-offs, the migrated `bestand` corresponds to the
cumulative historical goods receipts, not the actual physical stock —
this is only corrected once manual write-offs (Phase C) or a stock-take
happen.

### `reduktionen_manuell`

Manually chosen markdown level per model (`artikel_id`) × branch
(`lagerort_id`), unique per pair, `prozent` only 30/50/70. Without a row,
the recommendation from rule 6 applies; with a row, it is the effective
level (even below the recommendation). User as a snapshot
(`benutzer_kassennummer`, `benutzer_name`), plus `gesetzt_am` (set on).
Deleted along with a manually entered item when that item is deleted.

### `reduktionen_bestaetigt`, `hinweise`, `reduktion_empfehlung_zentrale` (Phase D, 2026-09-25)

Three tables for the open questions D-F1/D-F2/D-F3, migration
`e2f3a4b5c6d7`:

- `reduktionen_bestaetigt` (D-F1): `artikel_id` × `lagerort_id` unique,
  `stufe` (the confirmed automatic level). If the currently calculated
  level deviates, the confirmation no longer applies.
- `hinweise` (D-F2): `lagerort_id`, `artikel_id`, `typ` (only
  `nachlieferung_reduziert`), `alte_stufe`, `erstellt_am` — created
  automatically when booking a delivery for a model that was already
  marked down before (no batch separation in stock, hence only a hint
  instead of a real split).
- `reduktion_empfehlung_zentrale` (D-F3): `artikel_id`, `lagerort_id`,
  `prozent`, `ab_datum`, `status` (`offen`/`uebernommen`/`abgelehnt`),
  `ablehnungsgrund`, head-office and response snapshot. At most one open
  row per model × branch — a new recommendation replaces an older one.

### `article_notes`
As before, now keyed on `artikel_id` instead of `product_id` — a note
applies to the whole model (all colors/sizes), no longer just the
variant shown when it was created. Optimistic locking via `version`
unchanged.

### `lagerorte`
Seven entries: the four branches SF1 Volketswil, SF2 Conthey, SF3
Regensdorf, and SF4 Hägendorf (`verkauf = true`), and three external
locations without sale — the processing sites `GEWA` and `VEBO`, and the
`DIETIKON` warehouse. The schema deliberately does **not** distinguish
between processing site and warehouse: only `verkauf` matters for every
rule. Seed data in `app/core/lagerorte.py` (single source, used by
migrations and tests).

### `users`, `benutzer_lagerorte`
Unchanged since Phase A, items 1/2, except for the login lockout
(security S2, migration `b9c0d1e2f3a4`): `users.fehlversuche` counts
wrong passwords, `users.gesperrt_bis` (UTC) locks the account for 20
minutes after 5 failed attempts (`app/services/anmeldung.py`). Plus
`users.schnellzugriffe` (point 14, migration `d1e2f3a4b5c6`): JSON list
of the chosen function keys in their order, `NULL` without an own
choice. Catalog and role filtering live in `app/core/schnellzugriffe.py`,
not in the database — the API re-validates on every save.

Account management (2026-09-25) deletes a `users` row together with its
`benutzer_lagerorte`; bookings keep name/till number as a snapshot, so
no foreign key blocks the deletion. The phone flag (2026-09-28) lives
only in the session cookie, not in the database.

## Migrating the legacy data (`c3d4e5f6a7b8`)

Runs automatically on `alembic upgrade head` (not in offline `--sql`
mode, see below) and is lossless except for `products.article_no` (see
above):

1. **Suppliers/categories**: seed data as above.
2. **`products` → `artikel` + `varianten`**: same grouping as the former
   `article_groups.py` — same brand (trimmed, case-insensitive) + same
   non-empty supplier item number (trimmed) = one item; if the number is
   missing, every product stays its own item.
3. **`invoices` → `dokumente` + `wareneingaenge`**: `typ = 'rechnung'`,
   `status` always `'eingetroffen'` (the old system only knew goods that
   had arrived), storage location SF1 (legacy-data rule from CLAUDE.md).
4. **`invoice_items` + `invoice_item_sources` → `wareneingang_positionen`
   (+ `_quelle`) + `preise` (if a UVP is present) + `lagerbewegungen`**
   (type `zugang`, if a quantity is present).
5. **`bestand`**: aggregated from the newly created `lagerbewegungen`.
6. **`article_notes.product_id` → `artikel_id`**: via the mapping built
   in step 2.

## Migration history

| Revision | Description |
|---|---|
| `5ce94c6a96e3` | Baseline: `products`, `invoices`, `invoice_items`, `invoice_item_sources` |
| `7129c5082ac9` | `users` table including both check constraints |
| `246c67c1d45e` | `imported_by_kassennummer`/`imported_by_name` on `invoices` |
| `d567ef887517` | `ocr_used` (boolean, default `false`) on `invoices` |
| `e901abc23456` | New table `article_notes` including author snapshot and version field |
| `a1b2c3d4e5f6` | New tables `lagerorte` (SF1–SF4 + GEWA, seed data) and `benutzer_lagerorte` (m:n); `users.role` extended with `admin`; existing users assigned to SF1 |
| `b2c3d4e5f6a7` | `users.language` (DE/FR/EN, default `de`) including check constraint |
| `c3d4e5f6a7b8` | New data model (Phase A, item 3): `lieferanten`, `kategorien`, `artikel`, `varianten`, `preise`, `dokumente`, `wareneingaenge`, `wareneingang_positionen` (+`_quelle`), `lagerbewegungen`, `bestand`; full data migration of legacy data; `article_notes.product_id` → `artikel_id` |
| `d4e5f6a7b8c9` | Fix: set id sequences of the new tables to `MAX(id)`. The first version of `c3d4e5f6a7b8` only did this when legacy data existed — on a fresh database, the first insert without an explicit id then failed. Idempotent, PostgreSQL only, a no-op on a correct database |
| `e5f6a7b8c9d0` | Document number unique only per supplier (subtask B2): `UNIQUE (lieferant_id, dokumentnummer)` instead of a globally unique `dokumentnummer` |
| `f6a7b8c9d0e1` | `wareneingang_positionen.menge_eingetroffen` (subtask B5) including backfill of legacy data — the difference to `menge` is the open remaining quantity (D22) |
| `a7b8c9d0e1f2` | Manual entry (subtask B6): `wareneingaenge.dokument_id` and `artikel.lieferant_id` may stay empty (goods receipt without a document, D27; item without a supplier, D23) |
| `b8c9d0e1f2a3` | Two further storage locations without sale: `VEBO` (processing site like GEWA) and `DIETIKON` (external warehouse); GEWA renamed to "GEWA (external processing)". Idempotent; the downgrade only removes one of the two as long as nothing depends on it |
| `c9d0e1f2a3b4` | `artikel.kategorie_manuell` (subtask B8): tracks whether the category was chosen manually; server default `false`, because existing items got their category solely via the FEDAS suggestion |
| `d0e1f2a3b4c5` | Branch codes corrected (2026-09-22): SF2 is Conthey, SF3 Regensdorf, SF4 Hägendorf. Only the `code` of the existing row is swapped — the location stays where it is, and bookings hang off `lagerorte.id`. Swapped in a ring via intermediate codes, because `code` is unique |
| `e1f2a3b4c5d6` | `lagerbewegungen.eingangsdatum` (subtask C4): date from which a transfer starts the markdown clock of the target branch. Existing rows are receipts whose date is on the goods receipt — there the column stays empty |
| `f2a3b4c5d6e7` | Supplier groups (requirement 2026-09-23, implemented 2026-09-24): `lieferanten.typ` newly knows `intern` (direct orders from Nike, adidas, The North Face); one supplier per group for manual entry. The label code (111/555/333/999/444) is derived from `typ` (`app/core/lieferanten.py`), not stored |
| `a8b9c0d1e2f3` | Suppliers with their own parser (2026-09-24): ALPINA SPORTS Schweiz AG, CHRIS sports AG, CMP (F.lli Campagnolo S.p.A.) with `parser_key`, group third-party dealer (999). Data only |
| `b9c0d1e2f3a4` | Login lockout (security S2, 2026-09-24): `users.fehlversuche`, `users.gesperrt_bis` |
| `c0d1e2f3a4b5` | Manual markdown (2026-09-24): new table `reduktionen_manuell` |
| `d1e2f3a4b5c6` | Quick access (requirement 14, 2026-09-25): `users.schnellzugriffe` (JSON, chosen functions and order) |
| `e2f3a4b5c6d7` | Phase D, open questions (2026-09-25): new tables `reduktionen_bestaetigt`, `hinweise`, `reduktion_empfehlung_zentrale` |

Schema changes run exclusively through Alembic
(`alembic revision --autogenerate`); the container automatically runs
`alembic upgrade head` on startup (see `SERVER-SETUP.md`).
