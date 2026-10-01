# Sport-Fabrik Inventory

Project work: [Short intro and current priority](docs/start.md) · [Targeted knowledge search](docs/obsidian-graphify.md).

Internal inventory management for Sport-Fabrik: upload supplier documents
(PDF), read out line items with our own parsers, correct them in the
preview, and book them into a PostgreSQL database. Stock is tracked per
branch as an append-only movement journal; markdowns (30/50/70 %) follow
the time in stock; staff can also work on their phones. Items can be
searched, their delivery and price history reviewed, and the item list
exported as an Excel file.

Runs on a central server (Volketswil); the 4 branches (SF1 Volketswil,
SF2 Conthey, SF3 Regensdorf, SF4 Hägendorf) as well as the external
locations without sale — the processing sites GEWA and VEBO and the
Dietikon warehouse — access it over the internal network via the browser.
Login follows the POS-system pattern: employees with just a cash-register
number, branch managers and admin/head office additionally with a
password. Employees may manually book in and correct stock and book out
sales (only sales), all only in their assigned branches. Booking out any
other reason, cancelling, and transferring are reserved for branch
managers and head office. Their
existing cross-branch booking rights remain in place; read rights are
unchanged. Uploading/editing/deleting documents remains reserved for
branch managers and head office. Admin/head-office accounts are
cross-branch; all other users are assigned to one or more branches and can
switch between their branches in the interface.

## Feature overview

- **Upload invoices** (also several at once as a batch), automatically
  recognize line items, review them in the preview and correct individual
  fields if needed — import only happens after explicit confirmation.
- **The system recognizes the supplier and document type itself** based on
  features in the document (one parser module per supplier layout, see
  `app/services/parsers/`); a still-unknown layout is reported as such,
  instead of aborting with a misleading error message.
- **The system recognizes the target branch from the delivery address** on
  the document and suggests it on import (changeable) — deliveries to a
  different branch or to the external GEWA warehouse also end up in the
  right place this way.
- **Expected deliveries**: order confirmations and purchase orders only
  announce goods — stock is only created once someone confirms arrival. If
  less arrives than expected, the remaining quantity stays visibly open.
- **Overview** as the home page: up to five quick-access shortcuts chosen
  per user (order by drag-and-drop or arrows), branch metrics, what's
  coming up in the active branch (deliveries and incoming transfers,
  stock to count, items at markdown age, items without EAN or category,
  notices about new deliveries of marked-down items), and recent activity
  summarized (a delivery as a whole, a transfer as one entry, removals
  other than sales).
- **Stock per branch** (the "Stock" page): current stock per variant and
  storage location with color, size, and main group, search, branch
  filter, oldest receipt date, and the effective markdown level; item
  names link to the item details; rows with quantity 0 don't appear.
  Every login may read all branches; goods at an external location are
  recognizable as such because they don't yet have a receipt date.
- **Scan to write off** (the "Write off" page): every scan immediately
  books out one unit — sale, breakage/defect, theft/shrinkage, own use,
  return, or other. If stock isn't sufficient, the page warns but still
  books it; a mis-scan can be undone with a counter-booking. Items can
  also be picked from a stock list. Below that, the list of all
  write-offs with time, person, and reason. Employees book sales only;
  other reasons and undo are for branch managers and head office.
- **Transfer** (the "Transfer" page, like a delivery since 2026-09-28):
  the source sends goods with a dispatch date — by scan or from its stock;
  the removal is booked at once. The destination confirms the arrival
  under "Deliveries" after unpacking, only then the goods are in its
  stock. Goods from GEWA, VEBO, or Dietikon get their receipt date on
  arrival; between branches, the date is kept.
- **Correct stock** ("Count" button in the stock view): enter the counted
  quantity, the system books the difference with a reason.
- **Manually record goods** (the "Record" page): scan or type in, without a
  document and without a parser — for goods without a document and for
  suppliers whose layout isn't recognized yet. Only brand, description,
  quantity, and RRP are required; the POS category can optionally be added.
  Everything is booked at once as a single goods receipt.
- **Items without a barcode** aren't a special case: a line item without an
  EAN goes through with a note (the key is then supplier + item number +
  color + size); an unreadable EAN, on the other hand, still blocks the
  import.
