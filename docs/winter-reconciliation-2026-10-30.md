# Winter order size reconciliation — 30 October 2026

Managers and head office can open `/winter-abgleich` (also linked from receiving and the import preview), choose an open winter order receipt and upload a branch size matrix (`winterhw_sf1.pdf` etc.). Parsing stays local.

- **Parser** (`parsers/winter_sizes.py`): joins the two table halves (articles/sizes on the first page group, article numbers/extra columns on the second) by row position, keeps section-specific size headers across page breaks, and rejects rows whose size cells do not reconcile with the printed totals or whose partner page is missing. The branch is read from the document and must match the receipt's branch.
- **Preview** (`services/winter_reconciliation.py`): per article the previous quantity, the proposed size split, the new total and the difference. Matching uses the normalised article name; ambiguous or missing matches need an explicit choice. Source warnings block the group.
- **Apply:** only after explicit confirmation and only for selected groups. Sizes must add up to the original quantity unless a quantity revision with a written reason (at least 10 characters) is chosen. Price differences, received lines, delivery differences or stock movements block the replacement. The old ONESIZE lines remain as history (`wareneingang_positionen.ersetzt_durch_abgleich_id`) and no longer count as open, in totals, receiving or EAN generation. New lines reuse an existing size variant of the shared article or create one without EAN (use the bulk EAN button afterwards; ONESIZE EANs are never copied).
- **Safety:** the preview fingerprint and the uploaded file hash bind the request; stale previews are rejected; the same request is idempotent; a file may complete remaining groups once. The audit table `winter_abgleiche` keeps before/after, actor, file name and reason. No stock is booked.
- Migration `b20261030` (checked up/down/up on throwaway PostgreSQL 18; downgrade refuses once audits exist).

Verification: full SQLite suite 383 passed, 43 skipped (private documents/Tesseract/Node missing in the default PATH); `tests/test_betrieb.py` 35 passed with the Playwright-bundled Node; browser flow with confirmation, cancellation, history and receiving list. Not tested with the private branch PDFs or on the development instance (no deployment). The SF1 file totals 2,600 pieces versus 3,266 stored — resolve this difference before applying.

## Full revision (added 30 October 2026)

A branch list can be an updated order rather than a size split of the stored one (the real SF1 list: 2,600 pieces versus 3,266 stored, different models/colours). The page therefore also offers: **new article** as match target, an **entfällt** list for previous articles missing in the new list, and a button "Neufassung auswählen". Any new article, dropped article or quantity change requires the explicit order revision with a reason (at least 10 characters). With an explicit revision the new list's prices apply to the new lines; without it a price difference still blocks. Dropped/replaced lines stay as history; received articles can never be dropped. No stock is booked.

Real-data check (throwaway copy of the development database, PDF `winterhw_sf1.pdf`): 224 of 229 groups applied, 655 active lines, 2,460 pieces; repeating the request was idempotent. The remaining 140 pieces are 5 groups blocked on purpose: Vector CRB and Vector 300 (section header says EP/VP but the totals columns follow the opposite order) and three Flyte JR Revo lines (size column "2" next to ONESIZE sections). They need a human decision.

## Parser exceptions confirmed by the owner (30 October 2026)

- **Vector poles (Skistöcke):** the section prints the two total columns swapped while the unit prices are correct. The row is accepted only when the swapped totals are exactly consistent (VP × quantity in the first total column, EP × quantity in the VP total). The listed VP (69.90 / 39.90) is used; any other inconsistency still blocks.
- **McKinley Flyte JR Revo:** the "2" under the One-Size header is part of the model name. These rows are read as `McKinley Flyte JR 2 Revo <colour>` with size ONESIZE. The rule is limited to this name; other digit columns next to ONESIZE stay blocked.
- Real SF1 list after the change: 235 lines, 2,600 pieces, no blocked groups, EP footer total still matches. Synthetic regression tests: `tests/test_winter_parser_exceptions.py`.

## SF2 list: per-size total line omits one article (30 October 2026)

In the real SF2 list the sections *Winterschuhe Men* and *Winterschuhe Lady* print a "Total pro Grösse" line that leaves out one listed article (Scarpa Rush Polar GTX: 17 and 16 pieces). Row totals and the printed grand totals (120 and 97) are right. The parser now accepts a section only if the difference between the computed and the printed per-size totals equals exactly one listed row and the printed grand total equals the sum of all rows. Any other difference still blocks. Real SF2 list: 202 lines, 2,324 pieces, no warnings, EP footer matches. Tests: `tests/test_winter_parser_exceptions.py`.

## Automatic match suggestions (30 October 2026)

The review table now proposes a target for every new group (`suggest()` in `app/services/winter_reconciliation.py`; nothing is applied automatically). Confidence levels: **exact** (same name), **high** (name ratio >= 0.93, same numbers, unambiguous), **medium** (ratio >= 0.75 but a number/model number differs or several old articles are almost equally similar), **none** (a new article is proposed). Only exact/high suggestions are pre-ticked; medium ones are filled in but unticked with a visible warning, `none` pre-fills "new article" unticked. Articles with received goods are never proposed, each old article is proposed at most once, every field stays editable and manual changes are labelled. A summary line shows the counts and how many previous articles do not occur in the new list. Real SF2 check (parser level, names only): 26 exact, 5 high, 52 medium, 119 none. Tests: `tests/test_winter_suggestions.py`.
