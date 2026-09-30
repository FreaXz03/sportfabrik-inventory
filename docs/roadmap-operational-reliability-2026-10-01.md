# Roadmap — operational reliability (proposal 2026-10-01)

Status: **proposal, not approved.** Derived from the vault note "Sportfabrik Inventory – Capability Review and Improvement Priorities" (static review of 2026-09-30, commit cc17d0c). Nothing here is implemented. Every package needs Fabian's answers to its open questions before implementation starts; no business rule below is decided yet.

## Milestone

> **One branch can reconcile a complete working day, recover from mistakes, and restore its data.**

This replaces "more features" as the next substantive milestone. Already requested UI work may still be finished, but it no longer counts as the main measure of progress.

## Code observations re-checked on 2026-10-01

Spot-checked against `feature/warenwirtschaft-v2` (a69ecc5); the review findings still hold:

| Finding | Where | Conflict with |
|---|---|---|
| Deleting a posted document deletes its `lagerbewegungen` rows, then recalculates stock | `app/services/importer.py:391`, `:435` | Hard rule 2 (every change is a movement line) |
| Correction computes `counted − balance at submission`; no count time, version, or session | `app/services/korrektur.py:66`, `:95` | — (race with concurrent sales) |
| No operation identifier on stock-changing requests (sale, transfer, partial arrival) | no `idempot*`/`operation_id` in `app/` | — (phone retries can double-book) |
| Revenue estimate ignores manual markdowns (no history) | `app/services/statistik.py:9`, `reduktion_manuell.py:60` | — (reports can overstate revenue) |
| Invoice and delivery note each create an arrived receipt; matching only by file hash / document number | `app/services/importer.py:186` | Hard rule 3 risk (same goods booked twice) |
| `bestellempfehlung` = top 10 models by units sold, not a replenishment calculation | `app/services/statistik.py:186` | — (misleading name) |

## Work packages (in order)

Each package: failing test first for the hard rule it protects (see CLAUDE.md), then implementation, then the review steps of `.claude/rules/development-workflow.md`.

### Package 0 — Housekeeping (small, can start now)

- PR of the 2026-09-29/30 work into `main` (already queued in `start.md`).
- Rename the "order recommendation" statistic to what it is ("best sellers with current stock") via translation keys DE/FR/EN. No logic change.
- Decide the open questions of packages 1–3 (list below), so implementation is not blocked.

### Package 1 — Reliable receiving and cancellation

Goal: posted history is never rewritten; one physical delivery is booked once.

1. **Cancel instead of delete.** Unposted drafts may still be deleted. A posted document is cancelled with linked counter-movements (pattern: sale reversal in `app/services/ausbuchung.py`). Original document, source snapshot, and prices stay. Preview shows the quantity effect and flags later sales/transfers of the same variants.
2. **Link documents to one delivery.** Shared delivery/order reference. On import, choose: new expected delivery / confirm an existing arrival / attach document without changing quantity. Default for an invoice whose goods already exist: review, not a second receipt. Store document date and physical arrival date separately.

Acceptance: (a) receive 10, sell 3, cancel the receipt → original + cancellation visible, balance −3 shown as a discrepancy, nothing deleted. (b) Confirmation 10, receive 8, attach delivery note and invoice, receive 2 → stock 10, all documents linked, nothing left open.

Touches: `importer.py`, `wareneingang.py`, models + Alembic migration, preview UI, Pending.

### Package 2 — Safe counting and phone submissions

1. **Stale-count check.** A count starts with the balance and a timestamp. If stock moved before submission, ask for a recount (first version: warning). A count without difference is saved as "counted, no difference".
2. **Retry protection.** Each deliberate user action (sale scan, transfer, partial arrival, correction) carries a client-generated operation ID. Same ID again → return the stored result. New scan → new ID → new booking.

Acceptance: count 7, colleague sells 1, submit 7 → no extra unit appears silently. Response lost after a sale, retry → one sale; two intentional scans → two sales.

Touches: `korrektur.py`, `ausbuchung.py`, `umlagerung.py`, `wareneingang.py`, phone JS under `/m`, one migration (operation-ID table with unique constraint).