- **Internal EAN at the push of a button**: items without a manufacturer
  barcode get an in-house EAN-13 (GS1 range 20–29, with check digit) and
  thereby become scannable at the till.
- **Markdowns** (Phase D): every item in a branch starts at −30% on
  arrival (−50% after 18 months, −70% after 36 months). A page lists the
  items of a branch that have reached −50% or −70% or will reach it
  within 30 days, each with "Print
  labels" (one label per unit, with a roll hint) and "Done" (the model
  disappears until the next level). Any staff member — branch managers
  too — can set 30/50/70 % by hand only in their own branches (head office
  everywhere; by EAN or from the stock list); head office can
  send markdown recommendations per branch, which the branch accepts or
  declines with a reason.
- **Price label as PDF** for the pre-printed rolls (47 × 83 mm, portrait;
  logo, percent dot, and mountains are pre-printed): the RRP (struck
  through), the supplier's group code (111/555/333/999/444), the model
  year, and the EAN barcode are printed — individually or for a whole
  goods receipt. The interface says which roll to load (30% yellow, 50%
  red, 70% green); "View sample" shows the label with a suggested
  pre-print.
- **OCR fallback** for the rare cases where an invoice is only available as
  a scanned paper document instead of a digital PDF.
- **Item search**: up front, only "Scan EAN" (immediately active) and quick
  search, with further filters (brand, supplier item number, description,
  category, delivery date, manually recorded only) collapsed; sortable
  columns, column selection, and Excel export.
- **Delete incorrectly recorded items**: branch managers and head office
  can remove a manually recorded item without a document, along with its
  stock and bookings.
- **Item details**: RRP history at the top, delivery history, current
  stock of all sizes and colors across locations, markdown per branch; POS
  category and EAN/label behind small buttons; "delete item" at the
  bottom. (Free-text notes were removed from the interface on 2026-09-24;
  data and API remain.)
- **Invoice list** with a detail view, irrevocable deletion (including
  correct recalculation of item metrics) by branch managers.
- **Statistics** (branch managers and head office): pieces sold per POS
  category, estimated revenue (marked as an estimate), an order
  recommendation, and removals other than sales per reason with the
  person who booked them; opens on "this week".
- **Account management** (head office): create and delete employee and
  branch-manager accounts in the browser; past bookings keep the name.
- **Phone use** (`/m`, 2026-09-28): installable web app for phones —
  search, camera scan, count/correct, confirm deliveries, transfer, write
  off, enter goods, markdowns. A phone login only reaches these features
  (server-side allowlist); roles and branch limits apply unchanged.
- **Design system** (`DESIGN.md`): one token set for all pages,
  site-wide light/dark mode, larger font, and column selection for staff
  with limited vision.
- **HTTPS only** (security S1): a local Caddy proxy with an internal
  certificate; the session cookie is `Secure`.
- **Multilingual DE/FR/EN**: interface and error messages fully translated
  (German is the default), language can be switched per user at any time.
- **Role-based login** following the POS-system pattern, automated,
  verified backups (database + original PDFs).
- **Stock per branch**: every imported invoice line item books a goods
  receipt against the active branch of the uploading account, as a
  movement in the append-only journal `lagerbewegungen` (see
  `docs/datenmodell.md`) — goods receipts are never overwritten directly.
- **FEDAS category suggestion**: if the supplier provides a matching FEDAS
  product group, the POS category is automatically suggested on import
  (all 54 FEDAS categories mapped to the till's 11 sport areas, plus bike
  and food; see `app/core/fedas.py`).
- **Manually choose a category** when the FEDAS code is missing or doesn't
  yield anything (e.g. kids) — on the item page or right when recording.
  The interface indicates whether the category was suggested or chosen
  manually; a manual choice is never overwritten by a later import. The
  "No category" filter in the item search shows where something is still
  missing.

## Tech stack

- **Backend**: FastAPI + SQLAlchemy 2.0, Python 3.10+
- **Database**: PostgreSQL, schema management via Alembic migrations
- **PDF parsing**: PyMuPDF (word-coordinate-based table detection), one
  module per supplier layout with automatic detection
  (`app/services/parsers/`)
- **OCR**: Tesseract (via `pytesseract`) as a fallback for scanned paper
  invoices without a text layer
