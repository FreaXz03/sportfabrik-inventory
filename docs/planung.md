# Requirements & Planning (reconstructed retroactively)

This document describes the mandate, requirements, development phases, and
key decisions of the Sport-Fabrik Inventory System. It was created
**retroactively**: a large part of the app already existed before a Git
repository or a formal requirements list was set up. The following
requirements are therefore reconstructed from the original, informal
mandate and from the solution actually built — not from a requirements
document that existed beforehand.

## Starting point

Original mandate (paraphrased, as formulated at the outset):

> An inventory system for the Sport-Fabrik (clothing store). A page where
> you can upload and manage invoices, extract all the items in them, and
> save them to a PostgreSQL database. The whole thing should then run on a
> Linux server at the store, with four PCs having access to it.

The store carries ski, bike, hiking, running, and tennis equipment;
deliveries currently come primarily from INTERSPORT Schweiz AG via PDF
invoice.

## Functional requirements (reconstructed)

| # | Requirement | Implemented in |
|---|---|---|
| F1 | Upload PDF invoices and automatically read out line items | `app/services/parsers/` (registry + one module per supplier layout) |
| F2 | Preview of the recognized line items before saving; nothing is accepted unchecked | `app/routers/preview.py` (`/upload-preview`) |
| F3 | Import only after explicit confirmation, and only exactly the checked file | `app/routers/preview.py` (`/import-invoice`), hash comparison |
| F4 | Central item database; items delivered multiple times (same EAN) merged instead of duplicated | `app/services/importer.py`, `Artikel`/`Variante` models (until Phase A point 3: `Product` model, see `datenmodell.md`) |
| F5 | Item search by brand, EAN, supplier item number, description, color, size, delivery-date range | `app/routers/catalog.py` |
| F6 | Full delivery history per item (variant group) and per invoice, including the original invoice text | `app/routers/history.py`, `WareneingangPositionQuelle` (until Phase A point 3: `InvoiceItemSource`), `app/services/article_groups.py` |
| F7 | Ability to fully delete an invoice after the fact, with correct recalculation of affected item data | `delete_invoice()` in `app/services/importer.py` |
| F8 | Simultaneous access from four store PCs, without inconsistent data on concurrent import | Advisory lock (`pg_advisory_xact_lock`) |
| F9 | Login modeled on the existing POS system: employees with cash-register number only, branch managers additionally with a password | `app/routers/auth.py` |
| F10 | Only branch managers may upload, import, and delete invoices; employees may only view/search | RBAC dependencies (`require_chef_*` / `require_login_*`) |
| F11 | Traceability of which person (cash-register number/name) imported an invoice | `hochgeladen_von_kassennummer`/`hochgeladen_von_name` on `Dokument` (until Phase A point 3: `imported_by_*` on `Invoice`) |
| F12 | Operation on a Linux server at the store, access over the local network | Docker/Compose, `SERVER-SETUP.md` |
| F13 | Make scanned paper invoices without a digital text layer (exceptional case: invoice only on paper in the package, no email PDF) readable via OCR | `app/services/ocr.py`, `parser.page_content()` |
| F14 | Ability to correct recognized line items directly in the preview instead of rejecting the whole invoice | `app/services/corrections.py`, `/validate-preview` |
| F15 | Upload and import several invoices in sequence, without restarting after each file | `app/static/js/preview.js` (queue), `/invoice-import-status` |
| F16 | Store free-text notes per item (group) (e.g. sales observations), with author and change history | `ArticleNote` model, `app/routers/article_details.py` |
| F17 | View price history (RRP over time) per item (group) | `/api/articles/{id}/prices` |
| F18 | Show color/size variants of the same item together rather than individually in history/notes/price history | `app/services/article_groups.py` |
| F19 | Export a filtered item list as an Excel file (e.g. for order lists) | `app/services/article_export.py`, `/api/articles/export` |
| F20 | Ability to sort invoice- and item-history tables by any column | `sort_by`/`sort_dir` in `app/routers/history.py` and `app/routers/catalog.py` |
| F21 | Simplify the interface for staff with limited vision (show/hide columns, larger font) and offer a site-wide light/dark mode | `app/static/js/theme.js`, column selection in `articles.html` |
| F22 | Regular, verified backups of the database and original PDFs | `scripts/backup_inventory.py`, `docs/BACKUPS.md` |

