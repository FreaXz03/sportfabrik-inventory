# Inbox requirements from 2026-10-01 (receiving, classification, support)

Recorded in the project on 2026-10-01 from Fabian's vault note "Sportfabrik
Inventory Requirements", section "Receiving, classification and support
follow-ups — 2026-10-01" (original German wording stays in the vault).
**Nothing here is implemented yet.** This file does not decide open business
questions; conflicts with the hard rules in `CLAUDE.md` are named per point.

| # | Requirement | Status / notes |
|---|---|---|
| 1 | A product may sit in only a main group (shoes, textiles, hardgoods) while no subcategory is found | Open |
| 2 | Better automatic category assignment from keywords in the product name and the document filename (e.g. "PANT" → textiles; "OUTDOOR" in the filename + "WOMAN PANT" → textiles / outdoor) | Open. Define FEDAS-vs-keyword conflicts; never overwrite manual assignments |
| 3 | On Deliveries, forward a delivery to another branch before confirming arrival; the destination confirms arrival | Open. Keep history, no duplicate stock postings; related to rule 3 (book only on arrival) and the transfer-as-delivery model |
| 4 | Site-wide bug-report button: popup with title, message, optional images; sent to fabian_morf@icloud.com | Open. Needs an outbound-mail design |
| 5 | Button on the document-upload page to submit documents the system does not recognize, sent to the same address | Open. **Conflicts with rule 1** if the document leaves the server: needs an explicit, user-triggered flow and Fabian's decision first; local parsing stays unchanged |
| 6 | Normalize sizes (D38 → 38; US shoe sizes, e.g. Asics, → EU via a table) | Open. Needs verified brand-specific tables; no universal US→EU conversion. Item data from supplier documents is otherwise not translated (rule 7) — normalization is about sizes only |
| 7 | Parser for `CMP Nachbest. SF1 15.08.26.pdf` | Open. Test run 2026-10-01: current parser reports "unknown layout". The document must be shown explicitly (rule 1) |
| 8 | An internal EAN can be replaced by a newly entered EAN; both stay stored for the variant, the old one stays usable | Open. Touches rule 5 (internal EANs marked as internal); needs a table or column for several EANs per variant |
| 9 | Overview "Stock by main group" shows all items without a main group although some have one | Reported bug, not reproduced yet. The dev DB now holds the 2026-10-01 test-run data to try it |
| 10 | Hide Statistics and Pending when the selected location is GEWA, VEBO or Dietikon (also for mixed assignments) | Open. Confirmed by Fabian 2026-10-01: Dietikon is meant, hiding the pages is enough. Read rights unchanged (rule 9) |

Next steps after approval: 9 (bug), 10 (small), 1–2 (categories), 3, 8, 6,
7 (needs the document), 4–5 (mail design and rule-1 decision).
