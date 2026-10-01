# Sportfabrik Inventory — Getting started

Status: 2026-10-01. This overview is orientation, not confirmation of a production deployment.

## Goal and current status

Inventory management for four Sportfabrik branches; GEWA, VEBO, and Dietikon are external storage locations without sales. Documents are parsed locally on-site. Item master shared across branches, stock and booking rights are branch-specific. Later: POS integration and online shop.

**Implemented:** phases A–D (Phase D incl. D-F1 to D-F4, 2026-09-25), the **Item Details and Reports** catalog (all 17 points), the **UI redesign after DESIGN.md** (2026-09-27, PRs #16/#17), **HTTPS** (security S1, locally), **phone use** under `/m`, and the **decisions of 2026-09-28**: employees book out sales only, markdown 30 % from arrival (50/70 % after 18/36 months), markdown changes only in one's own branches (head office all), "Pending" per branch, transfer as a delivery with dispatch date and arrival confirmation, statistics with removals and "this week". **2026-09-29:** markdown choice at goods entry (N2), cancelling a transfer in transit, security S1 rest (sessions end on password change), S3, S4 (age-encrypted external backups), S5–S7 (headers + CSP), transfer cancel also for the dispatcher, **dashboard redesign** (sales of the last 14 days, stock by markdown stage, best sellers, activity grouped by day; small charts allowed in `DESIGN.md` §9.3); all migrations checked on PostgreSQL 18 (throwaway Docker container, up/down/up, app smoke test). All docs in English. Tests: 177 passed, 12 skipped (SQLite, 2026-09-29; skips = parser tests that need local documents). Checked locally only — no store deployment.

**GitHub:** PR #18 merged into `main` (2026-09-29); `feature/warenwirtschaft-v2` (working branch) equals `main`.

## Done 2026-09-30 (after the redesign)

Merged into `feature/warenwirtschaft-v2` (not pushed, not in `main`), checked locally only: collapsible sidebar (hamburger, choice kept per browser), user name next to the user icon, larger menu text, Settings entry removed from the menu (the user icon and branch pill open the same dialog); quick-access cards above the greeting (title only, equal height, full width, gear icon); **Pending** counts "without EAN" / "without checkout category" across all branches for all roles (lists match); **bell icon** top right on every page with the number of Pending notices (`/api/anstehend/anzahl`); **preset markdown scanning** on Runterschreiben (pick a stage, every scanned item is set to it); **head-office recommendations**: open ones show in the branch's Pending immediately, head office can withdraw any recommendation at any time (status `zurueckgezogen`, no rollback of a stage already set) and send one to all sales branches in one action (also branches without stock; each branch answers separately). Migration `b5c6d7e8f9a0`. Tests: 183 passed, 12 skipped.

## Next steps

**First: Sportfabrik Inventory Redesign**, explicitly prioritized on 2026-09-29. Follow [the redesign specification](redesign-2026-09-29.md): structural sidebar layout on all pages, stacked existing logo, exact navigation, function search, dashboard charts and Settings modal; preserve current colors and design elements. All 8 phases are done (merged into `feature/warenwirtschaft-v2`); the follow-up refinements of 2026-09-30 are listed above.

**Proposed next milestone (2026-10-01, not yet approved):** "one branch can reconcile a complete working day, recover from mistakes, and restore its data." Five work packages (reliable receiving/cancellation, safe counting and retries, one-branch pilot, returns/held stock, price snapshots/planning) and nine open business questions: [roadmap-operational-reliability-2026-10-01.md](roadmap-operational-reliability-2026-10-01.md). Open questions Q1–Q9 answered on 2026-10-01 (pilot SF1, cancel instead of delete, invoices attach to deliveries, no data loss); package order 0–5 approved; Fabian reconciles SF1 daily. Package 0 started 2026-10-01: "order recommendation" renamed to "best sellers with current stock" (UI texts DE/FR/EN; API key `bestellempfehlung` unchanged); the PR into `main` is still open. Package 0 PR: [#19](https://github.com/FreaXz03/sportfabrik-inventory/pull/19) (description updated). **Package 1 step 1 done 2026-10-01:** a posted document is cancelled with counter-movements instead of deleted (`app/services/beleg_storno.py`, `/api/invoices/{id}/cancel-preview` + `/cancel`, UI on the document page, migration `c6d7e8f9a0b1`); delete remains only for documents without postings. Open: re-importing a cancelled file is still blocked by the unique file hash/document number. **Package 1 step 2 done 2026-10-01:** a delivery note or invoice that matches an existing delivery (same supplier and branch, ≥ 50 % of its lines, ≤ 120 days; `app/services/lieferung.py`) must be attached or booked as new goods — the preview asks, the server enforces (409), nothing is automatic; an attached document books nothing (table `dokument_lieferung`, migration `d7e8f9a0b1c2`, `POST /api/lieferung-kandidaten`). Match thresholds are working values, not a business decision. Not done in step 2: "confirm an existing arrival" from a document (arrival is still confirmed on the goods-receipt page), separate arrival date per document, Pending list of open deliveries. **Package 2 done 2026-10-01:** optional operation ID (`X-Operation-Id`) on sale, count, transfer, arrival and manual entry — same ID returns the stored result and books nothing (`app/services/operation.py`, table `operationen`); stale-count check on `/api/korrektur` (`stand_bewegung_id` from `/api/bestand`, `409 bestand_geaendert`, recount or `bestaetigt`) and a record of every count in `zaehlungen` — phone and desktop count screens updated, migrations `e8f9a0b1c2d3`, `f9a0b1c2d3e4`. Both parts are optional on the API (decision 2026-10-01): clients that send no ID/marker are not protected. Next: package 3 (SF1 operating pilot) — mostly operations; see the roadmap. Items 2 and 3 below become part of package 3 (pilot).

The previously queued items below follow the redesign:

1. PR for the 2026-09-29 work (N2, transfer cancel, security S1/S3–S7) into `main` — at the end of this session.
2. Store deployment (Phase F): migrations on the store server's database (checked locally on PostgreSQL 18), network separation/VPN (required for the 6-character password decision), create the age key pair (`docs/BACKUPS.md`), S8 hash pins (`docs/sicherheit.md`, `docs/SERVER-SETUP.md`). After the update everyone logs in once more (S1).
3. Test phones in the store with real labels (iPhone + Android); remove the temporary "−1" stock button after the in-store trial.

Full list with context: `docs/projekt-kontext.md`, sections "Status check and next steps – 2026-09-28" and "Decisions and implementation – 2026-09-29".

Working branch: `feature/warenwirtschaft-v2`; check the actual branch and any open changes first.

## Open only the source that fits the task

| Question | Main source |
|---|---|
| Next milestone proposal, work packages, open questions | `docs/roadmap-operational-reliability-2026-10-01.md` |
| Newest requirements and their code status | `docs/anforderungen-inbox-2026-09-28.md` |
| Business decisions, roadmap, open questions | `docs/projekt-kontext.md`, sections 4, 9, 10, and the latest dated section at the end |
| Implementation history | `docs/projekt-kontext.md`, section 11 and addenda; cross-check against current code |
| Item details and reports (points 1–17) | `docs/anforderungen-artikeldetails-auswertungen-2026-09-24.md` |
| Architecture and workflows | matching section of `docs/architektur.md` |
| Tables, migrations, API | `docs/datenmodell.md`, `docs/api-referenz.md`, and affected source files |
| Phone use | `docs/handynutzung.md`; API: `docs/api-referenz.md`, "Phone pages" |
| Security / store deployment | `docs/sicherheit.md`, for deployment `docs/SERVER-SETUP.md` |
| Older usage requests / labels | `docs/anforderungen-inbox-2026-09-23.md`, `docs/anforderungen-inbox-2026-09-24.md` |
| Graphify, selection, local search | `docs/obsidian-graphify.md` |
| Interface, colors, typography, components | `DESIGN.md` |
| Visual overviews (non-technical) | `docs/overviews/` (mirror of the vault versions) |

Unknown relationships: `python3 scripts/projektwissen.py query "Umlagerung"` or `"reduktionen_manuell"`. Returns code relationships and document hits with limited output. Then read the original sections directly, not the whole graph.

The main vault holds ideas and requirements; the generated Sportfabrik graph is an optional view. Historical status notes are not an additional current source. Cloud sessions without a local graph search the original files directly.