F9–F11 and F13 were added only later, during the first project-analysis
session; F1–F8 and F12 had already been implemented at that point. F14–F22
were added afterward, in a second, extensive expansion stage (see
development phases).

## Non-functional requirements (reconstructed)

- **Language/target audience**: consistently German interface and error messages; the target audience is store staff without an IT background, including staff with limited vision (see F21).
- **Robustness over convenience**: when something is unclear (unknown layout, missing required fields, ambiguous color/size), the line is flagged with a warning instead of being guessed — corrections are possible (F14), but always explicit and re-validated server-side.
- **No silent data corruption**: hash check between preview and import, transactions with rollback on error, advisory lock against race conditions, optimistic locking on notes (version conflict instead of silent overwrite).
- **Independent of the internet**: no frontend framework, no build pipeline, no external script dependencies in the browser — must work on the store network without internet access.
- **Traceability**: the line-item-level audit trail (`WareneingangPositionQuelle`, including `correction_audit`) is preserved even if item master data changes later.
- **Extensibility**: the architecture should be able to accommodate further supplier layouts and endpoints without becoming unwieldy (see folder structure in `docs/architektur.md`).

## Deliberately out of scope (as of today)

- ~~Further supplier layouts besides INTERSPORT~~ — superseded: Alpina, Chris Sports, and CMP parsers exist since 2026-09-24 (Phase E, partly).
- ~~Admin interface for user management~~ — superseded: head office manages accounts on `/konten` since 2026-09-25; the CLI script (decision E10) still exists.
- External backup storage location (the backup automation itself is implemented, see F22 and `docs/BACKUPS.md`; a copy outside the PC is still pending, now with encryption, security S4).

**Superseded since Phase A point 3** (see `projekt-kontext.md` section 11):
stock is now tracked for real (`lagerbewegungen`/`bestand`, see
`datenmodell.md`) — though with the limitation documented there that the
stock migrated from the legacy data only reflects the cumulative historical
goods receipts, not the actual physical stock (missing sales/write-off
history in the old system). An exact, current stock figure only arrives
with Phase C.

## Development phases (timeline)

