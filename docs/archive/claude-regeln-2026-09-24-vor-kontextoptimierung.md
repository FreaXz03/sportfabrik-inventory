# Historical snapshot — do not load as current guidance

Superseded by the current CLAUDE.md. Read only for historical questions.

# CLAUDE.md — Sportfabrik Inventory Management System

Guidance for Claude Code in this repo. **First read `docs/projekt-kontext.md`** — it holds the target picture, all decisions (D1–D27), the proposed data model, and the roadmap. If old code/old docs conflict with `projekt-kontext.md`, `projekt-kontext.md` wins.

## What this is about

Inventory management system for **Sportfabrik** (Intersport outlet, 4 branches in Switzerland: SF1 Volketswil, SF2 Conthey, SF3 Regensdorf, SF4 Hägendorf). Plus three external locations without sale: the processing sites **GEWA** and **VEBO** (functionally equivalent) and the **Dietikon warehouse**.
Goods are entered via upload (invoice / delivery note / order confirmation) or manually; the item master stays forever, stock is tracked per branch, branches get markdown hints (30/50/70%). Later, connection to the Intersport till.

The existing repo (a FastAPI app for Intersport invoices) is the starting point and is being **rebuilt**, not rewritten from scratch: reuse the parser, two-stage import, hash check, audit snapshot, advisory lock, auth, and tests.

## Hard rules

1. **Document data stays local — AI is otherwise allowed.** Invoices, delivery notes, and order confirmations are read by **our own parsers**, running entirely on the server (PyMuPDF, Tesseract, OpenCV or similar): no language model, no cloud service gets to see document data, and an unknown layout is reported rather than guessed. This applies to **operations**. For **building the parser**, Fabian may deliberately show individual documents (decision 2026-09-22) — that content then goes to the model provider, serves only that purpose, and is never published anywhere. Reading documents in bulk or unnoticed remains forbidden (see Graphify). Outside of document processing, AI is permitted, including external services. Development tools follow the same criterion: only run Graphify with `--code-only`, otherwise invoices from `uploads/` or `Rechnungen/` go to a language model (see `docs/obsidian-graphify.md`). Regardless of AI, the frontend stays **free of external CDNs** — it must run on the store network without internet access.
2. **Never overwrite stock directly** — every change is a line in `lagerbewegungen` (receipt, sale, write-off, correction, transfer). Stock is derived from this, or kept consistent with it.
3. **Only book stock once goods have arrived** — order confirmations only create an *expected* goods receipt.
4. **The item master is shared across branches**; stock / goods receipts / markdowns are branch-specific (`lagerort_id`). The master record stays — the only exception: a manually entered item without a document may be deleted entirely by branch manager/head office (mis-entry, decision 2026-09-24).
5. **EAN is optional.** Variants without an EAN must work (key: supplier + item number + color + size). Internal EANs: EAN-13 in the GS1 range 20–29 with a correct check digit, marked as internal.
6. **Receipt-date rules** (for storage duration / markdown):
   - Goods to an external location (GEWA, VEBO, Dietikon — all `verkauf = false`): still **no** receipt date; set on arrival at a branch SF1–SF4 (retroactively if needed). What matters is always `lagerorte.verkauf`, never the individual code.
   - Branch-to-branch transfer: **the original date stays**.
   - Markdown thresholds per branch: 18 months → 50%, 36 months → 70%, counted from the last goods receipt of the same supplier item number **at that branch**; a new delivery restarts the clock.
7. **Multilingual DE / FR / EN.** No new hardcoded UI text — always translation keys (templates + JS + error messages). German is the default. Item data from supplier documents is not translated.
8. **POS categories** exactly as in the till: main group (textile, hardware, footwear, bike, food) × sport area (bike, leisure, tennis, winter, outdoor, football, kids, swimming, indoor, running, skating); bike and food have no sport area.
9. **Rights (2026-09-24):** Employees may manually book in and correct stock, but only in their assigned branches. Booking out a sale/removal, cancelling, and transferring are reserved for branch managers and head office. Their existing cross-branch booking rights remain in place; read rights are unchanged. Uploading/editing/deleting documents remains reserved for branch managers/head office. Confirming "goods arrived" remains allowed (D21).
10. **Purchase price (EK)** may optionally be saved if present in the document — never mandatory.

## Supplementary product requirements from 2026-09-23

Usability and good readability matter a lot: several staff wear glasses and/or have little PC experience. Keep interfaces clear, simplify search, and support scanner workflows. The new requirements and supplier codes are in `docs/anforderungen-inbox-2026-09-23.md`. Item deletion was clarified and implemented on 2026-09-24 (only manually entered items without a document, only by branch manager/head office — see rule 4).