- **Excel export**: openpyxl
- **Frontend**: vanilla HTML/CSS/JS, no framework, no build pipeline; a
  single stylesheet (`app/static/css/app.css`) with design tokens for
  light and dark mode, a locally bundled font, no external CDNs
- **i18n**: its own lightweight catalog (JSON files + `translate()`/
  `i18n.js`, see `docs/architektur.md` section "Multilingual"), no
  additional dependency
- **Tests**: pytest (167 passed, 12 skipped without optional extra
  prerequisites such as Node.js or a real sample invoice — as of
  2026-09-28)
- **Deployment**: Docker / docker compose (see
  [`docs/SERVER-SETUP.md`](docs/SERVER-SETUP.md))

## Documentation

This README is the quick start. More detailed documentation lives in
[`docs/`](docs/):

- [`docs/start.md`](docs/start.md) — short orientation, current status,
  and next steps (**start here**)
- [`docs/projekt-kontext.md`](docs/projekt-kontext.md) — target picture,
  business decisions D1–D27, roadmap, open questions, implementation
  history
- [`DESIGN.md`](DESIGN.md) — design system: tokens, typography,
  components, accessibility
- [`docs/handynutzung.md`](docs/handynutzung.md) — phone use: plan and
  implementation status
- `docs/anforderungen-*.md` — dated requirement records from Fabian's
  inbox, each with implementation status
- [`docs/overviews/`](docs/overviews/) — two visual HTML overviews
  (inventory management, goods flow), mirrored from the vault
- [`docs/planung.md`](docs/planung.md) — requirements, development phases,
  and key decisions (reconstructed retroactively)
- [`docs/architektur.md`](docs/architektur.md) — layer model, security
  model, flow diagrams for upload/correction/import/delete
- [`docs/datenmodell.md`](docs/datenmodell.md) — tables, ER diagram,
  migration history
- [`docs/api-referenz.md`](docs/api-referenz.md) — all endpoints with
  permissions
- [`docs/SERVER-SETUP.md`](docs/SERVER-SETUP.md) — Docker build, server
  setup, data migration, operations
- [`docs/BACKUPS.md`](docs/BACKUPS.md) — automated, verified backups
- [`docs/sicherheit.md`](docs/sicherheit.md) — security review from
  2026-09-24 with open measures (HTTPS, login rate limiting, backups …)
- [`docs/obsidian-graphify.md`](docs/obsidian-graphify.md) — generating the
  code's knowledge graph with Graphify and opening it in Obsidian; why
  `graphify-out/` doesn't belong in the repo
- [`docs/claude-cloud-setup.md`](docs/claude-cloud-setup.md) — setting up
  Claude Code cloud sessions: plugins via the environment's setup script,
  project dependencies via a SessionStart hook
- [`docs/Sportfabrik-Inventory-Uebersicht-Geschaeftsleitung.docx`](docs/Sportfabrik-Inventory-Uebersicht-Geschaeftsleitung.docx) —
  a short, non-technical summary for management (not a replacement for the
  technical documents above)
- `docs/Sportfabrik-Inventory-Dokumentation.docx` — the same content as
  above as one combined Word document; deliberately **not** in the repo
  (see `.gitignore`), since it's regenerated from the Markdown documents
  above on every major change instead of being maintained manually

## Folder structure

