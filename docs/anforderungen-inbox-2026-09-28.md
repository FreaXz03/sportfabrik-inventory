# Inbox requirements from 2026-09-25 and 2026-09-28

Recorded in the project on 2026-09-28. Both lists come from Fabian's vault
inbox; the 2026-09-25 clarifications were so far only in the vault. Each
point states the **code status checked on 2026-09-28** and any conflict with
existing rules. Nothing here is implemented yet unless marked so; this file
does not decide open business questions.

## Status 2026-09-28, evening

Fabian decided all open points the same evening; implemented test-first
(details: `projekt-kontext.md`, "Decisions and implementation –
2026-09-28, evening"):

| # | Decision | Status |
|---|---|---|
| K1, K2 | — | **done**: removals per reason/person in statistics; opens on "this week" |
| K4, N1 | 30 % from arrival, 50 % after 18 months, 70 % after 36 months | **done** |
| K5 | "Automatic" instead of "Recommendation" | **done** |
| K6 | Own branches only, also branch managers; head office all | **done** |
| K8 | Employees book out sales — only sales | **done** |
| N2 | — | **open**: where to store a markdown chosen at goods entry |
| N3 | "Pending" per branch; head office sees all | **done** |
| N4 | Transfer as a delivery with dispatch date | **done** |
| Arrival timing | Confirm after unpacking and checking | working rule, texts updated |
| Password length | 6 is enough while only store Wi-Fi/VPN reach the server | decided |

The tables below keep the state found in the morning review.

## Clarifications from 2026-09-25

| # | Requirement | Code status 2026-09-28 | Conflict / open point |
|---|---|---|---|
| K1 | Statistics also show how many items were removed from stock, for which reason, the latest removals, and who booked them | **open** — `app/services/statistik.py` covers sales only | — |
| K2 | Statistics open directly on "this week"; other periods selectable afterwards | **open** — `statistiken.html` preselects "this month" | — |
| K3 | Statistics only for branch managers and head office | **done** (`require_chef_page`/`require_chef_api`) | — |
| K4 | New items start at 30 % right away; there is no item without a markdown | **open** — `app/services/reduktion.py` returns 0 % below 18 months | Changes rule 6 (thresholds 18 → 50 %, 36 → 70 %) and D-F2 ("new delivery jumps back to 0 %"). Needs the exact new rule: 30 % from arrival, 50 % from 18 months, 70 % from 36 months? |
| K5 | Don't write the word "recommendation" in the markdown display | **open** — `reduktion_wahl.*` texts still say "Recommendation" | Wording only; follows from K4 |
| K6 | Change markdowns only in the own branch, see other branches read-only; head office may change all | **partly** — employees: own branches only (done). Branch managers can currently change **all** branches (`list_wareneingang_lagerorte`) | Should branch managers be limited to their assigned branches for markdowns only, or also for other bookings? |
| K7 | Edit quick access via drag-and-drop | **done** (point 14, 2026-09-25) | — |
| K8 | Removals for all reasons except sale only for branch managers and head office | **stricter than requested** — all write-offs, including sales, are branch-manager/head-office only (rule 9, 2026-09-24) | Implies employees may book **sales**. Contradicts rule 9 in `CLAUDE.md`. Needs Fabian's decision before any change |

## Inbox from 2026-09-28

Original note in German, translated here; wording kept as close as possible.

| # | Requirement | Code status 2026-09-28 | Conflict / open point |
|---|---|---|---|
| N1 | "All items have a minimum markdown of 30 % — also new goods. There is no item without a markdown." | **open** | Same as K4 (confirms it) |
| N2 | "When entering goods, I want to choose directly which markdown the item has." | **open** — manual entry has no markdown field; the level can be set afterwards in item details or on "Markdowns" | Should the choice be stored as a manual markdown (`reduktionen_manuell`) for the target branch? Label printing would then use it |
| N3 | "Make 'Pending' on the overview separate per branch. Only the head-office account sees everything." | **partly** — deliveries, negative stock, and due markdowns already follow the active branch; "without EAN" and "without category" are item-master counts across all branches (rule 4: master shared) | Should item-master counts be restricted per branch (items with stock there) or hidden for non-head-office accounts? |
| N4 | "Treat a transfer like a delivery: when I transfer something, I choose the dispatch date, when I sent it where; the branch then gets it like a new delivery and confirms its arrival from there." | **open** — transfers are booked in one step (removal at source + receipt at destination, `app/services/umlagerung.py`) | Large change: goods "in transit" between dispatch and arrival, a new expected-receipt type, phone + desktop pages. Touches rule 6 (branch-to-branch transfer keeps the original date) and F11. Needs a short design decision first |

## Related open decision

- **Arrival confirmation timing** (discussed 2026-09-28): confirm "goods
  arrived" immediately on delivery, or only once goods are unpacked and
  priced? The system supports both; no rule decided. Relevant for N4 and
  for the markdown clock (rule 6 counts from the receipt date).

Status and next steps: [`projekt-kontext.md`](projekt-kontext.md), section
"Status check and next steps – 2026-09-28"; short version in
[`start.md`](start.md).
