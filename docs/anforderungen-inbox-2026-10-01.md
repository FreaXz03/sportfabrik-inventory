# Inbox requirements from 2026-10-01 (receiving, classification, support)

Recorded in the project on 2026-10-01 from Fabian's vault note "Sportfabrik
Inventory Requirements", section "Receiving, classification and support
follow-ups — 2026-10-01" (original German wording stays in the vault).
**Status 2026-10-01 (evening): points 1, 2, 3, 8, 9 and 10 are implemented (committed on `feature/warenwirtschaft-v2`, not pushed); 4–7 are open.** This file does not decide open business
questions; conflicts with the hard rules in `CLAUDE.md` are named per point. Fabian answered points 3, 5 and 8 on 2026-10-01 (see table).

| # | Requirement | Status / notes |
|---|---|---|
| 1 | A product may sit in only a main group (shoes, textiles, hardgoods) while no subcategory is found | Open — **Done 2026-10-01:** Textil/Hartware/Schuhe also exist as main group only (rule 8 extended, approved); FEDAS with an unmapped sport area suggests it; migration seeds and backfills. |
| 2 | Better automatic category assignment from keywords in the product name and the document filename (e.g. "PANT" → textiles; "OUTDOOR" in the filename + "WOMAN PANT" → textiles / outdoor) | Open. Define FEDAS-vs-keyword conflicts; never overwrite manual assignments — **Done 2026-10-01 (starter lists):** `app/core/stichwoerter.py`; FEDAS wins, keywords fill gaps, ambiguous matches stay open (e.g. "Kids Running" — business question: which wins?), Velo/Food never by keyword, manual never overwritten. |
| 3 | **Redirect a delivery** to another branch before arrival: a delivery sometimes goes straight to another store, so it must not be booked at the first branch and transferred afterwards. The expected receipt moves to the other branch; that branch confirms arrival | **Decided 2026-10-01** (Fabian): still book only on arrival (rule 3), nothing is booked at the original branch. Open: implementation (change the destination of an expected receipt, keep the history of the redirect, rights: who may redirect) — **Done 2026-10-01:** `POST /api/wareneingaenge/{id}/umleitung`, branch managers/head office, history in `wareneingang_umleitungen`; refused after any arrival and for transfers. |
| 4 | Site-wide bug-report button: popup with title, message, optional images; sent to fabian_morf@icloud.com | Open. Needs an outbound-mail design |
| 5 | Button on the document-upload page to submit documents the system does not recognize, sent to the same address | **Decided 2026-10-01** (Fabian): allowed, because it only goes to his own mailbox. Exception to rule 1: only on an explicit click, only to fabian_morf@icloud.com, never automatic; local parsing stays unchanged. Open: mail design (SMTP settings, attachment size, show the user what is sent) |
| 6 | Normalize sizes (D38 → 38; US shoe sizes, e.g. Asics, → EU via a table) | Open. Needs verified brand-specific tables; no universal US→EU conversion. Item data from supplier documents is otherwise not translated (rule 7) — normalization is about sizes only |
| 7 | Parser for `CMP Nachbest. SF1 15.08.26.pdf` | Open. Test run 2026-10-01: current parser reports "unknown layout". The document must be shown explicitly (rule 1) |
| 8 | Add a second EAN to an existing variant later (e.g. the original EAN next to the internal one); **both EANs lead to the same article/variant** | **Clarified 2026-10-01**: not a replacement, an addition. Open: table for several EANs per variant (e.g. `varianten_eans`), lookups/scans find the variant by any of them, one stays the label/primary EAN, internal EAN stays marked as internal (rule 5) — **Done 2026-10-01:** table `varianten_eans`, `POST /api/varianten/{id}/eans`; scans/search find any EAN. |
| 9 | Overview "Stock by main group" shows all items without a main group although some have one | Reported bug, not reproduced yet. The dev DB now holds the 2026-10-01 test-run data to try it — **Cause found 2026-10-01:** FEDAS codes with an unmapped sport area got no category at all although the product type (main group) was known — fixed with point 1 (dev DB here was empty, so not reproduced on the test-run data). |
| 10 | Hide Statistics and Pending when the selected location is GEWA, VEBO or Dietikon (also for mixed assignments) | Open. Confirmed by Fabian 2026-10-01: Dietikon is meant, hiding the pages is enough. Read rights unchanged (rule 9) — **Done 2026-10-01:** by `lagerorte.verkauf` of the selected location; pages redirect, bell and overview panel hidden. |

Next steps after approval: 9 (bug), 10 (small), 1–2 (categories), 3, 8, 6,
7 (needs the document), 4–5 (mail design and rule-1 decision).
