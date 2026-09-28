# Inbox additions from 2026-09-24

## Binding priority – 2026-09-24

Fabian has decided: **First implement the new requests from the inbox, then continue phase D.** The already-built markdown page stays as-is; this neither resets phase D nor marks it as complete.

Priority goes to the entire new requirements catalog "Item details and reports": clean up item details, simplify lists and workflows, personalize the overview and quick access, add statistics and account management. The explicitly requested manual markdowns (all staff, per branch, 30/50/70%, selection via EAN or stock list, shown in item details and stock) also belong to this pulled-forward package, even though they technically touch phase D.

Only after that come the remaining phase D work and open decisions. Mobile usage stays planned for the end of the project, as agreed. Required checks before store deployment remain in place. This is a priority decision, not a confirmation of implementation.

Requirements catalog: [Item details and reports](anforderungen-artikeldetails-auswertungen-2026-09-24.md).


Status: documentation sync; no code, parser, or test changes.

## Labels – current specification

Fabian's latest explicit spec: **width 47 mm, height 83 mm** (portrait). This replaces the previous target of 84 × 47 mm. This does not automatically change the previously documented code default.

Three interchangeable rolls are already pre-printed: 30% with a yellow dot, 50% with a red dot, 70% with a green dot. The scan shows a blank 30% template and two printed examples: struck-through price 333.00 / supplier 111 / year 25, and 499.00 / supplier 999 / year 27. Match the print layout to the pre-printed elements; clarify barcode position and print orientation against the sample.

Local source in the Obsidian vault Main: `03 Ressourcen/Sportfabrik Inventory – Etikettenbeispiele.md`.

## FEDAS source

Fabian has provided the German overview: http://download.fedas.com/actualversion/download/pdf/ger_pdf_overview.pdf . He describes it as the list with all codes. Retrieval on 2026-09-24 failed (HTTP 502); version, completeness, and specific codes not yet checked. This supersedes the earlier statement that no list was known; the verified import and mapping to POS categories remain open. Do not adopt unverified codes.

Local source: `03 Ressourcen/Sportfabrik Inventory – FEDAS-Liste.md`.

## Alpina paper scan

Additional local parser sample: delivery note 119719, ship date 2026-09-01, order 151850, SF1 Volketswil, one page, four line items, 29 units, open quantity 0. JPEG scan with EAN barcodes, RRP, quantities, and a handwritten mark. No stock booking or parser implementation from this sync.

Local source: `03 Ressourcen/Sportfabrik Inventory – Alpina-Lieferschein 119719.md`. The scan stays in the local vault and is not copied into the public repository.

## Test cleanup – requested work

Fabian's request: clean up all tests, keep only the most important ones, review less important basic-feature tests for deletion, and build large, current main-feature tests. Goal: lower token usage. Selection and scope still open; no blanket test deletion, and no claim that this has already been done. The project rule requiring a green test run before commits stays in place.

Local source: `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory Tests aufräumen.md`.

## Further inbox requirements – 2026-09-24, afternoon

Status: all five points implemented on 2026-09-24 (commits `431dc6f`, `fd95054`), checked in the browser against a test database.

- [x] Clicking an entry under "Upcoming" opens the matching filtered list directly; e.g. "2 variants without EAN" shows exactly those two variants.
- [x] Auto-focus quick search on the stock page when it opens.
- [x] Move "Show columns" on the item page into "More filters".
- [x] Show the currently selected branch prominently in the stock page's title; the smaller branch switcher stays as well.
- [x] Make the quick-access buttons on the overview a consistent size.

### Mobile usage – agreed plan for the end of the project

Agreed with Fabian on 2026-09-24; **planning only, implementation not until near the end of the project**. Web app on personal phones with camera scanning and stock workflows. Staff only on the store Wi-Fi; branch managers and management/head office also from outside. Existing rights and central data storage stay unchanged. Technical VPN/Wi-Fi solution still open. Full plan: [Mobile usage](handynutzung.md). **Status update:** built earlier than planned, on 2026-09-28 — see `docs/handynutzung.md` and the "Mobile phone use – implemented 2026-09-28" section in `docs/projekt-kontext.md`.

### Keep the visual documentation up to date together

For every change to context, progress, decisions, or other project documentation, also update both HTML documents in the local Obsidian vault Main: `Anhänge/Sportfabrik Warenwirtschaft.html` and `Anhänge/Sportfabrik Warenfluss.html`. Explicitly distinguish current state, open requirements, and ideas. Don't copy any private image file into the public repository.

Sources in the vault: `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory – Bedienungswünsche vom 24.09.2026.md`, `Sportfabrik inventory aufs Handy.md` in the same folder, and `03 Ressourcen/Sportfabrik Inventory – Visuelle Übersichten.md`.

## Further requirements: item details and reports

17 new points from two inbox notes are consolidated in [Item details and reports](anforderungen-artikeldetails-auswertungen-2026-09-24.md). Confirmed: revenue as an estimate at the reduced price at the time, manual markdown by all staff per branch to 30/50/70%, per-user quick access. No confirmation of implementation.