| Phase | Date | Content |
|---|---|---|
| 0 | before the first project analysis (exact date not documented, since no Git repository existed yet) | Core development by Fabian: FastAPI backend, PostgreSQL data model, PDF parser for the INTERSPORT layout, two-stage upload/import workflow, searchable item catalog with delivery history, Docker/server preparation, test suite (29 tests) |
| 1 | 2026-09-06, 12:33 | Project analysis; Git repository set up, first commit, public GitHub repo (`github.com/FreaXz03/sportfabrik-inventory`), SSH access set up |
| 2 | 2026-09-06, 12:57 | Introduced Alembic database migrations (instead of `Base.metadata.create_all()`); removed the development endpoint `/upload-test`; cleaned up unused, empty `navigation.js` |
| 3 | 2026-09-06, 13:28 | Implemented login and role-based access rights (POS-system pattern); user management via CLI script (`scripts/manage_users.py`) |
| 4 | 2026-09-06, 13:59 | UI fixes: fixed a broken "Reset" button (ID name collision with `HTMLFormElement.reset`), hid the upload hint for employees, added traceability (who imported an invoice) |
| 5 | 2026-09-06, 14:13 | Cleaned up folder structure (`app/` organized into `core/`, `routers/`, `services/`; `static/` sorted by file type); added `README.md` |
| 6 | 2026-09-06, 15:20 | First complete documentation set (`planung.md`, `architektur.md`, `datenmodell.md`, `api-referenz.md`, plus a summarized Word document) |
| 7 | 2026-09-06, 16:15 | OCR fallback for scanned paper invoices without a text layer (`app/services/ocr.py`), including test coverage (`tests/test_ocr.py`) and a migration for `Invoice.ocr_used`; afterward two real parsing bugs were fixed based on a real scanned sample invoice |
| 8 | 2026-09-06, 17:30–19:56 | UI polish over several rounds: sortable item search, wider layout, page size 100, column selection + larger font for staff with limited vision (F21), renamed "Chef" in the interface to "Filialleiter" (branch manager), fixed the login page, site-wide dark mode with a settings menu; afterward the login redirect was secured against open redirects, `migrations/env.py` was made more robust against special characters in the password, automated, verified backups were set up (F22, `scripts/backup_inventory.py`, `docs/BACKUPS.md`) |
| 9 | after that | Larger functional extension: corrections directly in the preview (F14), batch import of several invoices (F15), price history and free-text notes per item (F16/F17), Excel export of the item list (F19) |
| 10 | after that | Item variants (same brand + supplier item number) grouped for history/notes/price history (F18), column selection in the item history simplified |
| 11 | after that | Further polish to the overview, invoice/item history (sorting, F20), and the batch-import flow |
| 12 | 2026-09-20 – 2026-09-21 | Target picture and decisions D1–D27 for inventory management v2 (`projekt-kontext.md`) |
| 13 | 2026-09-21 – 2026-09-25 | Phases A–D implemented: branches, roles, languages, new data model, goods receipt v2, stock, markdowns; item-details catalog (17 points), statistics, accounts, quick access (PRs #9–#15) |
| 14 | 2026-09-27 – 2026-09-28 | UI redesign after `DESIGN.md` (PRs #16/#17), documentation in English, HTTPS (S1), phone use |

From phase 12 on, `projekt-kontext.md` (section 11 and the dated addenda)
is the authoritative history; this table only gives the big picture.

Phases 9–11 were largely developed in parallel, independent of the UI-polish
sessions (Phase 8); the exact timestamps of these commits are not available,
the order results from the commit history (`df99ebc`, `b15774d`, `94e5085`).

## Key decisions (with rationale)

**E1 — Cash-register-number login instead of a classic user account for everyone.**
Employees log in with only their cash-register number (no password),
branch managers additionally with a password. Rationale: matches the
existing POS system in the store, lowers the barrier for employees in
day-to-day use, while sensitive actions (upload, delete) are additionally
secured.

**E2 — Two-stage upload/import instead of saving directly.**
`/upload-preview` writes nothing to the database; only `/import-invoice`
with a confirmed hash saves it. Rationale: the parser cannot always safely
resolve edge cases automatically (missing EAN, ambiguous color/size,
unknown layout) — errors should be caught before saving, not laboriously
corrected afterward.

**E3 — Hash comparison between preview and import.**
`/import-invoice` requires the SHA-256 hash of the previously checked file.
Rationale: prevents a different file from being imported between the check
and the confirmation than the one actually reviewed.

**E4 — `pg_advisory_xact_lock` instead of fine-grained row locking.**
Import and deletion are serialized via a PostgreSQL advisory lock.
Rationale: a simple, robust solution for multi-station operation (four
PCs), without having to design a complex locking scheme.

**E5 — Denormalized audit fields instead of pure foreign-key linking.**
`WareneingangPositionQuelle` (until Phase A point 3: `InvoiceItemSource`)
permanently stores the original line-item data; `Dokument.hochgeladen_von_
kassennummer`/`hochgeladen_von_name` (until Phase A point 3:
`Invoice.imported_by_*`), `Lagerbewegung.benutzer_kassennummer`/
`benutzer_name`, and `ArticleNote.author_name`/`author_number` store a
snapshot rather than (only) a foreign key. Rationale: historical
correctness is preserved even if item master data changes later or a user
account is deleted.

**E6 — Alembic migrations instead of continuing with `create_all()`.**
Rationale: schema changes must be traceable, versioned, and reproducible on
all four PCs — plain `create_all()` doesn't provide that.

**E7 — Session cookie without automatic expiry.**
Rationale: matches the behavior of the existing POS system; nobody needs to
keep logging back in during day-to-day store operation.

**E8 — No frontend framework, no build pipeline.**
Rationale: must run on simple store PCs without internet access; a build
step would be additional, unnecessary complexity for an internal tool of
this size.

**E9 — Folder structure `core/` / `routers/` / `services/` instead of a flat list.**
Rationale: preparation for growth (e.g. further supplier parsers, further
endpoints), clear responsibilities instead of many equally-ranked files at
one level.

**E10 — Simple CLI script instead of an admin interface for user management.**
Rationale: user accounts change rarely (new employees, new branch
managers); a dedicated web interface for this would be disproportionate to
the benefit for four PCs and a handful of accounts.

**E11 — OCR fallback instead of a dedicated image parser for scanned invoices.**
If a PDF page has no text layer at all (paper invoice scanned instead of
received digitally by email), `app/services/ocr.py` renders the page and
reads it via Tesseract OCR; the recognized words are prepared exactly like
PyMuPDF word coordinates, so that the layout detection and table detection
of the parser modules can continue to be used unchanged.
Rationale: a separate, parallel image-parsing logic would have had to
rebuild the same column detection a second time, error-prone. OCR is
inherently less reliable than a native text layer; line items and invoices
from OCR are therefore explicitly flagged (`ocr_used`) and given a note in
the preview to check them especially carefully — but the import remains
possible as long as there are no genuine data problems (OCR use alone does
not block the import).

**E12 — Re-validate corrections server-side instead of trusting client values.**
`apply_corrections()` never accepts unchecked whatever the browser sends:
every corrected line item goes through the same validation as a freshly
parsed one. Rationale: an incorrectly corrected line item (e.g. an invalid
EAN) must not accidentally lead to worse data quality than an uncorrected
warning.

**E13 — Group item variants by brand + supplier item number
(originally via a runtime query, since Phase A point 3 as a real
foreign-key relationship).**
Originally, `app/services/article_groups.py` recalculated the association
of color/size variants on every query (brand + supplier item number),
instead of maintaining a fixed group foreign-key relationship in the
database — rationale at the time: an additional table would have had to be
kept in sync on every correction of these fields and could become stale.
With the new data model (Phase A point 3, see `datenmodell.md`) this table
now exists (`artikel`, referenced by `varianten.artikel_id`) — the
grouping **rule** stays identical (same brand + same, non-empty supplier
item number), but is now applied only once, at import time
(`app/services/importer.py`), instead of being recalculated on every query;
`article_groups.py` has since only read the relationship.

**E14 — Optimistic locking (version field) instead of locking for notes.**
Rationale: notes are rarely edited by two people at the same time; a
version conflict (HTTP 409) with a prompt to reload is simpler and robust
enough for this usage pattern, without having to manage a persistent lock.

**E15 — Batch import as a pure frontend queue instead of a server batch endpoint.**
Rationale: nothing changes about the import on the server side (each file
remains atomic and checked on its own); a server-side batch API would have
had to map the same logic a second time, without real added value over
several individual imports that the browser triggers automatically one
after another.

**E16 — Login redirect target against a fixed whitelist instead of arbitrary URLs.**
Rationale: `next` comes from the URL and is therefore potentially
manipulable; a whitelist of known, safe target routes reliably rules out
open redirects, without limiting the convenience feature (returning to the
originally requested page after login).

## Open points

Current list: `projekt-kontext.md`, section "Status check and next steps – 2026-09-28". Still valid from the original list:

- External backup storage location outside the PC — backup creation and verification themselves are already automated (see `docs/BACKUPS.md`).
- ~~A second supplier layout~~ — done (Alpina, Chris Sports, CMP).
- New, long password for `.env.server` (do not reuse the local Windows password).
- Docker build and data migration to the Linux server at the store (a local test run via `docker compose --env-file .env.server up -d --build` is already possible; the production migration is still pending).
