# Sportfabrik Inventory — Getting started

Status: 2026-09-28. This overview is orientation, not confirmation of a production deployment.

## Goal and current status

Inventory management for four Sportfabrik branches; GEWA, VEBO, and Dietikon are external storage locations without sales. Documents are parsed locally on-site. Item master shared across branches, stock and booking rights are branch-specific. Later: POS integration and online shop.

**Implemented:** phases A–D (Phase D incl. D-F1 to D-F4, 2026-09-25), the **Item Details and Reports** catalog (all 17 points), the **UI redesign after DESIGN.md** (2026-09-27, PRs #16/#17), **HTTPS** (security S1, locally), and **phone use** under `/m` (2026-09-28: search, camera scan, count/correct, goods arrival, transfer, write-off, manual entry, markdowns). All docs are in English since 2026-09-28. Tests: 165 passed, 12 skipped (SQLite, 2026-09-28). Checked locally only — no PostgreSQL run, no store deployment.

**GitHub:** `main` ends at PR #17. `feature/warenwirtschaft-v2` (working branch) is ahead of `main` with English docs, HTTPS, and phone use — pushed, no open PR.

## Next steps

1. Merge `feature/warenwirtschaft-v2` into `main` (PR); delete the merged/obsolete branches `feature/schnellzugriffe`, `claude/sportfabrik-inventory-init-06df66`, `fix/ultrareview-warning-danger`.
2. **Decisions needed from Fabian** (details: `docs/anforderungen-inbox-2026-09-28.md`): may employees book sales (contradicts rule 9)? Minimum 30 % markdown — exact thresholds? Branch managers change markdowns only in their own branches? "Pending" per branch? Transfer as a delivery with dispatch date? Arrival confirmation immediately or after unpacking? Password minimum 6 or 10?
3. Then, test-first: statistics with removals and "this week" as default, 30 % start markdown and wording, markdown rights; design and build "transfer as delivery" (desktop + phone).
4. Store deployment (Phase F): PostgreSQL run of all migrations, S1 rest (sessions on password change), S3–S8, network separation, VPN for off-site branch-manager access, encrypted backups (`docs/sicherheit.md`, `docs/SERVER-SETUP.md`).
5. Test phones in the store with real labels (iPhone + Android).
6. Translate remaining German code comments to English (separate commit).

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