## Tech & conventions

- Python 3.10+, FastAPI, SQLAlchemy 2.0, PostgreSQL, Jinja templates, vanilla JS/CSS (no framework, no build pipeline).
- **Schema changes only via Alembic** (`alembic revision --autogenerate`, then check the migration). Migrate existing data (legacy data → storage location SF1), never discard it.
- Amounts/quantities as `Numeric`, never `float`.
- Validate server-side — never trust client values (see `app/services/corrections.py`).
- Keep the structure: `app/core/` (DB, models, security), `app/routers/` (endpoints), `app/services/` (logic), `app/static/`, `app/templates/`. New supplier parsers as their own modules (e.g. `app/services/parsers/<supplier>.py`) with a shared interface + automatic supplier detection.
- Code and identifiers in English or German as in the existing code; UI text via i18n; commit messages short and to the point.

## Knowledge graph (Graphify)

If a local `graphify-out/graph.json` exists, check there first (modules,
functions, call relationships), then `docs/projekt-kontext.md` /
`docs/architektur.md` for the why, and only open individual source files
last. The graph is a snapshot — **on conflict, the source code wins**.

`graphify-out/` is deliberately gitignored: the repo is public, and a graph
built without `--code-only` contains content from supplier invoices.
Cloud sessions therefore don't have the graph. Details:
`docs/obsidian-graphify.md`.

## Tests