### Package 3 — One-branch operating pilot

Mostly operations, partly parallel to packages 1–2. Builds on Phase F in `start.md` / `docs/SERVER-SETUP.md`.

- Store server, network separation/VPN, S8 hash pins (`docs/sicherheit.md`).
- Backups scheduled on the server itself (not a local Codex task), external age-encrypted copy, **one demonstrated full restore** (database + original documents) into an isolated environment.
- Verified opening count for the pilot branch (migrated quantities are historic receipts without sales — not a starting balance).
- One agreed sales-capture process until POS integration (Phase G) exists; daily reconciliation owner.
- Real scanner, label printer, iPhone + Android trial; remove the temporary "−1" button afterwards.
- Written outage procedure; agreed acceptable data loss and downtime.

Acceptance: one real day of receipts, sales, returns, transfers, and closing counts reconciles; restore works.

**Do not start all four branches on the migrated balances.**

### Package 4 — Returns, held stock, transfer discrepancies

1. Stock states: at least *saleable* and *held/inspection* per variant and location.
2. Customer return: condition, reason, original sale if known, outcome (release / supplier return / write-off). Refund reference stored separately.
3. Explicit outcomes for open quantities: awaiting remainder, supplier cancelled remainder, shortage under investigation, lost in transit, returned to source. Existing transfer cancellation stays for mistaken dispatches only. Show transit age and responsible person.
4. Pending becomes an exception list: negative balances, overdue transit, delivery differences, returns awaiting inspection, count conflicts, stale backups — each with cause, transaction, owner, resolving action. Negative stock stays allowed (decision 2026-09-22); it becomes actionable, not blocked.

Acceptance: two returned shoes go to inspection, neither saleable automatically. Ship 10, receive 9, declare 1 lost → transfer closed with a linked loss, no unit reappears at the source.

### Package 5 — Price snapshots, planning, reporting

1. Each sale stores RRP, effective markdown, estimated unit price, currency, and source of the calculation. Markdown changes become append-only history. Later: actual POS amount next to the estimate. Older figures labelled "reconstructed".
2. Replenishment proposal per variant: sales rate, saleable stock, incoming goods, lead time, pack size, "reorderable" flag; check other branches first.
3. Reports: stock accuracy, negative balances, transit age, return reasons, slow movers, size completeness. Stock value / margin only after a costing policy exists; missing purchase price is "unknown", never zero (rule 10).
4. Exports: stock per branch, movements, open receipts/transfers, price history.

Acceptance: changing today's markdown never changes yesterday's sale estimate. A confirmed incoming delivery reduces the proposal.

## Open business questions (Fabian)

Not answered — do not implement guesses.

| # | Package | Question |
|---|---|---|
| Q1 | 1 | Who may cancel a posted document — branch manager/head office only (same as upload/delete today, rule 9)? |
| Q2 | 1 | Does a delivery note always arrive with the goods, or can it arrive before/after? Same for invoices. |
| Q3 | 1 | When an invoice matches an existing delivery: attach silently, or always ask? |
| Q4 | 2 | Stale count: always force a recount, or allow "count minus sales since start" automatically? |
| Q5 | 2 | Should large count differences need branch-manager approval? (Optional; today employees may correct in own branches.) |
| Q6 | 3 | Which branch pilots? How are sales captured until the till connection exists? Who reconciles daily? |
| Q7 | 3 | Acceptable data loss (e.g. last hour / last day) and downtime during an outage? |
| Q8 | 4 | Who decides a return's outcome, and who may declare transit goods lost? |
| Q9 | 5 | Which items are reorderable vs. seasonal/one-off? Where do lead times come from? |

## Deliberately postponed

Full accounting, CRM, newsletter, supplier portal; AI forecasting before data is reliable; RFID and warehouse optimisation; full offline booking (online-only phone use stays accepted — retries and outage handling first); batch-based markdown aging (current 30/50/70 % clock stays, rule 6); cosmetic dashboard work as the main progress measure.