```
app/
  main.py            Entry point: FastAPI app, middleware, router registration
  core/              Database connection, models, password hashing
    database.py
    models.py          SQLAlchemy models of the new data model (see docs/datenmodell.md)
    security.py
    lagerorte.py       Seed data SF1-SF4 + GEWA/VEBO/DIETIKON (see app/services/lagerorte.py for read access)
    lieferanten.py     Seed data suppliers (INTERSPORT + one per supplier group) and label codes 111/555/333/999/444
    kategorien.py      Seed data POS categories (main group x sport area, 35 combinations)
    fedas.py           FEDAS code -> POS category suggestion (Phase B, see docs/projekt-kontext.md)
                       -> manual choice is in app/services/kategorien.py
    i18n.py            translate()/normalize_language(): reads the catalog from app/static/i18n/*.json
    handy.py           Phone detection and the allowlist of routes a phone may use
    schnellzugriffe.py Catalog of quick-access functions and role filtering
  routers/           HTTP endpoints (pages + JSON API), grouped by topic
    auth.py            Login/logout, RBAC dependencies, branch switching, language choice (/api/me, /api/active-lagerort, /api/language)
    catalog.py         Item search, Excel export
    dashboard.py       Overview page
    history.py         Invoice list, details, item history, deletion
    article_details.py Notes and price history per item
    preview.py         Upload preview, correction validation, import confirmation
    wareneingang.py    View expected deliveries and confirm their arrival
    erfassung.py       Manually record goods (scanner lookup via EAN, booking without a document)
    etiketten.py       Add/generate an EAN and print labels as PDF
    kategorien.py      View POS category and choose manually (/api/kategorien)
    bestand.py         View stock per branch (/bestand, /api/bestand)
    ausbuchung.py      Write off by scan, one unit per scan, undo (/ausbuchen, /api/ausbuchen)
    umlagerung.py      Transfer goods on receipt (/umlagern, /api/umlagerung)
    korrektur.py       Book a counted quantity (/api/korrektur)
    reduktion.py       Markdowns page, due list, confirmation, manual level (/runterschreiben, /api/reduktionen)
    empfehlung.py      Head-office markdown recommendations (/empfehlungen)
    statistik.py       Statistics (/statistiken, /api/statistik)
    konten.py          Account management by head office (/konten, /api/konten)
    handy.py           Phone pages under /m (access rules: core/handy.py)
  services/          Business logic without HTTP dependency, reusable
    importer.py        Transactional import/deletion of invoices (books goods receipt + stock against the active branch)
    parsers/           One module per supplier layout + registry (see docs/architektur.md)
      __init__.py        Registry: detect layout/supplier (parse_document, UnknownLayoutError)
      base.py            Shared building blocks: read a PDF once (incl. OCR), lines/numbers
      intersport.py      INTERSPORT invoices (also ECOM returns, code 555) incl. FEDAS code and purchase price
      alpina.py          ALPINA order confirmations (item = model, color/size as variant)
      chrissports.py     CHRIS-sports order confirmations (price = RRP, D12; purchase price = amount/quantity)
      cmp.py             CMP order confirmations (size grid, block sums cross-checked)
    ocr.py              OCR fallback (Tesseract) for scanned pages without a text layer
    corrections.py      Validate manual corrections in the preview
    article_groups.py  Group color/size variants of the same item via the real artikel_id relationship
    article_export.py  Item list as a formatted .xlsx file
    lagerorte.py        Read a user's storage-location assignment (branch switching, target of a goods receipt)
    lieferadresse.py    Detect the storage location from a document's delivery address (suggestion)
    wareneingang.py     Expected deliveries, confirm arrival, book receipt
    manuelle_erfassung.py Book in goods without a document directly (D23/D27)
    artikel.py          Item and variant rules (rule 4/5) shared by import and manual recording
    ean.py              Check digit, validation, and internal EAN-13 (GS1 20-29)
    barcode.py          EAN-13/EAN-8 as a bar pattern (no extra library)
    etikett.py          Label as a PDF in label size (PyMuPDF)
    reduktion.py        Storage duration and markdown stage per rule 6
    kategorien.py       POS category: selection list, set manually, never overwritten (B8)
    bestand.py          Read stock: quantity per variant x storage location, filters and metrics (C2)
    ausbuchung.py       Book sale/removal, reverse via counter-booking, list of write-offs (C3)
    uebersicht.py       Metrics, upcoming items, and current activity for the overview
    artikel_loeschen.py Fully remove an incorrectly recorded item without a document
    umlagerung.py       Transfer with date rules D13/D17/F10/F11 (C4)
    korrektur.py        Correction: book the difference to the counted quantity (C5)
    reduktion_manuell.py      Manual markdown per model x branch (30/50/70)
    reduktion_bestaetigung.py "Done" on the markdown list (D-F1)
    reduktion_empfehlung.py   Head-office recommendation and branch response (D-F3)
    hinweise.py         Notice when a marked-down model is delivered again (D-F2)
    statistik.py        Statistics: sales per category, revenue estimate, best sellers with current stock
    konten.py           Create/delete accounts (head office)
    anmeldung.py        Login lockout after 5 wrong passwords (S2)
  templates/         HTML pages (served by the routers via FileResponse)
  static/
    css/, js/          Stylesheet and frontend scripts (theme, session, i18n, preview, item details)
    js/i18n.js           Load the catalog, apply data-i18n, window.SportfabrikI18n.t()
    js/nav.js            Main navigation (grouped, active page, menu on narrow screens)
    js/session.js        Top-right header: branch and account menu
    i18n/{de,fr,en}.json Translation catalog (single source, also read by the backend)
    fonts/, img/        Self-hosted font, logo
    BRAND-SOURCES.md    Source of logo/font, brand colors

migrations/          Alembic migrations (see docs/SERVER-SETUP.md for the process)
scripts/
  manage_users.py    CLI to create/remove users (employee/branch manager/admin) and their branch assignment
  backup_inventory.py Verified backup of the database and original PDFs (see docs/BACKUPS.md)
  claude-cloud-setup.sh   Plugins for Claude Code cloud sessions (see docs/claude-cloud-setup.md)
  claude-session-deps.sh  Project dependencies in cloud sessions (see docs/claude-cloud-setup.md)
  projektwissen.py   Local knowledge search over code and doc sections (see docs/obsidian-graphify.md)
docs/                Detailed documentation (see above) and deployment guides
tests/               pytest suite, one test module per business area
```

