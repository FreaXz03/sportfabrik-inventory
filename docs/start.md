# Sportfabrik Inventory — Getting started

Status: 2026-09-28. This overview is orientation, not confirmation of a production deployment.

## Goal and current focus

Inventory management for four Sportfabrik branches; GEWA, VEBO, and Dietikon are external storage locations without sales. Documents are parsed locally on-site. Item master shared across branches, stock and booking rights are branch-specific. Later: POS integration and online shop.

Phases A–C are complete per project documentation. Phase D is fully implemented as of 2026-09-25: markdown write-downs and manual markdowns, plus the open questions D-F1 to D-F4 (confirmation list, restock notice, head-office recommendation, fixed thresholds — details in section 10). The **Item Details and Reports** catalog (all 17 points) is also implemented. The **UI redesign after DESIGN.md** (tokens, typography, components, icon sprite, scan/empty/loading states, formal-address decision) is fully implemented as of 2026-09-27, including ultrareview fixes from PR #16 — see the "UI redesign after DESIGN.md" addendum in `docs/projekt-kontext.md`. All project docs were translated German → English on 2026-09-28 (content unchanged). Everything checked locally only (no PostgreSQL run, no store deployment). Next focus: prepare store deployment (`docs/sicherheit.md`, open items S1 and minimum password length) or mobile usage (planned for project end). Before implementation, cross-check the current code and the end of section 11 in the project context.

Working branch: `feature/warenwirtschaft-v2`; check the actual branch and any open changes. Documented local tests say nothing about PostgreSQL or the running store server.

## Open only the source that fits the task

| Question | Main source |
|---|---|
| Current requirements, points 1–17 | `docs/anforderungen-artikeldetails-auswertungen-2026-09-24.md`; implementation addendum at the end of `docs/projekt-kontext.md` |
| Business decisions, roadmap, open questions | `docs/projekt-kontext.md`, sections 4, 9, 10; note the latest dated addendum |
| Implementation and historical milestones | `docs/projekt-kontext.md`, section 11 and addenda; cross-check against current code |
| Architecture and workflows | matching section of `docs/architektur.md` |
| Tables, migrations, API | `docs/datenmodell.md`, `docs/api-referenz.md`, and affected source files |
| Security / store deployment | `docs/sicherheit.md`, for deployment `docs/SERVER-SETUP.md` |
| Original usage requests / labels | `docs/anforderungen-inbox-2026-09-23.md`, `docs/anforderungen-inbox-2026-09-24.md` |
| Graphify, selection, local search | `docs/obsidian-graphify.md` |
| Interface, colors, typography, components | `DESIGN.md` |

Unknown relationships: `python3 scripts/projektwissen.py query "Umlagerung"` or `"reduktionen_manuell"`. Returns code relationships and document hits with limited output. Then read the original sections directly, not the whole graph.

The main vault holds ideas and requirements; the generated Sportfabrik graph is an optional view. Historical status notes are not an additional current source. Cloud sessions without a local graph search the original files directly.
