# Sportfabrik Inventory — Working Rules

## Language (decision 28.09.2026)

**All text must be English:** conversation, documentation, commit messages and pull requests. Exceptions: the app's user interface stays trilingual DE/FR/EN via translation keys, German remains the UI default (rule 7); existing German code comments/docstrings and the German management overview (`docs/Sportfabrik-Inventory-Uebersicht-Geschaeftsleitung.docx`) may stay German (decision 2026-09-28).

## Entry and targeted reading

- For project work, first read only `docs/start.md` (short orientation). Do not load the full project context, architecture, vault, or history by default.
- Known file / concrete error: read the relevant spot directly. Unknown relationships: `python3 scripts/projektwissen.py query "<term>"` (scoped graphify query over code and document sections).
- Afterwards, check only the matching original sections and affected source files. The document index shows references — it does not replace business rules.
- If the graph is missing/outdated or a query returns nothing, search once, targeted, with `rg`; no repeated full scans and no automatic AI rebuilds.
- Graph and status notes are orientation. Verify technical facts against the current code; for target behavior, the latest explicit decisions apply. Name contradictions.
- Check the current branch and open changes before editing; preserve changes made by others.

## Hard rules

1. **Document data stays local — AI is otherwise allowed.** Invoices, delivery notes, and order confirmations are read by **our own parsers**, running entirely on the server (PyMuPDF, Tesseract, OpenCV or similar): no language model, no cloud service gets to see document data, and an unknown layout is reported rather than guessed. This applies to **operations**. For **building the parser**, Fabian may deliberately show individual documents (decision 2026-09-22) — that content then goes to the model provider, serves only that purpose, and is never published anywhere. Reading documents in bulk or unnoticed remains forbidden (see Graphify). Exception (2026-10-01): a user may send a document the system does not recognize to Fabian's own mailbox with an explicit click on the upload page — never automatic, never to anyone else. Outside of document processing, AI is permitted, including external services. Development tools follow the same criterion: Graphify may analyze code and explicitly selected project documentation; `--code-only` is optional. No automatic analysis of receipts, uploads, credentials, or personal vault areas. Selection and process: `docs/obsidian-graphify.md`. Regardless of AI, the frontend stays **free of external CDNs** — it must run on the store network without internet access.
2. **Never overwrite stock directly** — every change is a line in `lagerbewegungen` (receipt, sale, write-off, correction, transfer). Stock is derived from this, or kept consistent with it.
3. **Only book stock once goods have arrived.** Order confirmations only create an *expected* goods receipt. The same applies to transfers (2026-09-28): the source dispatches, the destination confirms the arrival. Arrival is confirmed after unpacking and checking.
4. **The item master is shared across branches**; stock / goods receipts / markdowns are branch-specific (`lagerort_id`). The master record stays — the only exception: a manually entered item without a document may be deleted entirely by branch manager/head office (mis-entry, decision 2026-09-24).
5. **EAN is optional.** Variants without an EAN must work (key: supplier + item number + color + size). Internal EANs: EAN-13 in the GS1 range 20–29 with a correct check digit, marked as internal.
6. **Receipt-date rules** (for storage duration / markdown):
   - Goods to an external location (GEWA, VEBO, Dietikon — all `verkauf = false`): still **no** receipt date; it is set on arrival at a branch SF1–SF4 (retroactively if needed). What matters is always `lagerorte.verkauf`, never the individual code.
   - Branch-to-branch transfer: **the original date stays**.
   - Markdown levels per branch (2026-09-28): **30% from arrival**, 18 months → 50%, 36 months → 70%, counted from the last goods receipt of the same supplier item number **at that branch**; a new delivery restarts the clock. There is no item at a branch without a markdown.
7. **Multilingual DE / FR / EN.** No new hardcoded UI text — always translation keys (templates + JS + error messages). German is the default. Item data from supplier documents is not translated.
8. **POS categories** exactly as in the till: main group (textile, hardware, footwear, bike, food) × sport area (bike, leisure, tennis, winter, outdoor, football, kids, swimming, indoor, running, skating); bike and food have no sport area.
9. **Rights (2026-09-24, refined 2026-09-28):** Employees may manually book in and correct stock, and book out **sales only**, all only in their assigned branches. Booking out any other reason, cancelling, and transferring are reserved for branch managers and head office. Markdowns may be changed only in one's own branches — also by branch managers; head office may change all. Their existing cross-branch booking rights remain in place; read rights are unchanged. Uploading/editing/deleting documents remains reserved for branch managers/head office. Confirming "goods arrived" remains allowed for everyone (D21).
10. **Purchase price (EK)** may optionally be saved if present in the document — never mandatory.


## Development and testing

- Python/FastAPI, SQLAlchemy, PostgreSQL, Jinja, and vanilla JS/CSS; reuse the existing structure and parsers. Schema changes via Alembic; preserve existing data. Quantities/money as numeric, validated server-side.
- Keep the interface simple and readable, for scanners and staff with little PC experience. Load details from the requirements catalogs only when needed.
- New business logic: write a meaningful failing test first, then implement. Few end-to-end flow tests; individual tests for hard rules. No tests for pure text changes.
- Before code commits: `DATABASE_URL=sqlite:// .venv/bin/pytest -q`. For pure documentation/tooling maintenance, run targeted checks only; no unnecessary application test run. Report PostgreSQL/production testing separately.
- Documents stay outside the public repo. Parser tests with real documents only via explicit local paths/environment variables.
- Work on the branch `feature/warenwirtschaft-v2`, not directly on main. Small, traceable commits; no push without being asked.
- Don't invent answers to open business questions about branch workflows. Security status: `docs/sicherheit.md`; check open mandatory measures before store deployment.

## Keeping knowledge current, keeping context small

- `docs/start.md`: short current orientation and next priority. Update at each completed milestone; don't append a running log.
- `docs/projekt-kontext.md`: business decisions and detailed implementation history. Update architecture, data model, and API sections only when matching changes are made.
- Vault: ideas and original requirements; link to status and technical details instead of copying the same paragraphs into multiple notes. When docs change, check the two Sportfabrik HTML overviews in the vault for affected content; the repo mirrors them in `docs/overviews/` (copy after updating the vault versions).
- The automatic codegraph hook stays local and AI-free. The document section index is refreshed locally on every query. Semantic document analysis is optional, only for explicit selections; no full vault scan. Details: `docs/obsidian-graphify.md`.
- After finishing a task, briefly note the result, open points, and affected files. Recommend a new session for an unrelated change of task; don't abandon work in progress on your own. Condense long sessions with a compact handover when needed.
- No routine graph/Obsidian exports or parallel agents for minor things. Export only when the view is actually needed; don't change model choice or sessions unasked.