Rule of thumb for new code: HTTP endpoints belong in `routers/`, reusable
business logic without a direct HTTP dependency belongs in `services/`,
and everything around the database/models/security belongs in `core/`.

## Local setup (Windows development machine)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

For the OCR fallback on scanned paper invoices, also install Tesseract
OCR — it's an external program, not a Python package, so it's not
included in `requirements.txt`: download the Windows installer from
[github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki),
under "Additional language data" also select the German (`deu`) and
orientation-detection (`osd`) language packs, and add the installation
folder (default `C:\Program Files\Tesseract-OCR`) to `PATH`. Without
Tesseract, the app keeps working normally — only scanned invoices (not
received digitally by email) can then not be uploaded. On the Linux
server, Tesseract is already included in the Docker image, so no extra
step is needed there.

Create `.env` (not checked in) with at least:

```
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/inventory_db
SESSION_SECRET=<generate via "python -c "import secrets; print(secrets.token_hex(32))"">
```

Create or keep the database schema up to date:

```powershell
alembic upgrade head
```

Create the first branch-manager account, so a login is possible at all
(storage-location codes: SF1-SF4 for the branches, GEWA/VEBO/DIETIKON for
the external locations; the first code given is set as the primary
branch):

```powershell
python scripts/manage_users.py add-chef <cash-register-number> "<Name>" SF1
```

(The CLI command and the internal role name are still called
`chef`/`add-chef` — only the interface displays "Filialleiter" (branch
manager) for it. For a cross-branch admin/head-office account, use
`add-admin <cash-register-number> "<Name>"` without a storage-location
argument.)

Start the app:

```powershell
fastapi dev app/main.py
```

## Tests

```powershell
pip install pytest
DATABASE_URL=sqlite:// pytest -q
```

The tests are built around main flows (decision 2026-09-24): a few large
flow tests over the real app with login (`tests/test_ablauf_*.py`:
document, recording, stock, items, login, markdowns, recommendations,
notices, statistics, accounts, phone), plus small table-driven tests
for hard rules (`tests/test_regeln.py`), the parsers
(`tests/test_parser.py`), and operations (`tests/test_betrieb.py`:
migrations, scripts, no internet in the frontend). Shared test fixtures
with master data and accounts per role: `tests/conftest.py`; self-built
sample documents: `tests/testbelege.py`. For new features, the rule is:
**test first**.

Real documents never live in the repo. Some tests are therefore skipped
when an optional prerequisite is missing: the original INTERSPORT invoice
(set the `INTERSPORT_TEST_PDF` environment variable to its path), a
locally installed Tesseract, or Node.js (frontend scripts and login
redirect).

## Backups

See [`docs/BACKUPS.md`](docs/BACKUPS.md): verified, automated backup of
the database and original PDFs (`scripts/backup_inventory.py`).

## Deployment

See [`docs/SERVER-SETUP.md`](docs/SERVER-SETUP.md) for the Docker build,
server setup, data migration, and the process for future schema changes.
