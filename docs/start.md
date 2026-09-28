# Sportfabrik Inventory — Getting started

Status: 2026-09-28. This overview is orientation, not confirmation of a production deployment.

## Goal and current status

Inventory management for four Sportfabrik branches; GEWA, VEBO, and Dietikon are external storage locations without sales. Documents are parsed locally on-site. Item master shared across branches, stock and booking rights are branch-specific. Later: POS integration and online shop.

**Implemented:** phases A–D (Phase D incl. D-F1 to D-F4, 2026-09-25), the **Item Details and Reports** catalog (all 17 points), the **UI redesign after DESIGN.md** (2026-09-27, PRs #16/#17), **HTTPS** (security S1, locally), **phone use** under `/m`, and the **decisions of 2026-09-28**: employees book out sales only, markdown 30 % from arrival (50/70 % after 18/36 months), markdown changes only in one's own branches (head office all), "Pending" per branch, transfer as a delivery with dispatch date and arrival confirmation, statistics with removals and "this week". All docs in English. Tests: 167 passed, 12 skipped (SQLite, 2026-09-28). Checked locally only — no PostgreSQL run, no store deployment.

**GitHub:** `main` ends at PR #17. `feature/warenwirtschaft-v2` (working branch) is ahead of `main` with everything above.

## Next steps

1. Merge `feature/warenwirtschaft-v2` into `main` (PR); delete the merged/obsolete branches.
2. **Open question for Fabian (N2):** choosing the markdown at goods entry — store it as the manual markdown of the target branch?
3. Store deployment (Phase F): PostgreSQL run of all migrations (incl. `f3a4b5c6d7e8`), network separation/VPN (required for the 6-character password decision), S1 rest (sessions on password change), S3–S8, encrypted backups (`docs/sicherheit.md`, `docs/SERVER-SETUP.md`).
4. Test phones in the store with real labels (iPhone + Android); remove the temporary "−1" stock button after the in-store trial.
5. Possible follow-up: cancel a transfer that is still in transit (wrong destination).

Full list with context: `docs/projekt-kontext.md`, section "Status check and next steps – 2026-09-28".

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