- `DATABASE_URL=sqlite:// .venv/bin/pytest -q` in the project folder; tests for every new piece of logic (stock movements, markdown rules, EAN check digit, parsers, rights).
- **Tests first** (decision 2026-09-24): for every new feature, write the test first, watch it fail (red), then build the feature until it passes (green).
- **Few, large tests** (decision 2026-09-24): one flow test covers a whole main workflow (e.g. upload document → import → stock). Small individual tests only for hard rules (EAN check digit, markdown clock, receipt date, parsers). No tests for incidental things.
- **Documents never go into the repo** (it's public): parser tests with real documents read the files via an environment variable and are skipped without it.
- Before every commit: all tests green.

## Way of working

- Working branch: `feature/warenwirtschaft-v2`. Don't commit directly to `main`.
- Work in small, traceable commits (one subtask = one commit).
- After every completed phase: update `docs/projekt-kontext.md` (section "Implementation status"), `README.md`, and `docs/datenmodell.md` / `docs/api-referenz.md`.
- For open business questions (branch workflows, pricing, till), ask instead of guessing — Fabian works in the store and knows the workflows.

## Completed: Phase A — Foundation

1. Storage locations SF1–SF4 + GEWA/VEBO/DIETIKON (seed data), user ↔ storage location, roles per rule 9, branch switching in the UI. ✅ completed — see `docs/projekt-kontext.md` section 11.
2. i18n groundwork (DE/FR/EN), per-user language choice, existing pages switched to keys. ✅ completed (incl. backend error messages) — see `docs/projekt-kontext.md` section 11 and `docs/architektur.md` section "Multilingualism (i18n)".
3. New data model per `docs/projekt-kontext.md` section 8.2 (suppliers, categories, items/variants, prices, documents, goods receipts, stock movements, stock) + Alembic migration of existing data. ✅ completed, including switching over the live import (not just the migration) — see `docs/projekt-kontext.md` section 11.
4. Update tests + docs. ✅ completed — see `docs/projekt-kontext.md` section 11.

Phase A is now fully complete.

## Completed: Phase B — Goods receipt v2

Subtasks (details and rationale for the order: `docs/projekt-kontext.md`
section 11, "Phase B — split into subtasks"):

1. **Parser registry**: one module per supplier layout (`app/services/parsers/`)
   with a shared interface, automatic supplier and document-type
   detection, unknown layouts clearly reported. ✅ completed —
   see `docs/architektur.md`, section "PDF parsing".
2. Document number unique only **per supplier** (`UNIQUE (lieferant_id,
   dokumentnummer)`) incl. duplicate check in the importer. ✅ completed —
   migration `e5f6a7b8c9d0`.
3. **EAN truly optional** (rule 5), also in parser/corrections.
   ✅ completed — a missing EAN is a hint (doesn't block the import),
   an unreadable EAN stays a warning.
4. **Storage location from the delivery address**, detected and suggested on upload.
   ✅ completed — suggestion (D19), changeable; one document = one storage location (D20);
   all storage locations are bookable (D26).
5. **Expected → arrived** (rule 3, D6): order confirmation/order
   only creates an expected goods receipt; employees may also
   confirm arrival (D21), remaining quantities stay open (D22).
   ✅ completed — page `/wareneingaenge`, migration `f6a7b8c9d0e1`.
6. **Manual entry** with scanner (Z2), also a path for unknown layouts.
   Only brand + description + quantity + RRP are mandatory (D23); this creates **no
   document** — direct goods receipt (D27). ✅ completed — page `/erfassen`,
   migration `a7b8c9d0e1f2`; employees may also enter items (rule 9/D21).
7. **Add/generate EAN afterwards** (internal EAN-13, GS1 20–29) + label as PDF.
   ✅ completed — at the push of a button (D24), label with year, supplier,
   RRP, markdown stage, and barcode (D25); label size configurable
   (default 50 × 30 mm, actual roll size still open).
8. **Choose category manually** when the FEDAS code is missing or unknown.
   ✅ completed — item page, entry, and "No category" filter in the
   item search, migration `c9d0e1f2a3b4`; a manual choice no longer gets
   overwritten by import (`artikel.kategorie_manuell`).

Phase B is now fully complete. Next phase per the roadmap
(`docs/projekt-kontext.md` section 9): **C — Stock**.

## Completed: Phase C — Stock

Subtasks and rationale for the order: `docs/projekt-kontext.md`
section 11, "Phase C — Stock, split into subtasks". In short:

1. **Warning on over-delivery** — more arrived than expected: warn, book anyway. ✅ completed
2. **Stock view per storage location** — all branches readable, external locations shown separately. ✅ completed
3. **Booking out via scan** — manual sale/removal; if stock isn't enough: warn, book anyway. ✅ completed (one scan = one unit)
4. **Transfer** — external → branch sets the receipt date (D13), branch → branch keeps it and doesn't restart the destination branch's markdown clock; if the destination branch never had that item number, the clock starts on arrival (F11). ✅ completed
5. **Corrections** — book the difference with a reason. ✅ completed (enter the counted quantity, the system books the difference)

Phase C is now fully complete (2026-09-23). The stock view temporarily has a
test "−1" button; it will be removed once booking-out has been tried in the
store. Next phase per the roadmap: **D — Prices & markdown**.

Every booking remains a line in `lagerbewegungen` (rule 2) and goes through
the same lock as the receipt.

The FEDAS category suggestion (`app/core/fedas.py`) has been complete since 2026-09-24:
all 54 FEDAS-list activity areas are mapped to one of the 11
sport areas (confirmed by Fabian), plus bike (whole bicycles)
and food (sports nutrition). Only **Kids** can't be derived from FEDAS
and is chosen manually.

## Inbox refinements from 2026-09-24

Label: **47 mm width × 83 mm height**, pre-printed rolls 30% yellow / 50% red / 70% green — implemented (only RRP, supplier code, year, and barcode are printed; positions in `LAYOUT` in `app/services/etikett.py`). FEDAS list checked and mapped (see above). Tests cleaned up (see "Tests"). Details: `docs/anforderungen-inbox-2026-09-24.md`.

## Security

Findings and open measures from the security review on 2026-09-24 are in `docs/sicherheit.md` (S1–S9, with status). Update the status there whenever one is fixed. Mandatory before store deployment (phase F): HTTPS, login lockout (implemented: 5 failed attempts → 20 minutes), network separation, encrypted backups.

## Keep the visual documentation up to date

For changes to context, status, progress, decisions, or other project documentation, update both local HTML overviews: `/Users/fabianmorf/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/Anhänge/Sportfabrik Warenwirtschaft.html` and `Sportfabrik Warenfluss.html` in the same folder. Keep current state, requirements, and ideas separate. New usability requests and mobile planning questions are in `docs/anforderungen-inbox-2026-09-24.md`.

## Binding priority — 2026-09-24

Fabian has decided: **First implement the new requests from the inbox, then continue phase D.** The already-built markdown page stays as-is; this neither resets phase D nor marks it as complete.

Priority goes to the entire new requirements catalog "Item details and reports": clean up item details, simplify lists and workflows, personalize the overview and quick access, add statistics and account management. The explicitly requested manual markdowns (all staff, per branch, 30/50/70%, selection via EAN or stock list, shown in item details and stock) also belong to this pulled-forward package, even though they technically touch phase D.

Only after that come the remaining phase D work and open decisions. Mobile usage stays planned for the end of the project, as agreed. Required checks before store deployment remain in place. This is a priority decision, not a confirmation of implementation.

Details: `docs/anforderungen-artikeldetails-auswertungen-2026-09-24.md`.
