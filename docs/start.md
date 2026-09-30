# Sportfabrik Inventory — Getting started

Status: 2026-09-29. This overview is orientation, not confirmation of a production deployment.

## Goal and current status

Inventory management for four Sportfabrik branches; GEWA, VEBO, and Dietikon are external storage locations without sales. Documents are parsed locally on-site. Item master shared across branches, stock and booking rights are branch-specific. Later: POS integration and online shop.

**Implemented:** phases A–D (Phase D incl. D-F1 to D-F4, 2026-09-25), the **Item Details and Reports** catalog (all 17 points), the **UI redesign after DESIGN.md** (2026-09-27, PRs #16/#17), **HTTPS** (security S1, locally), **phone use** under `/m`, and the **decisions of 2026-09-28**: employees book out sales only, markdown 30 % from arrival (50/70 % after 18/36 months), markdown changes only in one's own branches (head office all), "Pending" per branch, transfer as a delivery with dispatch date and arrival confirmation, statistics with removals and "this week". **2026-09-29:** markdown choice at goods entry (N2), cancelling a transfer in transit, security S1 rest (sessions end on password change), S3, S4 (age-encrypted external backups), S5–S7 (headers + CSP), transfer cancel also for the dispatcher, **dashboard redesign** (sales of the last 14 days, stock by markdown stage, best sellers, activity grouped by day; small charts allowed in `DESIGN.md` §9.3); all migrations checked on PostgreSQL 18 (throwaway Docker container, up/down/up, app smoke test). All docs in English. Tests: 177 passed, 12 skipped (SQLite, 2026-09-29; skips = parser tests that need local documents). Checked locally only — no store deployment.

**GitHub:** PR #18 merged into `main` (2026-09-29); `feature/warenwirtschaft-v2` (working branch) equals `main`.

## Newly planned — 2026-09-29

“Pending”: show missing EAN and checkout-category totals across all branches to all roles; matching result lists must also be cross-branch. Other notices remain scoped to the selected branch. No permission changes. **Not implemented yet.** See the latest decision in `projekt-kontext.md`.

## Next steps

**First: Sportfabrik Inventory Redesign**, explicitly prioritized on 2026-09-29. Follow [the redesign specification](redesign-2026-09-29.md): structural sidebar layout on all pages, stacked existing logo, exact navigation, function search, dashboard charts and Settings modal; preserve current colors and design elements. Phases 1–5 (sidebar layout, navigation order, labels, `/anstehend` page, top search) are done on branch `worktree-redesign-sidebar`; open: Settings modal, dashboard charts, reviews (phases 6–8 in the specification).

The previously queued items below follow the redesign:

1. PR for the 2026-09-29 work (N2, transfer cancel, security S1/S3–S7) into `main` — at the end of this session.
2. Store deployment (Phase F): migrations on the store server's database (checked locally on PostgreSQL 18), network separation/VPN (required for the 6-character password decision), create the age key pair (`docs/BACKUPS.md`), S8 hash pins (`docs/sicherheit.md`, `docs/SERVER-SETUP.md`). After the update everyone logs in once more (S1).
3. Test phones in the store with real labels (iPhone + Android); remove the temporary "−1" stock button after the in-store trial.

Full list with context: `docs/projekt-kontext.md`, sections "Status check and next steps – 2026-09-28" and "Decisions and implementation – 2026-09-29".

Working branch: `feature/warenwirtschaft-v2`; check the actual branch and any open changes first.

## Open only the source that fits the task

| Question | Main source |
|---|---|
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

## Newly planned: head-office recommendations (2026-09-29)

Not implemented: branch-specific Pending notice linking to recommendations, withdrawal by head office, and sending to all sales branches in one action with separate branch responses. Clarify withdrawal after acceptance, branches without stock, and visibility before the effective date before implementation. See the latest planned extensions in `projekt-kontext.md`.
