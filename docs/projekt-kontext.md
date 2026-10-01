# Sportfabrik Inventory Management — Project Context, Vision & Target Picture

Entry point and current sources: [Short overview](start.md). Read only task-relevant sections.

## Binding priority – 2026-09-24

Fabian has decided: **First implement the new requests from the inbox, then continue Phase D.** The already-built markdown page stays in place; Phase D is neither reset nor marked complete by this.

Priority goes to the entire new requirements catalog "Item Details and Reports": tidy up item details, simplify lists and workflows, personalize the overview and quick access, add statistics and account management. The explicitly requested manual markdowns (all staff, per branch, 30/50/70%, selection via EAN or stock list, shown in item details and stock) also belong to this pulled-forward package, even though they technically touch Phase D.

Only after that come the remaining Phase D work and open decisions. Mobile phone use stays planned for the end of the project as agreed. Required checks before store deployment remain in place. This is a priority decision, not a confirmation of implementation.

**Status 2026-09-28:** this priority is fulfilled. The whole catalog (17 points) and Phase D (D-F1–D-F4) were implemented on 2026-09-24/25; mobile phone use was built early on 2026-09-28. Current open points and the next steps: section "Status check and next steps – 2026-09-28" at the end of this document.

Requirements catalog: [Item Details and Reports](anforderungen-artikeldetails-auswertungen-2026-09-24.md).


Status: 2026-09-24 (Rev. 6 from 2026-09-21: two external processing sites GEWA and VEBO plus external warehouse Dietikon, receipt date only starts at a branch; supplemented with the confirmed answers from 2026-09-22–24 in section 10) · **Authoritative target description** of the project. Actual technical state of the code: `README.md` and `docs/architektur.md`, `docs/datenmodell.md`.
Repo: github.com/FreaXz03/sportfabrik-inventory. Status 2026-09-28: `main` contains everything up to the UI redesign (PR #16, merged 2026-09-27) and its ultrareview fixes (PR #17, merged 2026-09-28). `feature/warenwirtschaft-v2` is ahead of `main` with the English documentation, HTTPS (S1), and the full phone feature set — pushed, no open PR yet. Full PR history: #8–#17, all merged.

---

## Addendum from 2026-09-23, evening

New business requirements: [Inbox requirements from 2026-09-23](anforderungen-inbox-2026-09-23.md). It covers the current supplier grouping (111/555/333/999/444), usability requirements, and the still-open conflict between fully deleting an item and permanently keeping the master record. The new grouping refines the older goods-source table below. Usability and good readability for staff who wear glasses or have little PC experience are central requirements. None of these additions is confirmed as implemented by this doc review.

## 1. Company & business model

| Point | Description |
|---|---|
| Company | **Sportfabrik** / Sport Fabrik AG (sportfabrik.ch) — discounter/outlet of **Intersport** (member no. 10166) |
| Size | **4 branches** in Switzerland (see below), founded **2005**. Head office Volketswil |
| IT scope | approx. **4–5 PCs** per branch → about 16–20 workstations total |
| Assortment | branded goods: clothing, shoes, hardware, bikes, skis, winter equipment, food, etc. |
| Pricing logic | sale **marked down from RRP** in steps of **‑30% / ‑50% / ‑70%**. New goods usually ‑30%; the longer in store, the more marked down |

### Branches & storage locations

| Code | Location | Address | Phone | Email |
|---|---|---|---|---|
| **SF1** | Volketswil *(head office, server location)* | Industriestrasse 21, 8604 Volketswil | 043 444 93 33 | volketswil@sportfabrik.ch |
| **SF2** | Conthey | Route Cantonale 7, 1964 Conthey | 027 322 75 83 | conthey@sportfabrik.ch |
| **SF3** | Regensdorf | Althardstrasse 10, 8105 Regensdorf | 044 840 05 90 | regensdorf@sportfabrik.ch |
| **SF4** | Hägendorf | Industriestrasse West 40/42, 4614 Hägendorf | 062 216 53 88 | haegendorf@sportfabrik.ch |
| **GEWA** | External processing *(no sale)* | GEWA-John Leuenberger, Grubenstrasse 22, 3322 Urtenen-Schönbühl | – | – |
| **VEBO** | External processing *(no sale)* | *address still to be added* | – | – |
| **DIETIKON** | External warehouse *(no sale)* | *address still to be added*, Dietikon | – | – |

**GEWA** and **VEBO** = two external **processing sites**, where goods are unpacked and prepared; they then go to a branch. Functionally equivalent — what applies to one applies to the other.

**Dietikon** = external **warehouse** with no processing; goods are only stored there temporarily.

→ In the system, all three are their own **storage locations without sale** (`verkauf = false`). Passing goods on to a branch = **transfer** (already part of the MVP for that reason). The system deliberately does **not** technically distinguish a processing site from a warehouse — for all rules, all that matters is that no sale happens there.

### Goods sources

| Source | Description | Documents (per examples) |
|---|---|---|
| **Intersport** | Direct delivery from Intersport Switzerland | PDF invoice, Intersport layout (parser exists) |
| **ECOM** | Returns from the Intersport online shop | **same Intersport invoice layout**, recognizable by the reference "SCH-SF ret.Ecom" / e.g. document no. "SF ECOM …" |
| **Third-party dealers / brands** | e.g. Alpina, Chris Sports (Giro), CMP/Campagnolo, Nike, adidas, Puma … | each supplier has its own layout; often **order confirmations**, sometimes scanned |
| **External dealers** | independent dealers/close-outs ("close out") | own layout, often **without EAN** |

## 2. Current state in store (problem)

- **POS (internal Intersport till system) entirely manual:** click category → type price → choose percentage → sell. No EAN search.
- **No inventory management system:** no item database, no stock levels, no price overview.

### POS categories (current structure, screenshot from 2026-09-20)

"Start sale" → **main group** → **sport area**. Textile, hardware, and footwear share the same 11 sport areas:

| Main group | Sport areas |
|---|---|
| Textile | Bike · Leisure · Tennis · Winter · Outdoor · Football · Kids · Swimming · Indoor · Running · Skating |
| Hardware | same 11 |
| Footwear | same 11 |
| Bike | *no subcategories* |
| Food | *no subcategories* |

→ **35 POS categories** in total (3 × 11 + Bike + Food). In the system, represented as **two fields**: `hauptgruppe` (main group) × `sportbereich` (sport area), empty for Bike/Food. This matches the till 1:1 and filters/reports well.

**Automatic category mapping via FEDAS:** Intersport invoices contain a 6-digit **FEDAS code** per line item (a European standard for sporting goods). From the examples: digit 1 = product type (1 = hardware, 2 = textile, 3 = footwear), digits 2–3 = sport (e.g. 24 tennis, 32 football, 60 bike, 64 outdoor, 75 leisure/lifestyle). → A mapping table FEDAS → POS category automatically suggests the category on import; only documents without a FEDAS code need it chosen by hand (once per item, then remembered).

## 3. End goal (vision)

> An **inventory management system for all 4 branches**, where every item is recorded on receipt (upload of a delivery note/invoice or manual entry), which **permanently stores every item ever recorded** with its price history, keeps **each branch's current stock**, supports branches in **marking down** — and is later connected to the **till**, so sold items are automatically booked out and the till only needs a scan.

## 4. Decisions (as of 2026-09-21)

| # | Topic | Decision |
|---|---|---|
| D1 | Item master | **Shared across all branches.** Only stock, goods receipts, and markdowns are branch-specific |
| D2 | Server | **One central server in Volketswil (SF1).** Network/VPN concept to be worked out together later |
| D3 | Workstations | approx. 4–5 PCs per branch |
| D4 | Till | Internal Intersport till system; categories see above (hardware confirmed). **Access/interface: Fabian to clarify with Intersport.** Connection later |
| D5 | Markdown | **Each branch decides for itself**, but there is a **central recommendation** so that, as far as possible, all branches mark down the same way. Rules see 8.3: receipt ‑30%, after **18 months** notice of ‑50%, after **36 months** ‑70% — calculated **per branch** from the **last goods receipt of the same item number at that branch**; a new delivery restarts the clock for **both** thresholds |
| D6 | Documents | Invoices, delivery notes, **and order confirmations** all occur; further examples will keep arriving. **Stock is only booked once the goods have arrived** |
| D7 | Purchase price | Save **optionally**, if present in the document — no priority |
| D8 | Rights (refined 2026-09-24) | Employees may manually book in and correct stock, but only in their assigned branches. Booking out sales/removals, cancelling, and transferring are reserved for branch managers and head office. Their existing cross-branch booking rights remain in place; read rights are unchanged. |
| D9 | **Document data stays local** | Invoices, delivery notes, and order confirmations are read **locally on our own server** by our own parsers — no handing off to third-party providers, no AI extraction. Outside of document processing, AI is allowed, including external services (refined 2026-09-22; before that, "no AI, no external services" applied to everything). For **building the parser**, Fabian may deliberately show individual documents (2026-09-22); in the finished system they continue to be read only by our own parser, later also without internet |
| D10 | EAN | EAN must be **addable later**. If one is never added, **the system generates an internal EAN** (including label) |
| D11 | External locations | Two processing sites (GEWA, VEBO) and one external warehouse (Dietikon) → each its own storage location without sale, goods are transferred from there to branches |
| D12 | Chris Sports | "Price" on their documents = **RRP** (discount 70% → purchase price = 30% of RRP) |
| D13 | Receipt date for external goods | Goods going to GEWA, VEBO, or the Dietikon warehouse get **no receipt date yet**. The date is set/added retroactively **once the goods have arrived at a branch (SF1–SF4)** — only from then does storage duration count |
| D14 | Label printer | **Sato CL4NX Plus** (industrial label printer), every PC on WiFi can print to it. Width 47 mm × height 83 mm (refined 2026-09-24, see section 10) |
| D15 | Scanner | Today only at the 2 till PCs. **Wireless scanners** will be acquired for goods receipt/adding EANs |
| D16 | Categories | Bike and Food have **no** subcategories; "hardware" confirmed |
| D17 | Branch-to-branch transfer | Goods **keep their original receipt date** (rebooking does not "reset the clock"). Only the path from an external location (GEWA/VEBO/Dietikon) into a branch sets the date for the first time (D13) |
| D18 | Line item without EAN on upload *(2026-09-21)* | **Let it through with a note** — the import is not blocked by this (rule 5). An EAN that is present in the document but unreadable, however, remains a blocking warning: that's a suspected read error, not a deliberately missing number |
| D19 | Storage location from the delivery address *(2026-09-21)* | The detected storage location is **only a suggestion** and stays editable on import |
| D20 | One document, one delivery address *(2026-09-21)* | A document has **one** delivery address, i.e. one goods receipt to one storage location. If the goods are later distributed to branches, that runs normally via a **goods transfer** — not via multiple storage locations on the same document |
| D21 | Confirming "goods arrived" *(2026-09-21)* | **Employees may also do this** — that's warehouse work, not a document right (rule 9) |
| D22 | Partial delivery *(2026-09-21)* | If less arrives than expected, the **remaining quantity stays open** ("expected"), so missing goods stay visible |
| D23 | Manual entry, required fields *(2026-09-21)* | **Brand + description + quantity + RRP** suffice. Everything else (supplier, category, color, size, EAN) is optional |
| D24 | Internal EAN *(2026-09-21)* | Generated **on demand** (when a label is needed), not automatically on import |
| D25 | Label content *(2026-09-21)* | **Year** (year of goods receipt), **supplier**, **RRP**, and the **markdown level** (30/50/70%). Whether the barcode should also be on the label is still open (see section 10) |
| D26 | Who can book to which storage location *(2026-09-21, confirmed)* | **Whoever may upload documents may book to any storage location** (own branch listed first). The document's delivery address determines the target, not the currently active branch — otherwise a delivery to another branch or to an external location couldn't be recorded at all. Branch switching stays limited to assigned branches; reading is allowed for all branches per the confirmation of 2026-09-22 |
| D27 | Goods without a document *(2026-09-21)* | Manual entry is a **direct goods receipt without a document** — no document and no document number is created. It is booked immediately to the chosen branch; everything stays traceable via the `lagerbewegungen` journal (who, when, how much) |

## 5. Requirements

### Must (MVP)

| # | Requirement | Details |
|---|---|---|
| Z1 | **Goods receipt via upload** | Upload invoice / delivery note / order confirmation → extract line items → check/correct → confirm |
| Z2 | **Manual goods receipt** | Record items without a document, quickly one after another, with an EAN scanner |
| Z3 | **Item master "forever"** | Every item ever recorded stays stored, even once sold out. Search by EAN, brand, item no., description, category |
| Z4 | **RRP price history** (+ optional purchase price) | RRP per item over time; look up the price of older items |
| Z5 | **Stock per branch** | Current stock per variant × branch, including receipt date (for storage duration) |
| Z6 | **Manual booking out** | Book out sales/removals by hand via scan (later automatically via the till) |
| Z7 | **Branches & storage locations** | SF1–SF4 plus GEWA, VEBO, and the Dietikon warehouse; separate stock/goods receipts, shared item master, branch switching, transfer external location → branch |
| Z8 | **Multilingual** | DE / EN / FR |
| Z9 | **POS categories** | Every item has a main group + sport area as at the till; suggestion via FEDAS |
| Z10 | **Markdown notices** | Overview/notification per branch per the rules in 8.3 (18/36 months) |
| Z11 | **Add/generate EAN** | Add an EAN any time via scan; otherwise generate an internal EAN and print a label |

### Already present and still wanted
Two-stage import with preview & correction, batch import, OCR for paper scans, item notes, Excel export, till-number login, light/dark mode, accessibility (large font/column selection), backups, Docker deployment.

### Later (backlog, continuously extended)
- [ ] **Till connection**: scan at the till supplies category, RRP, markdown; sale books out automatically
- [ ] Price tag printing with the marked-down price
- [ ] Transfers between branches (external location → branch is already MVP)
- [ ] Stocktaking (counting via scanner, booking differences)
- [ ] Reports: stock value, storage duration, sell-through by brand/category/branch, margin (if purchase price present)
- [ ] Finer-grained user rights
- [ ] *(further goals get added here)*

## 6. Analysis of the example documents (2026-09-20)

| Example | Document type | PDF type | EAN | RRP | Purchase price | Color/size | Notes |
|---|---|---|---|---|---|---|---|
| **Intersport** (invoice 9001759392, 21 pp., ECOM returns) | Invoice | Text | ✅ | ✅ | ✅ (price) | ✅ 2nd line "(color)/size" | FEDAS code, brand, supplier item no.; **existing parser** |
| **External dealer** (invoice 72586, Bollé close-out, Chippis) | Invoice (with delivery note no.) | Text | ❌ | ❌ | ✅ | ✅ under description | **Delivery address Conthey**, invoice addressed to Volketswil → derive branch from delivery address |
| **Alpina** (order conf. 160165) | Order confirmation | Text | ❌ | ✅ | ✅ gross + net | ✅ in description (e.g. "matte 52-56") | Delivery date per line item |
| **Chris Sports** (order conf. CS-12809663, Giro socks) | Order confirmation (liquidation) | Text | ✅ | ✅ ("price" = RRP) | ✅ amount | ✅ "color,size" per line | Variants grouped cleanly under the item |
| **CMP 2** (order conf. 2026A-F30-246) | Order confirmation | Text | ❌ | ✅ (sale price) | ✅ (purchase price) | ✅ **size matrix** (92–176) | Delivery to **GEWA** (external processing) |
| **CMP 1** (order 22065) | Order | **Scan (image)** | ❌ | ✅ (sale price) | ✅ (prices) | ✅ size matrix | Colored table, OCR text unusable |

### Findings & consequences

1. **Every supplier layout is different** — 6 examples, 6 layouts, more to come. Because of D9 (document data stays local) → **rule-based recognition, entirely local** (see 8.4):
   - **Supplier recognition** automatically via features in the document (VAT no., company name, GLN, table header).
   - **One parser per layout** as a plug-in; recurring patterns (table with header row, color/size on the following line, size matrix) as shared building blocks, so a new layout usually only needs a small configuration.
   - **Honest limitation:** a layout the system has never seen cannot be read automatically without AI. The process then is: document gets flagged as "unknown layout" → line items entered manually (header data pre-filled) → example sent to Fabian/development → parser extended. The more examples, the rarer this happens.
2. **Many documents have no EAN** (4 of 6), and not every physical item has a barcode either. → Variants must be able to exist **without an EAN** (key: supplier + item number + color + size). EAN can be **added any time via scan**; if an item never has one, **the system generates an internal EAN-13** (GS1 range 20–29 for internal numbers, with a check digit — never collides with real manufacturer EANs) and prints a label. That way, **every** item is eventually scannable at the till.
3. **RRP sometimes missing** (external dealer) → ask for it as a required field in the preview, otherwise no sale price can be calculated. An already-known RRP for the same item number is suggested.
4. **Order confirmation ≠ goods receipt.** → The document creates an **expected goods receipt**; only "goods arrived" (with quantity check) books the **stock increase** (D6).
5. **Storage location recognizable from the delivery address** (SF1–SF4 or one of the external locations GEWA/VEBO/Dietikon, addresses see above) → automatic pre-selection on upload, editable manually. Goods sent to an external location are later transferred to a branch.
6. **Size matrix** (CMP): one line = several sizes each with its own quantity → the parser must resolve this into individual variants.
7. **ECOM** needs no parser of its own: Intersport layout, source recognized via a reference field.

## 7. Target picture vs. current repo, reconciled

Snapshot from 2026-09-24: **Phase B complete**, **Phase C
complete** (C1–C5, 2026-09-23), plus the inbox requirements from
2026-09-23 (implemented 2026-09-24). Section 11 is authoritative for
the implementation status; this table only summarizes it against the
target picture.

| Area | In the repo today | Gap to the target |
|---|---|---|
| Upload & parsing | ✅ Intersport PDF, OCR (Tesseract, local), preview, correction, batch, **parser registry with supplier/document-type recognition** (B1), **storage location from the delivery address** (B4), **expected→arrived** (B5) | Only 1 layout registered so far (more in Phase E); no size matrix yet; OCR too weak for colored table scans |
| Manual entry | ✅ `/erfassen` page with scanner, no document (B6) — including category (B8) and label printing (B7) | — |
| Item master | ✅ `artikel` ↔ `varianten` as a real relationship, EAN optional (B3), internal EAN on demand (B7), POS categories with FEDAS suggestion and manual choice (B8), supplier groups with label code, manually entered items deletable (2026-09-24) | FEDAS table only partially confirmed (6 of 11 sport areas open) — chosen by hand until then |
| Prices | ✅ RRP and purchase price per goods-receipt line item (purchase price optional, rule 10), price history per variant, markdown level as a building block (`app/services/reduktion.py`, used on the label) | Markdown notices as their own view and the central recommendation are missing → Phase D |
| Stock | ✅ `lagerbewegungen` (append-only) + `bestand` per storage location; increases from import, confirmed arrival, and manual entry; **stock view** `/bestand` per storage location, readable by all branches (C2); **booking out via scan** `/ausbuchen` (C3); **transfer** `/umlagern` (C4); **corrections** via "count" in `/bestand` (C5) | Phase C complete. The migrated stock remains cumulative goods receipts until it's been counted and corrected |
| Branches | ✅ `lagerorte` (SF1–SF4 + GEWA, VEBO, Dietikon) + `benutzer_lagerorte` (m:n), branch switching in the UI; goods receipts, stock, and markdown calculation are branch-specific | Read rights clarified 2026-09-22 (section 10): employees and branch managers see documents and stock of **all** branches. All views (overview, documents, item details, stock, bookings-out) do this; branch switching stays limited to assigned branches (D26) |
| Language | ✅ i18n DE/FR/EN (catalog + per-user language choice, including backend error messages) | — |
| Roles | Employee / branch manager (`chef`) / central admin (`admin`) | Roles including admin and rights per rule 9 implemented (Phase A, point 1) |
| Deployment | Docker, 1 store server | Central server Volketswil, access from 4 branches |

## 8. Architecture proposals

### 8.1 Deployment
- One server in **Volketswil**, one PostgreSQL DB, separation via `filiale_id`.
- Other branches access it via **VPN** (e.g. WireGuard/Tailscale — to be set up together later). Not exposed unprotected to the internet.
- ⚠️ Login with just a till number is only acceptable inside the protected network → restrict access to VPN/store network.

### 8.2 Data model (proposal)

| Table | Purpose | Branch-specific? |
|---|---|---|
| `lagerorte` | SF1–SF4 (sale) + GEWA, VEBO, Dietikon (no sale), including address (for auto-detection) — **implemented** | – |
| `lieferanten` | Name, type (Intersport / ECOM / third-party dealer / external), parser mapping | no |
| `kategorien` | Main group × sport area (till structure) + FEDAS mapping | no |
| `artikel` | Model: brand, supplier, supplier item no., description, category, FEDAS | no |
| `varianten` | Color, size, **EAN (optional, unique if present)**, flag `ean_intern` for generated EANs | no |
| `preise` | History per variant: RRP, purchase price (optional), date, source | no |
| `dokumente` | Upload: type (invoice/delivery note/order confirmation/order), file, hash, supplier, detected branch | yes |
| `wareneingaenge` + `positionen` | Expected → received; quantity, RRP, purchase price, original snapshot | yes |
| `lagerbewegungen` | Journal: receipt, sale, write-off, correction, transfer — with quantity ±, reason, user, time | yes |
| `bestand` | Current stock per variant × branch + oldest receipt date | yes |
| `reduktionen` | Level per item × branch with valid-from; central **recommendation** separate | yes |
| `benutzer`, `benutzer_filialen` | Roles, branch assignment, language — **branch assignment implemented as `benutzer_lagerorte` (m:n)**, language follows in Phase A point 2 | partly |

Core principles: **Never overwrite stock — book it as a movement instead.** For the markdown rules, what counts is the date of the **last goods receipt of the same item number** (see 8.3).

### 8.3 Markdown logic (D5)

| Level | When | Reference date |
|---|---|---|
| ‑30% | on receipt (default) | – |
| ‑50% | notice after **18 months** | last goods receipt of the same **item number at that branch** — a new delivery restarts the clock |
| ‑70% | notice after **36 months** | last goods receipt of the same **item number at that branch** — a new delivery restarts the clock |

- "Item number" = supplier item number (model), i.e. across all colors/sizes.
- Calculated **per branch** (D5): a delivery to SF2 does not reset the clock at SF1.
- Goods without a receipt date (e.g. still at GEWA/VEBO or the Dietikon warehouse) generate **no** notices.
- A **branch-to-branch transfer** is not a goods receipt and does **not** restart the target branch's clock (confirmed 2026-09-22, see section 10). Only the path from an external location into a branch sets the date for the first time (D13).
- Head office (admin) sees the recommendations for all branches and can set a **uniform recommendation**; each branch adopts it or deliberately deviates (deviations visible).
- Notices as a "due for markdown" list + counter on the dashboard; thresholds (18/36 months) configurable.
- *Implemented state (2026-09-28):* −30 % applies automatically from arrival ("no item without a markdown"); thresholds are fixed (D-F4); changes only in one's own branches, head office all — see "Decisions and implementation – 2026-09-28, evening".

### 8.4 Document recognition without AI (D9)
- **Text PDFs** (5 of 6 examples): read word coordinates (PyMuPDF, as today) → layout parser.
- **Scans** (e.g. CMP order): local OCR with **Tesseract** (already in the project) + image preprocessing (grayscale, contrast, removing colored backgrounds) + table/line detection (OpenCV). Quality on colored tables is limited → the preview shows uncertain fields flagged for correction.
- **Supplier recognition** via features → matching parser; nothing recognized → "unknown layout" → manual entry.
- Everything runs on the server in Volketswil; no data leaves the company network.

### 8.5 Flow: external location → branch (D13)
Applies equally to the processing sites GEWA and VEBO and to the Dietikon warehouse. Rebookings happen spontaneously — so this is deliberately kept simple:

| Step | In the system | Receipt date (storage duration) |
|---|---|---|
| 1. Delivery to the external location | Goods receipt to storage location **GEWA**, **VEBO**, or **DIETIKON** (delivery address is recognized) | **empty** |
| 2. Processing or storage | Goods are visible under "External" (per location), but cannot be sold/booked out | empty |
| 3. Goods go to branch X | **Transfer → SFx**: select items/line items or the whole delivery | – |
| 4. Confirm arrival | Branch confirms arrival; date is suggested (today), can be entered **retroactively** — also as a bulk entry for several items | **set** → 18/36 months start counting from now |

In addition: a "**in transit / no receipt date**" list per branch, so nothing gets forgotten.

### 8.6 Hardware: labels & scanners
- **Labels:** the printer is a **Sato CL4NX Plus** (D14). The system generates labels as a **PDF in the matching label format** → printable from any PC via the normal printer driver, no special drivers needed. The CL4NX Plus additionally understands its own printer language (SBPL) and can emulate others — **direct printing** thus stays open as a later extension, but isn't needed for the start. Content per D25: year of goods receipt, supplier, RRP, markdown level. Two consequences: (1) because the **markdown level is on the label**, every markdown needs a new label — the "due for markdown" list (Phase D) should therefore lead directly to label printing. (2) because the **year** comes from the goods receipt, no label can yet be printed for goods at GEWA (D13: there's no receipt date there yet). Still open: label size and whether the barcode should also be on the label (section 10).
- **Scanners:** the web system works with any scanner in **keyboard mode (HID)** — no software needed. Recommendation for the wireless scanners: 1D/2D scanner with **USB wireless dongle or Bluetooth**, HID mode, reads **EAN-13 + Code 128**, ideally with **memory/batch mode** (scanning in the warehouse without wireless range). Test 1 device first, then 1–2 per branch.

### 8.7 Multilingualism
Translation files `de/en/fr`, language per user; item texts stay in the supplier's language.

### 8.8 What stays
FastAPI, PostgreSQL, Alembic, Docker, vanilla JS frontend, two-stage import with hash check, audit snapshot, advisory lock, tests, backups.

## 9. Roadmap

| Phase | Content | Result | Status 2026-09-28 |
|---|---|---|---|
| **A — Foundation** | Branches, roles (D8), branch switching, i18n scaffolding, new data model including categories, migration of existing data (→ SF1) | multi-branch and multilingual capable | done |
| **B — Goods receipt v2** | Document types, supplier recognition, expected→arrived, storage location from delivery address, manual entry with scanner, add/generate EAN + label, FEDAS category suggestion | every item enters the system | done |
| **C — Stock** | Stock movements, stock per storage location, transfer external location → branch, booking out via scan, corrections | current stock | done |
| **D — Prices & markdown** | RRP/purchase price history, markdown levels, central recommendation, 18-/36-month notices | markdown supported | done (2026-09-25); new requirements 2026-09-25/28 pending (minimum 30 %, see end of document) |
| **E — More suppliers** | Parsers for Alpina, Chris Sports, CMP (text + scan), external dealer; more as examples come in | upload for all known suppliers | partly: Alpina, Chris Sports, CMP (text); scans and further suppliers open |
| **F — Operations** | Server Volketswil, VPN, external backups, data migration; required points from the [security review](sicherheit.md): HTTPS, login rate-limiting, network separation, encrypted backups | all 4 branches in production | started: HTTPS and login lockout done locally; server, VPN, encrypted backups, S3–S8 open |
| **G — Till** | Connection to the Intersport till (depends on clarification with Intersport) | no more manual typing | waiting for Intersport |
| *(extra)* **Phone** | Phone web app for search, scan, count, receipt, transfer, write-off, entry, markdowns | staff work at the shelf | done (2026-09-28), remote access (VPN) open |
| *(proposed 2026-10-01)* **Operational reliability** | Cancel instead of delete, link documents to deliveries, stale-count check, retry protection, one-branch pilot with restore test, held stock/returns, price snapshots — see [roadmap](roadmap-operational-reliability-2026-10-01.md) | one branch reconciles a full day | proposal; Q1–Q9 answered 2026-10-01 |

## 10. Open questions

All questions from Rev. 2 and Rev. 3 are answered (D1–D27). Still open:

1. ~~**Label size** of the Sato CL4NX Plus~~ — answered on 2026-09-24: **47 mm wide × 83 mm high**, pre-printed rolls, implemented (see below).
2. ~~**Barcode on the label?**~~ — confirmed on 2026-09-24: **yes**, below the mountains (the roll is currently being redesigned for it).
3. **Till:** result of the clarification with Intersport (access/interface).
4. ~~**Manual booking-out outside the till:** the rule for negative stock still needs clarifying here.~~ — answered on 2026-09-22 (see below): warn, allow the booking anyway, same as at the till.
5. ~~**Open decisions of 2026-09-28**~~ — decided the same evening, see "Decisions and implementation – 2026-09-28, evening" at the end. N2 decided and implemented 2026-09-29 (see the section of that date at the end).

### Confirmed answers from 2026-09-22

Source: Fabian's direct answers, also recorded in the main vault under "Sportfabrik Inventory Decisions."

- **Read rights:** employees and branch managers may see documents and stock of all branches. Write rights are unchanged.
- **Negative stock:** allow with a warning in the till system; block in a later online shop. No general permission for other types of booking-out.
- **Transfer:** the receiving branch books the goods.
- **Over-delivery:** show a warning, still allow the booking. Implemented as Phase C, subtask C1.
- **Locations:** GEWA and VEBO process/unpack goods; Dietikon is a pure external warehouse without processing.
- **Label format:** Fabian to provide the details on 2026-09-23.
- **Till interface:** still no response from Intersport; Fabian will add news once available.

These answers are business decisions, not confirmation of newly implemented features.

### Confirmed answers from 2026-09-22 (second round, for Phase C)

- **Negative stock when booking out by hand:** same as at the till — the system **warns**, but books anyway. So stock may go negative; only the later online shop (F4) will block it. Background: the migrated stock is cumulative goods receipts with no sales, so differences are normal at first.
- **Branch-to-branch transfer and the markdown clock:** a transfer is **not** a goods receipt at the destination branch. Its clock keeps running unchanged there; the transferred goods get marked down along with the destination branch's existing level (D17: rebooking resets nothing). D13 stays unchanged: only the path from an external location (GEWA/VEBO/Dietikon) into a branch sets the receipt date for the first time and starts the clock.
- **Still open on this:** what applies if the destination branch has **never** had this supplier item number before? Then there's no date there for the clock to attach to.

- **Showing documents for parser development:** allowed. The goal remains a parser that later reads the files **without internet**; the documents are never published anywhere and are not read via AI in operation. This is the exception for development, not an automatic pathway — since the 2026-09-24 refinement, Graphify may also explicitly analyze selected project documentation; no automatic document analysis (see `docs/obsidian-graphify.md`).
- **Branch codes corrected:** SF1 Volketswil, **SF2 Conthey**, **SF3 Regensdorf**, **SF4 Hägendorf**. The previous assignment in docs, seed data, and tests was wrong (SF2 Regensdorf, SF3 Hägendorf, SF4 Conthey).

These answers are also business decisions; none of it is built yet (Phase C).

### Confirmed answers from 2026-09-23 (third round)

- **Reasons for booking out (F14):** as proposed — sale, breakage/defect, theft/shrinkage, own use, return to supplier, other with free text.
- **Scan when booking out (F15):** a scan immediately books out **one piece**. Multiple pieces = scan multiple times; there is no quantity prompt.
- **Transfer into a branch with no prior goods receipt (F11):** the clock there starts **from the goods' arrival** — the receipt date is then the day the destination branch books the receipt.
- **Label size (F1):** 84 × 47 mm on the Sato CL4NX Plus (84 × 38 mm was reported in the morning, corrected the same day). Fabian can provide a template of the current label.
- **Till interface (F2):** still no response from Intersport.
- **Learning FEDAS from practice (F8):** yes. There is no FEDAS list, and nobody knows if Sportfabrik has one. Categories chosen by hand should therefore be collected as suggestions for the mapping table — a code is only adopted after review, not automatically.
- **Corrections (C5), input:** what's counted is the **quantity on the shelf**; the system calculates the difference to stock itself and books it (a mini stocktake per line).
- **Corrections, reasons:** stocktake/count, wrongly booked, item found, other with free text.
- **Corrections, rights:** all roles (rule 9 — only documents are reserved for branch managers). *Refined on 2026-09-24:* employees only in their assigned branches.
- **Term "document" instead of "invoice" in the UI:** what gets uploaded is not just invoices, but also delivery notes and order confirmations. The umbrella term everywhere is "document" (FR "justificatif", EN "document"); "invoice" stays only where the document type is really meant.
- **Label size corrected:** 84 × 47 mm (not 84 × 38 mm).
- **Header area:** tidy up, make it more upscale and user-friendly. Implemented on 2026-09-23: one header row instead of two, navigation in groups (goods, documents) with an explanation per entry, branch pill and account menu on the right, menu button on narrow screens.
- **Temporary test button in stock:** a button per stock line that books out **one piece** (2 shirts → 1 shirt). The item stays in the master record, the booking is a normal line in `lagerbewegungen` (rule 2). Visible to all roles. Will be removed once booking out has been trialed in store.

### Confirmed answers from 2026-09-24

- **Label:** **47 mm wide, 83 mm high**; three pre-printed rolls (30% yellow, 50% red, 70% green) with logo, dot, and mountains. Only the RRP (struck through), supplier code, two-digit year, and the barcode below the mountains are printed; the roll is currently being redesigned for this (everything shifted up a bit). The UI states which roll to load. Implemented.
- **FEDAS mapping** (list from Fabian, local in the vault): all 54 experience areas mapped to the 11 sport areas. Fitness and combat sports → Indoor, golf and riding → Leisure, leisure/fashion winter → Outdoor. Whole bicycles → Bike, sports nutrition → Food. Kids not derivable (by hand). The list itself does not go into the repo. Implemented.
- **Supplier codes:** Alpina, CMP, Chris Sports, and Bollé are **999** — most of what comes in is 999.
- **Bollé invoice (FaGu):** only states the purchase price, no RRP → **no parser**, enter such goods by hand.
- **Alpina: all sizes of a model count together** (one item, also for the markdown clock).
- **Scanned delivery notes** (Alpina 119719, CMP reorder): enter **by hand** for now; a parser will follow once more examples exist.
- **Tests:** test first, then the feature; few large flow tests. Implemented (CLAUDE.md, "tests"). Sources: [Inbox additions from 2026-09-24](anforderungen-inbox-2026-09-24.md).


- **Deleting items:** needed mainly for wrongly **manually entered** items. Only branch managers and head office may delete, and only items **without a document**; then the item, stock, and bookings disappear entirely (a deliberate, logged exception to rules 2 and 4). Items from documents stay in the master record. Implemented, see section 11.
- The remaining inbox requirements from 2026-09-23 (supplier groups 111/555/333/999/444, usability, overview) are in [`anforderungen-inbox-2026-09-23.md`](anforderungen-inbox-2026-09-23.md).

### Further open product question

8. ~~**Learn FEDAS codes from practice?**~~ — answered 2026-09-23: yes, as a reviewed suggestion (see above). Implementation still open.

### Phase D — open questions (2026-09-24), answered and implemented on 2026-09-25

- **D-F1 "Done" for markdowns — decided: a list that must be confirmed.** New table `reduktionen_bestaetigt` (migration `e2f3a4b5c6d7`): the branch confirms a due model (`POST /api/reduktionen/bestaetigen`, same rights as manual markdown), it disappears from the due list until the next level becomes due (if the newly calculated level differs from the confirmed one, it reappears). "Soon" is unaffected. `app/services/reduktion_bestaetigung.py`, "Done" button on `/runterschreiben`.
- **D-F2 New delivery — decided: only the new pieces restart the clock, plus a notice.** Stock doesn't separate batches (only one `aeltestes_eingangsdatum` per variant × branch); a real separation would be a major data-model change. Implementation therefore deliberately lightweight: the automatic level still jumps back to 0% as before (rule 6 unchanged), but booking a delivery for a model that was already marked down creates a **notice** (new table `hinweise`, `app/services/hinweise.py`, hooked into `importer.py` and `wareneingang.py`/arrival confirmation) — visible on the overview ("notices" panel). The branch manually re-marks the old stock down to its previous level via the existing manual markdown, if needed.
- **D-F3 Central recommendation — decided: as proposed.** New table `reduktion_empfehlung_zentrale`: head office sets a level per model and branch effective from a date (`/empfehlungen`, head office only). The branch sees open recommendations on `/runterschreiben` and either adopts them (sets the same level by hand) or declines with a reason (`POST /api/empfehlungen/{id}/antwort`, same branch boundary as manual markdown). Head office sees all responses — deviations between branches become visible. `app/services/reduktion_empfehlung.py`.
- **D-F4 18/36-month thresholds — decided: fixed, the same for all branches, no configuration option needed.** Stay hardcoded as before (`app/services/reduktion.py`, `STUFEN`); no extra work needed.

Test-first: `tests/test_ablauf_reduktion.py` (confirming), `tests/test_ablauf_hinweise.py`, `tests/test_ablauf_empfehlung.py`. Checked in the browser (separately set-up SQLite instance): done button, notice panel, setting/adopting/declining recommendations, no console errors — no PostgreSQL run, no store deployment. Suite: 142 passed / 12 skipped.

### Security (review from 2026-09-24)

No critical or high findings; four medium and five low points are open, details and status in [`sicherheit.md`](sicherheit.md) (S1–S9). **S2 decided (2026-09-24):** lock out for 20 minutes after 5 wrong passwords — implemented. Not decided: minimum length of branch-manager passwords (10 instead of 6).

### Ongoing
- Keep collecting further example documents (esp. delivery notes, Nike/adidas/Puma, ECOM) → extend the parser list in section 6.
- FEDAS: fully mapped (2026-09-24); F8 (collect manually chosen categories as suggestions) is therefore barely needed anymore — only Kids remains manual work.
- Wireless scanner: get 1 test device.

## 11. Implementation status

| Phase | Status |
|---|---|
| Concept (D1–D27) | ✅ complete (D1–D17 on 2026-09-20, D18–D27 on 2026-09-21) |
| A — Foundation, point 1 (storage locations, roles, user↔storage location, branch switching) | ✅ complete, branch `feature/warenwirtschaft-v2` |
| A — Foundation, point 2 (i18n DE/FR/EN, per-user language choice) | ✅ complete, branch `feature/warenwirtschaft-v2` |
| A — Foundation, points 3–4 (new data model, migration of legacy data, live import, tests/docs) | ✅ complete, branch `feature/warenwirtschaft-v2` |
| B — Goods receipt v2: FEDAS category suggestion | ✅ suggestion and manual choice done (B8); only the not-yet-confirmed FEDAS codes remain open (see below) |
| B — Goods receipt v2, subtask 1 (parser registry, supplier and document-type recognition) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 2 (document number unique per supplier) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 3 (EAN really optional) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 4 (storage location from the delivery address) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 5 (expected → arrived) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 6 (manual entry with scanner) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 7 (internal EAN + label) | ✅ complete, branch `claude/next-step-l8tzqq` |
| B — Goods receipt v2, subtask 8 (choose category by hand) | ✅ complete, branch `claude/awesome-lamport-tivaj9` |
| C — Stock | ✅ complete: C1 (over-delivery warning), C2 (stock view), C3 (booking out via scan), C4 (transfer), and C5 (corrections), branch `feature/warenwirtschaft-v2` |
| Inbox requirements from 2026-09-23 | ✅ complete on 2026-09-24 (supplier group codes, stock columns, booking-out list, item search, overview, delete item), branch `feature/warenwirtschaft-v2`; open: parsers for the example documents, ECOM recognition, test cleanup |
| Booking rights (2026-09-24) | ✅ implemented: employees record and correct only in assigned branches; booking out, cancelling, transferring only branch manager/head office (`tests/test_rechte_lager.py`); not yet on the server |
| Work from 2026-09-24 | ✅ tests cleaned up (few flow tests), 47 × 83 mm label for pre-printed rolls, FEDAS fully mapped, ECOM recognition (555) and purchase-price storage, Alpina/Chris Sports/CMP parsers (Phase E partial), paper invoice INTERSPORT via OCR — see below |
| D — Prices & markdown | 🔶 Part 1 implemented (2026-09-24): "Markdown" page per branch with due/soon-due items and per-item label printing. Open: recording "done", central recommendation, configurable thresholds — questions to Fabian in section 10 |
| E–G | open (E partial: Alpina, Chris Sports, CMP done; scanned delivery notes open) |
| UI: consistent design system (all pages) | ✅ complete, branch `feature/warenwirtschaft-v2` |

**Phase B — goods receipt v2, split into subtasks** (from roadmap
section 9 and the open points of the code review; one subtask = one
commit, ordered by dependency):

| # | Subtask | Status |
|---|---|---|
| B1 | **Parser registry**: one module per supplier layout with a shared interface, automatic supplier and document-type recognition, clearly reporting an unknown layout | ✅ complete |
| B2 | Document number unique only **per supplier** (`UNIQUE (lieferant_id, dokumentnummer)`) including duplicate check in the importer — open point from the review, prerequisite for the second supplier | ✅ complete |
| B3 | **EAN really optional** (rule 5) also in the parser/corrections — prerequisite for manual entry and for suppliers without EAN (4 of 6 examples) | ✅ complete |
| B4 | Recognize **storage location from the delivery address** (SF1–SF4/GEWA, addresses in `lagerorte`) and **suggest** it on upload, editable (D19); one document = one storage location (D20) | ✅ complete |
| B5 | **Expected → arrived**: order confirmation/order create an *expected* goods receipt, only "goods arrived" (with quantity check) books stock (rule 3, D6). Employees may also confirm (D21), remaining quantities stay open (D22) | ✅ complete |
| B6 | **Manual entry** (Z2) with scanner, quickly one after another — also a path for unknown layouts (header data pre-filled). Only brand + description + quantity + RRP required (D23); without a document (D27) | ✅ complete |
| B7 | **Add/generate EAN**: internal EAN-13 in the GS1 range 20–29 with check digit (rule 5/D10), **on demand** (D24) + label as PDF for the Sato CL4NX Plus (D14/D25) | ✅ complete |
| B8 | **Choose category by hand** when the FEDAS code is missing or unknown (remembered permanently afterward) — remainder of the first subtask | ✅ complete |

That completes all eight subtasks of Phase B. Next phase per the
roadmap (section 9): **C — stock**. Within Phase B, one point stays
continuously open: the FEDAS codes not yet confirmed from real
invoices (`app/core/fedas.py`) — until then, these cases are chosen
by hand, which has been possible since B8.

**Phase C — stock, split into subtasks** (roadmap section 9;
the business answers for it are in section 10, ordered by
dependency and risk — one subtask = one commit):

| # | Subtask | Status |
|---|---|---|
| C1 | **Over-delivery warning**: more arrives than expected, the system warns and books anyway (confirmed 2026-09-22). Remainder of B5, small and settled — hence first | ✅ complete |
| C2 | **Stock view per storage location**: current stock per variant × storage location, readable by **all** branches (read rights 2026-09-22), with its own view of goods at an external location (without a receipt date). Until now no page showed stock — without it, nothing that follows can be checked | ✅ complete |
| C3 | **Booking out via scan** (Z6): book out a sale or removal by hand, `lagerbewegungen.typ = verkauf`/`ausbuchung` with reason and user. If stock isn't enough, the system **warns** and books anyway (2026-09-22). One scan = one piece (F15), reasons per F14 (2026-09-23) | ✅ complete |
| C4 | **Transfer**: external location → branch sets the receipt date for the first time (D13), branch → branch keeps it and does not restart the destination branch's clock (D17, 2026-09-22). Booked on receipt by the **receiving** branch (F5). If the destination branch never had the item number before, the clock starts on arrival (F11, 2026-09-23) | ✅ complete |
| C5 | **Corrections**: book a difference by hand (`typ = korrektur`) — only with a reason, so the journal stays traceable (rule 2). Especially needed at the start, because the migrated stock is cumulative goods receipts without sales. The counted quantity is entered, reasons and rights per 2026-09-23 | ✅ complete |

All five book through the same path as the receipt (`buche_zugang()`
or its counterpart) and the same database lock, so the paths don't
drift apart — just like import, arrival, and manual entry in Phase B.

**Details on Phase C, subtask C1 — over-delivery warning** (see
`docs/architektur.md`, section "Expected → arrived"):
- `bestaetige_ankunft()` still books the actual quantity and now also
  returns `mehrlieferungen`: for each affected line item, its id, the
  expected and the arrived quantity, and the difference. Quantities as
  text everywhere as usual (never `float`).
- The line item's **total so far** (`menge_eingetroffen`) is compared
  against the expected quantity, not the individual booking — otherwise
  an over-delivery would go unnoticed if it only arises through a later
  delivery.
- The `/wareneingaenge` page appends a warning sentence to the success
  message ("more arrived than expected for {count} line item(s)"), a
  new translation key in DE/FR/EN (rule 7). Nothing is blocked.
- Tests: three new cases in `tests/test_wareneingang_ankunft.py` (excess
  quantity booked and reported, an exact delivery reports nothing, an
  over-delivery only arises through the follow-up delivery). Full suite:
  421 tests passed (previously 418).

**Details on Phase C, subtask C2 — stock view** (see
`docs/architektur.md`, section "Viewing stock"):
- New `app/services/bestand.py` (read-only, rule 2), `app/routers/bestand.py`
  (`/bestand`, `/api/bestand`), page `app/templates/bestand.html` with
  `app/static/js/bestand.js`, "Stock" nav entry on all pages.
  Until now, **no** page showed stock — the item list even explicitly
  pointed out that its quantities were delivered, not on-hand, goods.
- One row is a **variant × storage location** with quantity and oldest
  receipt date; the same query returns the count and total quantity of
  the whole selection. Quantities as text, never as `float`.
- The active branch is pre-selected; **all** locations are selectable
  (read rights from 2026-09-22), plus "all branches and locations." The
  branch switch in the session bar stays unchanged, limited to assigned
  branches — it still decides where bookings go.
- Rows with quantity 0 are hidden (toggleable), a **negative** stock is
  always shown: it's been possible since 2026-09-22 and is exactly what
  someone needs to see.
- Goods at a no-sale location have no receipt date (rule 6/D13); the
  page writes the reason there instead of a blank dash.
- Search by brand, description, supplier item number, and EAN; loading
  more via `offset`, cap of 500 rows per query (store network).
- Tests: `tests/test_bestand.py` (16 cases: filter per storage location,
  external location without a date, sold-out and negative rows, search
  across four fields, paginated loading, API with the active and a
  foreign branch, unknown branch, rights without login). Full suite: 438
  tests passed (previously 421).
- Played through in the browser against a SQLite test database:
  pre-selection of the active branch, switching to "all branches and
  locations," search, negative stock, GEWA row with a note instead of a
  date. In the process, found and fixed: the first query sent
  `alle=true`, because the select list only knows the "all" entry before
  the first response — so everything was shown, even though the session
  bar displayed SF1. The page now remembers its own choice and leaves
  the first query to the server. A run against PostgreSQL is still
  pending.

**Details on Phase C, subtask C3 — booking out via scan** (see
`docs/architektur.md`, section "Booking out"):
- New `app/services/ausbuchung.py`, `app/routers/ausbuchung.py`
  (`/ausbuchen`, `/api/ausbuchen/stammdaten`, `/api/ausbuchen`,
  `/api/ausbuchen/{id}/storno`), page `app/templates/ausbuchen.html` with
  `app/static/js/ausbuchen.js`, "Book out" nav entry on all pages. No
  schema change: `lagerbewegungen` already knew `verkauf` and
  `ausbuchung`.
- **One scan = one piece** (F15): the scan books immediately, no
  quantity prompt. Fast scans are collected in the browser and booked in
  order.
- **Reasons** (F14): a sale is booked as `typ = verkauf`, breakage/defect,
  theft/shrinkage, own use, return, and other as `ausbuchung`; the
  reason is stored in `lagerbewegungen.grund`, for "other" with the free
  text (`sonstiges: …`, required, max 150 characters).
- **Insufficient stock** (F9): booked anyway, the response reports
  `bestand_reicht_nicht` and the page warns. If the stock row doesn't
  exist at all, it's created with a negative quantity and no receipt
  date. A removal never changes the receipt date.
- **Undo** instead of delete (rule 2): a counter-booking `typ = korrektur`
  with `grund = 'storno:<id>'`, at most once per booking-out.
- Booked under the same lock as receipts; which storage location may be
  booked is checked by the server (`resolve_wareneingang_lagerort`,
  pre-selecting the active branch). Booking out was initially open to all
  roles; *since 2026-09-24, only branch managers and head office*
  (booking rights, see below).
- **Temporary test button** (requested 2026-09-23): a "−1" per row in the
  stock view, books out one piece through the same path
  (`grund = 'test'`, not selectable on the booking-out page). Also works
  for variants without an EAN. Visible to all roles; removed once
  booking out has been trialed in store.
- Tests: `tests/test_ausbuchung.py` (24 cases: one piece per scan, reasons
  and type, required text for "other," unknown EAN/reason book nothing,
  variant without EAN, negative stock with warning, receipt date stays,
  stock = sum of movements, undo once and only for removals, API
  including rights). Full suite: 463 tests passed (previously 438).
- Played through in the browser against a SQLite test database: scan with
  enter, scan into negative with a warning, undo, "−1" in the stock view
  down into negative. A run against PostgreSQL is still pending.

**Details on Phase C, subtask C4 — transfer** (see
`docs/architektur.md`, section "Transferring"):
- New `app/services/umlagerung.py`, `app/routers/umlagerung.py`
  (`/umlagern`, `/api/umlagerung/stammdaten`, `/api/umlagerung`), page
  `app/templates/umlagern.html` with `app/static/js/umlagern.js`,
  "Transfer" nav entry. Migration `e1f2a3b4c5d6`:
  `lagerbewegungen.eingangsdatum`.
- **The receiving branch books on receipt** (F5): the active branch is
  pre-selected as the destination, the source is chosen. One booking
  handles both the removal and the receipt, entirely or not at all;
  there's no "in transit" state.
- Collect goods via scan (each scan +1) or via search in the source's
  stock — this also covers variants without an EAN (rule 5). Quantity
  per row editable.
- **Date rules**, all decided solely via `lagerorte.verkauf`:
  external location → branch sets the receipt date (retroactively on
  request) and starts the clock (D13) — even at a branch that already
  had the item, because it's a new delivery; branch → branch keeps the
  goods' date (D17) and leaves the destination's clock unchanged (F10),
  unless the destination never had the item — then it starts on arrival
  (F11, checked per item, not per variant); a no-sale destination gets no
  date (rule 6).
- `reduktion.letzter_wareneingang()` now also counts transfers with an
  `eingangsdatum` — so the label and later Phase D see the clock
  correctly.
- **Assumption:** if stock at the source isn't enough, it warns and
  books anyway (like F9 for booking out) — the goods have, after all,
  physically arrived, and the migrated stock is imprecise. Please flag if
  that should be different.
- Tests: `tests/test_umlagerung.py` (24 cases: all date rules including
  retroactive and future, F11 per item, journal lines, summing, stock
  shortfall, invalid line items book nothing, all-or-nothing, API
  including rights). Full suite: 488 tests passed (previously 463).
- Played through in the browser against a SQLite test database: GEWA →
  SF1 via scan (2 pieces) and via stock search (variant without EAN),
  stock checked afterward at both locations. A run against PostgreSQL is
  still pending; the migration's SQL was checked offline.

**Details on Phase C, subtask C5 — corrections** (see
`docs/architektur.md`, section "Correcting"):
- New `app/services/korrektur.py`, `app/routers/korrektur.py`
  (`/api/korrektur/gruende`, `/api/korrektur`). No dedicated page: every
  row in the stock view has a "Count" button that opens a small form
  below it. No schema change.
- **Counted quantity instead of a difference** (2026-09-23): the
  difference is only calculated under the lock — if something was sold
  between counting and booking, the current state counts. If stock
  already matches, no row is created. The booked row is
  `typ = korrektur`, `menge` = difference.
- **Reasons:** `inventur` (stocktake), `falsch_gebucht` (wrongly booked),
  `gefunden` (item found), `sonstiges: …` (other, free text required).
  **Rights:** all roles (rule 9); *since 2026-09-24* employees only in
  their assigned branches.
- A correction is not a goods receipt: the receipt date stays, even if a
  new stock row is created.
- Tests: `tests/test_korrektur.py` (19 cases: difference minus/plus,
  nothing booked at the same level, 0 counted, from negative stock, new
  stock row without a date, date stays, required text, invalid
  quantities, unknown reason/variant, API including rights). Full suite:
  507 tests passed (previously 488).
- Played through in the browser against a SQLite test database (4 → 1
  and 2 → 5, also using enter in the quantity field).

That completes **Phase C**. Still open are the run against
PostgreSQL and removing the "−1" test button once booking out has been
trialed in store.

**Details on the inbox requirements from 2026-09-23** (implemented on
2026-09-24; requirements and the deletion decision in
`docs/anforderungen-inbox-2026-09-23.md`):
- **Supplier groups and label codes:** group = `lieferanten.typ`
  (new `intern` for Nike, adidas, The North Face), code derived from it
  (`app/core/lieferanten.py`: Intersport 111, ECOM 555, dealer 333,
  third-party dealer 999, internal 444) and bold on the label. One
  supplier per group for manual entry. Migration `f2a3b4c5d6e7`.
  **Open:** ECOM returns arrive in the Intersport layout and are still
  assigned as Intersport (111) until the parser recognizes the "ret.Ecom"
  reference.
- **Stock:** color, size, and main group in their own columns; rows with
  quantity 0 no longer appear (toggle removed), the item stays in the
  master record.
- **Bookings-out as a list:** the "Book out" page shows all sales and
  removals from the journal with time, person, and reason, filterable
  per branch (`GET /api/ausbuchungen`).
- **Item search:** "scan EAN" (focused, scan + enter searches
  immediately) and "quick search" up front, remaining filters under
  "more filters," which also has "manually entered only."
- **Overview:** greeting, quick access, KPIs for the active branch,
  "pending" (deliveries, negative stock, markdown age −50/−70% including
  the next 30 days, items without category/EAN), "recent activity"
  (`app/services/uebersicht.py`, extended `GET /api/dashboard`). The
  markdown figures are an age-based **notice** — whether something has
  already been marked down is something the system only knows from
  Phase D.
- **Delete item:** `DELETE /api/articles/{id}` and a button on the item
  page, only branch manager/head office, only without a document
  (`app/services/artikel_loeschen.py`).
- Tests: `test_lieferantengruppen.py`, `test_uebersicht.py`,
  `test_artikel_loeschen.py`, additions in `test_bestand.py`,
  `test_ausbuchung.py`, `test_ean_etikett.py`, `test_manuelle_erfassung.py`.
  Full suite: 533 passed, 20 skipped (previously 507). Reviewed in the
  browser against a SQLite test database: overview, stock, booking out
  with the list, item search with scan. The delete button itself was
  only checked via the API tests (branch-manager login needs a
  password).

**Details on Phase A, point 1** (see `docs/datenmodell.md` for the tables in detail):
- New tables `lagerorte` (seed data) and `benutzer_lagerorte` (m:n, with `ist_primaer`) via Alembic migration `a1b2c3d4e5f6`; existing users assigned to SF1. Migration `b8c9d0e1f2a3` adds VEBO and the Dietikon warehouse (Rev. 6), bringing the total to seven storage locations: SF1–SF4 with sale, GEWA/VEBO/DIETIKON without.
- `users.role` extended with `admin` (roles: `mitarbeiter` = employee, `chef` = branch manager, `admin` = head office), rights per rule 9 implemented in `app/routers/auth.py` and `app/routers/article_details.py`.
- Branch switching in the UI: `/api/me` returns the active branch + selectable branches, `POST /api/active-lagerort` switches it (admin additionally gets "all branches"); UI selector in the session bar (`app/static/js/session.js`).
- `scripts/manage_users.py` extended with branch assignment (`add-mitarbeiter`/`add-chef <till-number> <name> <storage-location-codes...>`) and `add-admin`.
- Stock/goods receipts/markdowns are not yet branch-specific — that comes with the new data model in Phase A point 3 and Phases B–D.

**Details on Phase A, point 2** (see `docs/architektur.md`, section "Multilingualism (i18n)"):
- `users.language` (DE/FR/EN, default `de`) via Alembic migration `b2c3d4e5f6a7`.
- Catalog as the single source: `app/static/i18n/{de,fr,en}.json` (330 keys), read by the backend (`app/core/i18n.py`, `translate()`) and frontend (`app/static/js/i18n.js`, `data-i18n` attributes + `window.SportfabrikI18n.t()`).
- Language detection per request: logged in, the account language; anonymous (`/login`), the `Accept-Language` header (`app/routers/auth.py`, `get_language`/`get_language_optional`).
- All existing templates (`login.html`, `dashboard.html`, `preview.html`, `articles.html`, `history.html`) and JS files switched to keys; **all** `HTTPException` error messages in the backend (router **and** services: `parser.py`, `ocr.py`, `corrections.py`, `importer.py`) go through `translate()`.
- Language choice: `POST /api/language` (account), DE/FR/EN switcher in the session bar and on the login page (`localStorage` before login).
- Deliberately not translated: item data from supplier documents (rule 7), fixed German text anchors in the INTERSPORT layout (the parser always looks for "Rechnungsdatum" in the PDF, for example), Excel export column headers (its own document format, open point).
- Tests: `tests/test_i18n.py` (catalog/`translate()`, language detection, `/api/language`); full suite now 108 tests passed (previously 86).

**Details on Phase A, points 3–4** (see `docs/datenmodell.md` for the tables in detail):
- New data model per section 8.2 fully implemented: `lieferanten`, `kategorien` (35 POS categories), `artikel`, `varianten`, `preise`, `dokumente`, `wareneingaenge`, `wareneingang_positionen` (+`_quelle`), `lagerbewegungen`, `bestand` via Alembic migration `c3d4e5f6a7b8`. Stock is now kept append-only via `lagerbewegungen` (rule 2), no longer implicitly via `invoice_items`.
- Existing data (`products`/`invoices`/`invoice_items`/`invoice_item_sources`/`article_notes`) fully and losslessly migrated (old tables stay untouched, "never discard") — the one deliberate gap: the former INTERSPORT-specific item number (`products.article_no`) is not carried over; only the supplier item number remains the item key (rule 5), the old value stays viewable in `products`.
- **Live import switched over**: `app/services/importer.py` now writes newly imported invoices directly into the new schema (item grouping, variants with/without EAN, prices, stock movements, stock); goods receipts are now booked against the uploading account's **active branch** (`require_active_lagerort` in `app/routers/auth.py`) instead of fixed to SF1. `delete_invoice()` cleans up stock movements/stock/prices consistently.
- `app/services/parser.py` now also captures the FEDAS code per line item (`artikel.fedas_code`) — the automatic category-suggestion logic built on it is part of Phase B (see below).
- `app/services/article_groups.py` uses the real foreign-key relationship (`varianten.artikel_id`) instead of a runtime query over brand + supplier item number.
- All affected routers (`catalog.py`, `history.py`, `article_details.py`, `dashboard.py`) as well as `article_export.py` switched to the new schema. The former separate "item no." column (the INTERSPORT-specific number) has been removed from item search, Excel export, and filters (see above); `/api/articles` now filters via `supplier_article_no` instead of `article_no`.
- Tests fully adapted to the new schema (including `test_importer.py`, `test_catalog.py`, `test_history.py`, `test_article_details.py`, `test_article_export.py`, `test_corrections.py`); the migration was additionally verified against real PostgreSQL (empty DB, DB with representative legacy data, downgrade/upgrade round trip), and the complete live-import and router path was smoke-tested against PostgreSQL.
- Known limitation: `bestand` after the migration equals the cumulative historical goods receipts (the old system knew nothing of sales/bookings-out) — not an exact physical stock count until Phase C (manual booking-out) or a stocktake corrects it.

**Details on Phase B, FEDAS category suggestion** (first subtask, see roadmap section 9):
- `app/core/fedas.py`: fixed mapping of the 1st FEDAS digit → main group (`1`=hardware, `2`=textile, `3`=footwear) and digits 2–3 → sport area, currently only the codes confirmed from real invoices (`24`=tennis, `32`=football, `60`=bike, `64`=outdoor, `75`=leisure — 6 of 11 sport areas are still missing: winter, kids, swimming, indoor, running, skating, as are the product-type digit(s) for the main groups bike/food themselves).
- `app/services/importer.py` sets `artikel.kategorie_id` automatically as soon as an invoice line item carries a known FEDAS code — both when creating a new item and when filling in a gap on an existing one (even if the variant was found via its EAN, which is the normal case for the migrated legacy items); if the code isn't mapped (yet), `kategorie_id` stays empty. A value that's already set is never overwritten by later invoices ("once per item, then remembered"); if it's still missing, it gets filled in later once an invoice with a known code arrives.
- ~~Deliberately not yet built: a UI for manually choosing a category~~ — done with subtask B8 (see below): if the suggestion is missing or doesn't apply, the category is chosen by hand on the item page or during entry, and becomes binding afterward.
- Tests: `tests/test_fedas.py` (pure mapping logic), `tests/test_importer_fedas.py` (interaction with the import: new item, unknown/missing code, filling in later, never overwriting) — additionally verified via a smoke test against real PostgreSQL.

**Details on Phase B, subtask B1 — parser registry with supplier and
document-type recognition** (see `docs/architektur.md`, section "PDF
parsing: one module per supplier layout"):
- `app/services/parser.py` became the package `app/services/parsers/`:
  `base.py` (shared building blocks — read the PDF **once** including
  per-page OCR fallback, group word coordinates into lines, parse
  numbers in Swiss notation), `intersport.py` (the previous layout as the
  first plug-in), and `__init__.py` as the registry. Interface per layout
  module: `KEY` (= `lieferanten.parser_key`), `LIEFERANT_NAME`,
  `detect()`, `parse()`, `dates()`. A further layout (Phase E) thus only
  needs a new module and an entry in `PARSERS`.
- **Supplier recognition** via features in the document instead of
  hardcoded: each module scores the document, the highest score wins.
  For the INTERSPORT layout, the line-item table with its header row is
  the required feature (on a scan, the company logo isn't always
  readable as text, but the table is); company name and invoice number
  only add to the score. On a tie, recognition aborts with a clear
  message instead of guessing a supplier.
- **Unknown layout** is now reported by the upload as such ("This
  document layout isn't known to the system yet … please pass it on as
  an example," HTTP 422) instead of "table header missing on page 1" —
  exactly the flow from section 6, point 1. If, instead, a single page
  of a *recognized* layout deviates, the previous, more specific message
  still applies.
- **Document type** (D6) comes from the document: `dokumente.typ` is no
  longer hardcoded as `rechnung` (invoice) but taken from the parser
  result; without a recognized type, nothing is booked. The INTERSPORT
  layout has so far only occurred as an invoice (anchor "Rechnung Nr.").
  `wareneingaenge.status` therefore still always stays `eingetroffen`
  (arrived) — the "expected → arrived" path is subtask B5.
- The **supplier** is looked up via the recognized `parser_key` (previously
  the constant `INTERSPORT_PARSER_KEY` in the importer).
- `invoice_dates()` moved into the INTERSPORT module as `dates()`: the
  German text anchors ("Rechnungsdatum"/"Belegdatum") belong to the
  layout, not to the import.
- **Only one read pass now:** recognition, line items, and invoice/
  document date all work on the same already-read document. Previously,
  the import opened the file a second time for the date fields and ran a
  scan through text recognition twice (noticeable on a 21-page invoice).
- The preview shows the recognized supplier and document type above the
  line-item table; `/upload-preview` and `/validate-preview` now supply
  `parser_key`, `supplier_name`, and `document_type` for this (see
  `docs/api-referenz.md`). New translation keys in DE/FR/EN, no
  hardcoded text (rule 7).
- Tests: `tests/test_parser_registry.py` (interface contract of every
  registered module, `parser_key` ↔ supplier seed, recognition with/
  without company name, score tie, translated message in DE/FR/EN, only
  one read pass) and `tests/test_import_end_to_end.py` (the complete
  path PDF → recognition → line items → database with a self-built mini
  invoice, so it runs **without** `INTERSPORT_TEST_PDF` — a gap the
  previous import tests had, since they replaced the parser with a
  stub). `tests/test_parser.py` is now called
  `tests/test_parser_intersport.py`. Full suite: 166 tests passed
  (previously 145); additionally run against real PostgreSQL 16 (import
  with categories/stock, duplicate, GEWA rule without a receipt date,
  unknown layout, deletion).

**Details on Phase B, subtask B2 — document number unique only per
supplier**
(migration `e5f6a7b8c9d0`, see also `docs/datenmodell.md`, `dokumente`):
- Document numbers are a supplier matter and can freely overlap. Before,
  `dokumente.dokumentnummer` was **globally** unique — a new supplier's
  invoice would have been rejected as a duplicate just because
  INTERSPORT had already used the same number. Now
  `UNIQUE (lieferant_id, dokumentnummer)` applies.
- **Two** objects had to be removed, because migration `c3d4e5f6a7b8`
  had created both: the column uniqueness (in PostgreSQL as the
  constraint `dokumente_dokumentnummer_key`) plus a separate UNIQUE
  index. The index on the number stays, just no longer unique.
- `datei_hash` (file hash) stays globally unique: the same file is the
  same document, regardless of who it's from.
- The importer now looks up the supplier **before** the duplicate check
  and compares the file hash (global) or the document number for the
  same supplier. The understandable message still comes from the
  importer; the database constraint is the fallback for two simultaneous
  imports.
- `GET /invoice-import-status` (batch queue) now also takes `parser_key`:
  the document number alone no longer says anything — without a
  supplier, only the file hash counts. The queue in the browser sends
  the value along and also compares it for duplicates within its own
  selection.
- Tests: two suppliers with the same number (via a second layout
  registered only for the test), the same supplier with the same number
  from a different file, the database constraint itself, the status
  query with and without a supplier, and the queue in the node test.
  Full suite: 170 tests passed.
- Checked against real PostgreSQL 16: migration on an empty and on a
  populated database, downgrade/upgrade round trip with data, behavior
  of both constraints, complete import path with two suppliers. `alembic
  revision --autogenerate` no longer shows any drift between the model
  and the schema for `dokumente`. Noticed in passing (not changed,
  affects a different table): `varianten.ean` has, for the same reason,
  duplicated uniqueness as well (constraint `varianten_ean_key` **and**
  UNIQUE index `ix_varianten_ean`) — harmless functionally, but
  unnecessary.
- `downgrade` deliberately fails as soon as two suppliers use the same
  number: then there's no longer a globally unique number.

**Details on Phase B, subtask B4 — storage location from the delivery
address**
(D19/D20, see `docs/architektur.md`, section "Storage location from the
delivery address"):
- Until now, every import booked against the account's active branch,
  even though the document states where the goods went — for the
  external dealer, the invoice goes to Volketswil but the goods go to
  Conthey; CMP delivers to GEWA.
- New module `app/services/lieferadresse.py`: recognizes the storage
  location from the document text. Pure text logic with no database and
  no layout knowledge, so it works the same for every supplier. Scored
  features (postal code 3, place name 2, own name like "GEWA" 2, street
  1), a minimum score, and umlaut tolerance ("Hägendorf"/"Haegendorf").
- Two passes: first around a delivery-address anchor ("Lieferadresse,"
  "Lieferung an," "Warenempfänger," "Ship to," …), otherwise across the
  whole text. **On a tie, there is no suggestion** — if the invoice and
  delivery addresses appear equally in the text, any choice would be a
  guess; then it stays at the active branch.
- D19 in the UI: the preview shows "book goods receipt to" as a
  selection, pre-filled with the suggestion, next to the reasoning
  ("recognized from the delivery address: SF2 · Conthey") or a note that
  nothing was recognized. `/import-invoice` accepts the chosen storage
  location and checks it server-side; without one, everything stays as
  before.
- **All** storage locations are bookable (own branch listed first).
  Otherwise a delivery to another branch or to GEWA couldn't be recorded
  at all — D19 would be pointless for exactly the cases it was meant
  for. Whoever gets here is allowed to upload documents anyway (rule 9);
  a wrongly chosen branch can be corrected via a transfer. **Confirmed
  by Fabian** (2026-09-21) and recorded as D26. Branch switching stays
  unchanged, limited to assigned branches; per the confirmation of
  2026-09-22 (section 10), employees and branch managers may read all
  branches.
- Tests: `tests/test_lieferadresse.py` (24 tests: every seed address,
  delivery address beats invoice address, tie with no suggestion,
  spelling variants, "Lieferschein" is not an anchor) and
  `tests/test_wareneingang_lagerort.py` (7 tests through the real app
  **with login**, i.e. including the rights path). Full suite: 213 tests
  passed (previously 182).
- Played through against real PostgreSQL 16 in the browser: login,
  uploading an invoice with delivery address Conthey, pre-selection SF2
  with reasoning, full selection list.

**Details on Phase B, subtask B5 — expected → arrived** (rule 3, D6,
D21, D22; see `docs/architektur.md`, section "Expected → arrived"):
- The import now distinguishes by document type: **invoice/delivery
  note** accompany the goods and book immediately, **order
  confirmation/order** create a goods receipt with status `erwartet`
  (expected) — no stock movement, no stock, no receipt date. Items,
  variants, and prices are still created, so announced goods are
  findable in the master record.
- Migration `f6a7b8c9d0e1`: `wareneingang_positionen.menge_eingetroffen`.
  `menge` is the quantity per the document, the new column is what has
  arrived of it, the difference is the remaining open quantity. Legacy
  data is backfilled (all previous goods receipts came from invoices).
- Partial delivery (D22): what arrives is booked; the rest stays open and
  the goods receipt stays `erwartet`. A follow-up delivery is simply
  confirmed again. Only once no line item is open anymore does the
  status change.
- Receipt date: set on the first receipt, enterable retroactively (D13);
  not set at all in a no-sale warehouse (GEWA) (rule 6).
- `varianten.first_seen`/`last_seen` ("first/last delivery") now only
  count goods that have **arrived** — an announcement is not a delivery.
  This also applies when recalculating after deleting a document.
- Import and arrival book through the **same** function (`buche_zugang`)
  and take the same database lock — both paths are thereby guaranteed
  to do the same thing.
- New page `/wareneingaenge` ("deliveries" in the nav): open deliveries
  for the active branch, per line item expected / already here / open, a
  field for the now-arrived quantity and a receipt date. Also usable by
  **employees** (D21). Translations DE/FR/EN.
- Tests: `tests/test_wareneingang_ankunft.py` (18 tests, including no
  stock before arrival, full and partial delivery, follow-up delivery
  closes it, GEWA without a receipt date, implausible quantities, a
  foreign line item, the complete path via the API as a logged-in
  employee). Full suite: 232 tests passed (previously 213).
- Checked against real PostgreSQL 16: migration on a database with
  legacy data (`menge_eingetroffen` correctly backfilled) and the whole
  flow in the browser as an employee — partial delivery, visible
  remaining quantity, completion.
- **Not yet reachable in daily use:** an order confirmation can't be
  uploaded yet, because the parser registry only knows the
  INTERSPORT invoice layout (more layouts: Phase E). So this path only
  becomes fully usable with the next parsers or with manual entry (B6).
- ~~**Left open:** if *more* arrives than ordered, the system books it
  (stock = what's physically there). Confirmed 2026-09-22: also warn,
  still allow the booking; the warning is still to be implemented.~~ —
  done with Phase C, subtask C1 (see below).

**Details on Phase B, subtask B6 — manual entry with scanner**
(D23, D27, rules 3/5/6/9/10; see `docs/architektur.md`, section
"Entering goods by hand"):
- Second path by which goods enter the system: no PDF, no parser
  (`app/services/manuelle_erfassung.py`, page `/erfassen`, nav
  "Enter"). Intended for goods without a document **and** for suppliers
  whose layout no parser knows yet — the path that makes B5 and the
  registry usable in daily practice at all, as long as only one layout
  is recognized.
- Migration `a7b8c9d0e1f2`: `wareneingaenge.dokument_id` and
  `artikel.lieferant_id` may stay empty. Goods without a document are a
  direct goods receipt **without a document** (D27), an item needs no
  supplier (D23). Existing data stays untouched.
- Only **brand, description, quantity, and RRP** are required (D23).
  EAN, color, size, unit, supplier item number, purchase price, and
  supplier are optional (rules 5 and 10).
- Booked immediately (rule 3 — only what's physically in hand gets
  manually entered), through the **same** `buche_zugang()` and the same
  database lock as import and arrival confirmation. One call = one
  goods receipt with all line items, in one transaction: all or nothing.
- New module `app/services/artikel.py`: the item and variant rules
  (rules 4/5) now live in **one** place and are used jointly by import
  and manual entry — otherwise the two paths would eventually have
  drifted apart. The same applies to the EAN format, which the preview
  now fetches from there.
- Receipt date: today or retroactive (D13); a no-sale warehouse (GEWA)
  gets none (rule 6), the date field then also disappears from the UI.
- The UI is tailored to the scanner: scan a barcode → a known EAN fills
  the form (brand, description, color, size, unit, last RRP/purchase
  price) → type the quantity → enter adds the line item to a list →
  next item. One button at the end books everything. An unknown EAN is
  accepted, and it also works without an EAN.
- **Rights:** **employees** may also enter goods (rule 9/D21) — no
  document is created, so the document right doesn't apply. The
  destination storage location goes through the same server-side check
  as import (D26): the active branch is pre-selected, all storage
  locations are bookable. Confirmed in the browser: the employee sees
  "Enter" but still no "Upload invoice."
- Audit like on import: a per-line-item unchanged snapshot of the input
  in `wareneingang_positionen_quelle` (with user and time); the stock
  movement carries the reason `manuelle-erfassung` (a fixed key, not UI
  text).
- Tests: `tests/test_manuelle_erfassung.py` (55 tests: required fields,
  comma as decimal separator, one wrong line item books nothing,
  variants with and without EAN, stock per branch, GEWA without a
  receipt date, retroactive and future date, supplier optional, EAN
  lookup, the complete path via the API as a logged-in employee). Full
  suite: 288 tests passed (previously 232).
- Checked against real PostgreSQL 16: migration forward and back and in
  offline mode (`--sql`), entry at SF1/SF2/GEWA including stock, stock
  movements, price history, and source snapshot. Then the whole flow in
  the browser as an employee, also in French.
- Side issue fixed: the `/wareneingaenge` page attached its i18n
  listener to `window`, but the event fires on `document` — a language
  switch left the texts generated by the script (column headers,
  messages) unchanged. Both pages now wait for the finished catalog and
  redraw on every language switch.
- ~~**Left open:** category (B8) and internal EAN with label (B7) are
  still missing here too~~ — done: B7 generates the internal EAN and
  prints the label right after entry, B8 adds the POS category as an
  optional field per line item.

**Details on Phase B, subtask B7 — internal EAN and label** (rules 5/6,
D10, D14, D24, D25; see `docs/architektur.md`, section "Internal EAN and
label"):
- `app/services/ean.py`: GS1 check digit, strict validation of manually
  added EANs, and the **internal EAN-13** following the pattern `20` +
  ten-digit variant id + check digit. No counter needed, always the same
  number for the same variant, `varianten.ean_intern` flags them. An
  existing EAN is **never** overwritten (rule 4).
- Deliberate difference from import: there it stays at the format check
  (B3), because the number is as printed on the supplier document.
  Whoever enters one here by hand also gets the check digit validated —
  otherwise a transposed digit would stay in the item master forever.
- `app/services/barcode.py`: EAN-13/EAN-8 as a bar pattern, computed
  in-house (no extra library, rule 1). UPC-12 is printed as an EAN-13
  with a leading zero; an EAN-14 (outer carton, actually ITF-14) or a
  wrong check digit deliberately produces **no** barcode, just the
  number — better none than one the till won't accept.
- `app/services/etikett.py`: label as a PDF in label size (one page per
  label, `anzahl` repeats it), drawn with PyMuPDF and the fonts embedded
  in the PDF. On it: year, supplier, RRP, markdown level (D25), plus
  brand, description, color/size, and barcode.
- `app/services/reduktion.py`: rule 6 as its own, tested building block —
  last goods receipt of the same item number **at this branch**, from
  which full months and the level are derived (18 → 50%, 36 → 70%). The
  notices for branches (Phase D) build on this. The 30% from D25 is a
  store decision and can be passed along when printing.
- UI in two places: on the **item page**, an "EAN & label" section (view,
  generate, add EAN, open the label with size/markdown/count) and,
  right after **manual entry**, a "print labels" button for the whole
  goods receipt, one label per piece. Both also for **employees** (rule
  9). Translations DE/FR/EN.
- **Assumptions while two questions stay open:** label size configurable
  (`GROESSEN`), the default was 50 × 30 mm back then — since 2026-09-23
  it's 84 × 47 mm, the confirmed roll size; the barcode is on it (see
  section 10, question 2). Both are changeable in one place.
- No schema change needed: `varianten.ean`/`ean_intern` already existed,
  they're now used.
- Tests: `tests/test_ean_etikett.py` (72 tests: check digits of real
  EANs, internal numbers, bar patterns against the standard including a
  self-test of the code tables, markdown levels at the cutoff dates,
  label data from the database, PDF size and content, setting an EAN
  including conflicts, and the complete path via the API). Full suite:
  360 tests passed (previously 288).
- Checked against real PostgreSQL 16 and played through in the browser:
  generating an internal EAN, an EAN with a wrong check digit rejected,
  label PDF (50 × 30 and 100 × 50 mm) viewed, labels printed for a goods
  receipt, DE/FR/EN language switch.

**Details on Phase B, subtask B3 — EAN really optional** (decision D18,
see `docs/architektur.md`, section "PDF parsing" → "Warning or note?"):
- Rule 5 applied in the data model and the importer, but **not** in the
  parser and the corrections: there, the EAN was a required field. In 4
  of 6 example documents, no item has an EAN — the upload would have
  been blocked from the start for these suppliers.
- Every line item now has two separate lists: `warnings` (blocks the
  import) and `hints` (passes through). The result counts both
  (`rows_with_warnings`, `rows_with_hints`).
- No EAN → a note. An EAN that's present in the document but has an
  invalid format → still a blocking warning. Same in the corrections:
  deleting the EAN is allowed (produces the note), entering nonsense
  stays an error. Color and size were already optional before.
- The preview shows notes, muted, below the warnings for the same line
  item, and as its own metric "line items with notes" (not colored as a
  warning). New translation keys in DE/FR/EN.
- Variants without an EAN are merged via supplier + item number + color
  + size (rule 5) — the importer could already do this, now it actually
  receives something there too.
- Tests: `tests/test_ean_optional.py` (12 tests from the parser through
  server-side revalidation to the database: note instead of warning,
  unreadable EAN blocked, deleting/adding an EAN, the same combination
  twice = one variant, a different size = two variants). Full suite: 182
  tests passed (previously 170).
- Checked against real PostgreSQL 16: several variants with an empty EAN
  coexist (NULL doesn't collide in the unique index), stock is booked
  per variant. The item list and Excel export show an empty EAN as "—"
  or as a blank cell.
- Still open (subtask B7): generating an internal EAN-13 and printing a
  label, so items without a manufacturer barcode also become scannable
  at the till. `varianten.ean_intern` is prepared for this but never yet
  set.

**Code review after Phase A** (2026-09-21, branch `feature/warenwirtschaft-v2`) — full
review of the existing code for bugs; fixed and each backed by real PostgreSQL runs or
new tests:
- **Migration `c3d4e5f6a7b8`**: the id sequences were only advanced when there was
  legacy data to migrate. On a fresh database, the first insert without an explicit id
  therefore failed ("duplicate key"). New migration `d4e5f6a7b8c9` repairs already-migrated
  databases idempotently.
- **FEDAS backfill**: category and FEDAS code were only backfilled when the variant was
  *not* found via its EAN — precisely the migrated legacy items would therefore have stayed
  without a category permanently.
- **Rule 6 (external locations)**: goods to a no-sale storage location (`lagerorte.verkauf = false` — GEWA, VEBO, Dietikon) now
  actually get no receipt date — neither on the goods receipt nor in
  `bestand.aeltestes_eingangsdatum`. The markdown clock (18/36 months) thus only starts on
  arrival at a branch.
- **`delete_invoice()`**: `first_seen`/`last_seen` were recalculated from the receipt date,
  but import sets them from the document date — after the change above, they would have
  fallen to NULL for such variants on deletion. Now the document date is used on both sides.
- Smaller fixes: `reused_products` also counted variants newly created within the same
  invoice; `fedas_code` was missing from the length check (would only have surfaced as a 503
  in PostgreSQL); two remaining hardcoded German UI texts (rule 7); saved column settings for
  the item list pointed at the wrong columns after the removal of the "item no." column;
  dead code removed from `article_details.py` and `auth.py`.
- **`app/static/js/i18n.js`**: on an unchanged language, the catalog was refetched and a
  second `sportfabrik:i18n-ready` sent. Because `session.js` reports the account language
  right after loading, every page fetched its catalog twice and its data three times
  (measured; now 1× and 2× respectively) — noticeable on the store network.
- **New tests**: `tests/test_lagerbewegungen.py` (10 tests: receipt, stock per branch,
  oldest receipt date, rule 6 per external location, recalculation on deletion — this core
  logic from rule 2 had until then not had a single test) and two catalog tests in
  `tests/test_i18n.py` comparing keys and placeholders across all three languages. Full
  suite: 145 tests passed.

**Details on Phase B, subtask B8 — choose category by hand** (rules 4/7/8,
rule 9/D21; see `docs/architektur.md`, section "POS category: suggestion
and manual choice"):
- Starting point: the FEDAS-code suggestion had existed since the first
  subtask, but there was no way to fill the gaps. And gaps are the
  normal case: only INTERSPORT supplies a FEDAS code at all, manually
  entered goods have no document at all (D27), and of the eleven sport
  areas, only five codes are confirmed from real invoices so far.
- `app/services/kategorien.py`: a selection list in till order (rule 8,
  not alphabetical), an item's state (set category, origin, FEDAS code,
  and current suggestion), setting and clearing it. Plus
  `merke_kategorie()` as a shared building block for items created along
  the way: fills only what's empty, and never overwrites.
- `artikel.kategorie_manuell` (migration `c9d0e1f2a3b4`) records the
  origin: `false` = suggestion from the FEDAS code, `true` = chosen by
  hand. The difference shows in the UI, since the mapping table isn't
  fully confirmed yet — whoever set the category by hand should be able
  to recognize that later. Existing items get `false` (server default):
  so far they can only have gotten their category from the suggestion.
- "Once per item, then remembered" now applies in both directions: import
  still only fills an empty category, but a manual choice conversely
  overwrites a wrong suggestion. Clearing restores the starting state
  (category open, `kategorie_manuell = false`) — a later document with a
  known code may then suggest again.
- Endpoints: `GET /api/kategorien` (all 35 categories),
  `GET/PUT /api/articles/{id}/kategorie`. Addressed like notes and
  prices, via the variant id; the category applies to all colors and
  sizes of the same model (rule 4). Rights: any login, including
  employees — maintaining the item master is not a document upload
  (rule 9/D21).
- UI in three places, i18n DE/FR/EN (rule 7; the category names
  themselves are not translated, they're written as they are at the
  till):
  - Item page: its own "POS category" section with the current
    category, origin ("chosen by hand" or "FEDAS-code suggestion"), and
    the selector. If the category is missing, the page also says why —
    no code on the document, or a code not yet mapped.
  - Manual entry: category per line item, optional (D23), with a note
    that an existing one stays unchanged. A scan shows the known item's
    category right away.
  - Item search: a new column (at the end, so remembered column numbers
    stay correct) and a filter "without category" — only with this can
    you find the items where someone still needs to choose. `kategorie_fehlt=true`
    (category missing) takes precedence over `kategorie_id`, otherwise
    you'd get an empty list for no apparent reason.
- The selection lists are grouped by main group (35 entries are too many
  for a flat list), but carry the full name ("Textile · Winter"):
  collapsed, a `<select>` only shows the entry, and "Winter" alone
  exists three times. Shared building block
  `app/static/js/kategorien.js`, so the item page, entry, and search all
  use the same labeling.
- Excel export deliberately unchanged: its column headers are fixed
  German (open point, see Phase A point 2) — a new column belongs in the
  same step as translating them.
- Tests: `tests/test_kategorien.py` (46 tests: till order, suggestion,
  setting/clearing/correcting, applies to all variants of the item, never
  overwriting, API including rights and error cases, entry with and
  without a category, item-search filter) and one more case in
  `tests/test_importer_fedas.py` (a manual choice survives a later
  invoice with a known code). Full suite: 416 tests passed (previously 369).
- Checked against real PostgreSQL 16: migration forward and back,
  selection list, state, setting, and filtering via the API; then the
  whole flow in the browser (choosing and saving a category for an item
  without one, an item with a suggestion, the "without category" filter,
  category during entry).

**Details on the UI redesign** (see `docs/architektur.md`, section
"Design: one token set for all pages"):
- `app/static/css/app.css` fully rebuilt: numbered sections, all colors,
  spacing, radii, shadows, and transitions as custom properties on `:root`. Dark mode now
  only redefines these tokens, no component has its own dark-mode rules.
- Calmer background, clearer type scale, fine dividers instead of zebra
  stripes in tables, soft shadows instead of colored borders; orange stays the accent for the
  main action, links, and warnings. The brand itself is unchanged.
- Two-row, sticky-on-scroll header (brand + navigation, session bar below); header and
  footer align at the same edge as the content via `--content-max`. Before, the navigation
  ran wider than the content.
- Controls unified: buttons with state colors and press feedback, fields with a soft focus
  ring instead of a thick border, `<select>` with its own arrow, language choice as a
  segmented control, "edit values" as a clean toggle, gear icon single-colored.
- Accessibility: visible keyboard focus is preserved, `color-scheme` for native controls,
  `@media (prefers-reduced-motion: reduce)` disables all transitions, mobile view with no
  horizontal overflow (previously 428 px of content on a 390 px screen).
- Fixed along the way: in item search, the "brand" column (`data-col="1"`) couldn't be
  hidden — it was missing the matching `hide-col-*` rule, so the checkbox had no effect.
- No new UI text (rule 7): the change is purely visual, all strings still run through the
  existing translation keys unchanged. Templates' cache parameter bumped to `?v=premium-1`,
  so branch computers load the new file.

**Open points from the review** (deliberately not changed in the review commit, see section 9):
- ~~`dokumente.dokumentnummer` is **globally** unique~~ — done with subtask B2
  (migration `e5f6a7b8c9d0`, see below): now `UNIQUE (lieferant_id, dokumentnummer)`
  including a duplicate check in the importer.
- ~~Rule 5 ("EAN is optional") applies in the data model and the importer, **not** in the
  parser/corrections~~ — done with subtask B3 (see below): a line item without an
  EAN passes with a note, an unreadable EAN stays a warning.
- ~~Branch scope of the views: the dashboard, invoice list, and item details show every
  logged-in account the documents of **all** branches. Whether rule 9 ("admin/head office
  cross-branch") should also restrict reading is a business question for Fabian.~~
  — clarified on 2026-09-22 (section 10, read rights): employees and branch managers may
  see documents and stock of all branches, write rights stay unchanged. The views' existing
  behavior is thus confirmed; nothing needed changing in the code.

**Concept change Rev. 6** (2026-09-21): two external processing sites instead of
one, plus an external warehouse.
- New alongside GEWA: **VEBO** (a functionally equivalent processing site) and the
  **Dietikon warehouse**. All three with `verkauf = false`, migration `b8c9d0e1f2a3`
  (idempotent; the downgrade only deletes a new storage location as long as nothing
  references it). GEWA is now called "GEWA (external processing)," so the
  difference from a pure warehouse is visible in the name.
- Rule 6 applies unchanged to all three: no receipt date, the markdown clock only
  starts at a branch SF1–SF4. The code always checks
  `lagerorte.verkauf` for this, never an individual code — a further external
  location is thus picked up automatically. The schema deliberately does not
  distinguish a processing site from a warehouse (confirmed 2026-09-21).
- `app/services/lieferadresse.py`: the keyword for storage-location recognition is
  now the first **distinguishing** word of the name. "Lager Dietikon" would
  otherwise have gotten "Lager" (warehouse) as its keyword and booked every document
  containing that word there; Dietikon is recognized via the place name, VEBO via
  its name.
- Tests for receipt date and stock parametrized across all three locations
  (`tests/test_lagerbewegungen.py`: 10 → 16), plus two new cases in
  `tests/test_lieferadresse.py` (VEBO via its name, "Lager" must not
  match). Full suite: 297 tests passed.
- **Open**: the addresses for VEBO and Dietikon are still missing and are
  marked open in `app/core/lagerorte.py`. Until they're added, VEBO is only
  recognized via its name and Dietikon only via its place name.

**Work from 2026-09-24** (branch `feature/warenwirtschaft-v2`, commits
`f4693f0` … `dd9b3aa`):

- **Tests cleaned up**: 36 files / 553 tests / ~8000 lines → 10 files /
  around 120 tests / ~2000 lines, runtime 22 s → 12 s. Five flow tests through
  the real app (`tests/test_ablauf_*.py`), table-driven tests for hard rules
  (`test_regeln.py`), parser (`test_parser.py`), operations (`test_betrieb.py`).
  Real documents via `BELEGE_DIR` or `INTERSPORT_TEST_PDF`, never in the repo.
- **Label** 47 × 83 mm (`app/services/etikett.py`, `LAYOUT`, `ROLLEN`),
  roll hint and "view sample" on the item page.
- **FEDAS** complete (`app/core/fedas.py`).
- **Import**: ECOM returns ("ret.Ecom") → supplier ECOM (555); purchase price from
  the document is saved (rule 10); on an invoice-level discount, no per-line-item
  purchase price, but a cross-check goods value − discount = total instead.
- **Parsers** `alpina.py`, `chrissports.py`, `cmp.py` (each with a checksum against
  the document), suppliers via migration `a8b9c0d1e2f3` (code 999). The
  paper invoice 9001665373 is read by the INTERSPORT parser via Tesseract.
- Tests: 118 passed without documents, 131 with documents (SQLite). No
  PostgreSQL run.
- Open: scanned delivery notes (waiting for more examples), PostgreSQL
  verification, Phase D.

**Security review from 2026-09-24:** secrets, injection, rights,
configuration, dependencies (`pip-audit`), and data protection checked. No
critical or high findings. Open (S1–S9, see [`sicherheit.md`](sicherheit.md)):
HTTPS and shorter/revocable sessions, login-attempt rate limiting,
Pillow 12.3.0, encrypted backups, API docs and `/db-test` in
production, security headers, hash pins, Google Fonts on the overview
pages.

*This document is updated on every decision/phase. The master copy lives in the Claude project "Sportfabrik WarenWirtschaftsSystem."*

## Local review on 2026-09-22

**Evening status:** branch codes corrected (SF2 Conthey, SF3 Regensdorf, SF4
Hägendorf, migration `d0e1f2a3b4c5`), documents may be shown for parser
development, Phase C planned and subtasks C1 and C2 built. Local suite:
438 passed, 20 skipped (SQLite). Nothing of it has run against PostgreSQL
yet. All on branch `feature/warenwirtschaft-v2`, pushed.

Adopted cloud-main `d1c6533`. Local suite with `DATABASE_URL=sqlite:// .venv/bin/pytest -q`: 415 passed, 20 skipped. No new PostgreSQL or production test. Codegraph freshly rebuilt with `--code-only` and exported locally as HTML and an Obsidian vault; graph files stay gitignored. Confirmed answers from the main vault carried into section 10.

## Inbox addendum – 2026-09-24, afternoon

Usability requirements (filter lists from "pending," autofocus in stock, column selection under "more filters," branch in the page title, equally sized overview buttons), mobile planning questions, and binding joint maintenance of the two HTML overviews: see [Inbox requirements 2026-09-24](anforderungen-inbox-2026-09-24.md#further-inbox-requirements--2026-09-24-afternoon). The five usability requests were implemented on 2026-09-24 (commits `431dc6f`, `fd95054`): clicking "pending" opens the filtered list with exactly the counted entries (now counted per variant), the stock search field active immediately, "show columns" under "more filters," branch shown large in the stock page title, equally sized quick-access buttons. The mobile questions were resolved by implementation on 2026-09-28 — see "Mobile phone use – implemented 2026-09-28" below.

## Mobile phone use – implemented 2026-09-28

Originally planned for the end of the project (see below), then built early on 2026-09-28 as commits `7a9c7eb`…`2b655ea` on `feature/warenwirtschaft-v2`. Full specification: [Mobile phone use](handynutzung.md).

**Access control:** a login from a phone is flagged in the session (`app/core/handy.py`); every route checks an allowlist. Blocked API calls get a translated 403, blocked pages redirect to the phone home `/m`. The flag survives "Request desktop site"; existing roles and branch limits apply unchanged, and tablets keep the desktop version.

**Implemented pages, in build order:**
- `/m`, `/m/suche` — home screen with large role-based tiles, installable as a home-screen app (manifest, icons, safe areas); article search by EAN, supplier number, or name; article view shows retail price, sizes/colours, and stock per location with the reduction stage.
- Camera scanning — browser barcode reader where available (Android Chrome), bundled ZXing otherwise (iPhone), no CDN. A code counts only after two identical reads with a valid check digit; camera stops at the first accepted code. Login returns phones to the `/m` page they opened.
- `/m/zaehlen` — scan or search an article, see stock in the active store, enter the shelf count with large -/+ buttons and a reason; server books only the difference and checks store rights. Introduced a shared article-picker (`handy-pick.js`) reused by search and count.
- `/m/lieferungen` — lists expected deliveries for the active store; confirms partial or full arrival with an arrival-date field for stores with sales. Open to everyone, including employees (rule 9, D21).
- `/m/umlagern` — reserved for branch managers/head office (rule 9); choose source and destination, scan/search items into a list, book removal and receipt in one step, matching the desktop flow. *(Since the evening of 2026-09-28: dispatch with a dispatch date; the destination confirms on `/m/lieferungen`.)*
- `/m/ausbuchen` — reserved for branch managers/head office (rule 9; *since the evening of 2026-09-28 employees may book sales only*); cancelling a booking stays desktop-only. Pick store and reason, then scan/search and tap "1 piece" repeatably. Negative-stock warning (F9) works as on desktop.
- `/m/erfassen` — manual goods entry without a document; known EAN pre-fills brand/description/colour/size/last price/category. Employees book only to their own stores, branch managers/head office to any location (rule 9). Label printing stays desktop-only.
- `/m/runterschreiben` — shows models reaching -50%/-70% (rule 6) in the chosen store or within 30 days, each with a "Done" button; scan/search to set 30/50/70% by hand or reset to the recommendation. Head-office recommendations stay desktop-only.

**Not built (deferred, matching original scope):** cancelling a booking, label printing, head-office markdown recommendations — all desktop-only by design. VPN/protected remote access for branch managers/management while off the store WiFi is still open (see original plan below); the phone allowlist enforces which *features* are reachable, not network origin.

**Original plan (2026-09-24), for reference:** web app on personal phones: search/camera scan, price and stock lookup, counting/correcting, goods receipt, transfer, and booking out. Staff only on the approved store WiFi; branch managers and management/head office additionally via protected remote access. Existing rights stay in place; access checked server-side, no GPS tracking. Shared central database, no offline bookings initially. VPN/WiFi and the exact timing within the later project phases stay open.

### Rights refined on 2026-09-24

Employees may manually book in and correct stock, but only in their assigned branches. Booking out a sale/removal, cancelling, and transferring are reserved for branch managers and head office. Their existing cross-branch booking rights remain in place; read rights are unchanged.

Implemented in the local code: server-side check and matching navigation, quick access, and stock actions. Foreign storage-location ids are rejected with HTTP 403 on manual entry/correction. Without a branch assignment, no manual booking is possible. Earlier statements of "all roles" for booking-out/transfer are thereby superseded. No server deployment as part of this change.

## New requirements: item details and reports – 2026-09-24

[Item details and reports](anforderungen-artikeldetails-auswertungen-2026-09-24.md) describes the new design of item details, manual markdown, summarized activity, statistics for management/head office only, account management by head office, and further usability improvements. All 17 points are on the task plan, implementation open. The three follow-up questions are answered: estimated revenue at the then-current marked-down sale price; manual markdown by all staff per branch to 30/50/70%; quick access per user. Existing rights for bookings-out and item deletion stay valid.

### Implementation status of item details and reports – 2026-09-24, evening

Built and checked in the browser against a test database (not in store, no PostgreSQL run), suite 127 passed / 12 skipped:

- **Points 1–6, item details:** RRP history at the top and compact, price list collapsible (collapsed); POS category via "edit," EAN & label via its own button (both collapsed); notes removed from the UI (data and API stay); at the bottom, the current stock of all sizes and colors across all storage locations (`/api/bestand?artikel_von=`); "delete item" with a red notice at the very bottom.
- **Point 10:** the item name in stock links to the item details.
- **Point 15:** item search like stock — category first, brand + description and supplier no. + EAN each in one column.
- **Point 17:** entry now only offers the five supplier groups.

Decided (point 13): if an account is deleted, all bookings stay in the database; the name stays, only the link to the account is dropped.

- **Points 7, 11, 12, manual markdown:** new table `reduktionen_manuell` (migration `c0d1e2f3a4b5`), 30/50/70% per model × branch, "recommendation" clears the choice. Item details show the recommendation and effective level per branch with buttons (only own branches editable), the stock list has a "markdown" column, and markdowns has "mark down items by hand" (EAN scan or the whole stock list) and the "chosen by hand" list. The label suggests the effective level.
- **Point 16:** booking out offers a search/stock list under "choose from stock" with "book out 1 piece" per row (same reason, same rights).

All 17 points of the catalog are implemented.

- **Point 8, recent activity (2026-09-25, branch `feature/aktuelles`):** the overview shows a delivery as a whole delivery (supplier, document number, branch, number of items and pieces), a transfer as one entry (from → to), and removals with a reason other than sale. Sales and corrections no longer appear. Tested and checked in the browser with test data; no PostgreSQL run.
- **Point 14, quick access (2026-09-25, branch `feature/schnellzugriffe`):** five functions selectable per user and sortable via drag-and-drop (`users.schnellzugriffe`, migration `d1e2f3a4b5c6`). Merged via PR #12.
- **Point 9, statistics (2026-09-25):** new page `/statistiken`, branch manager/head office only (`require_chef_page`/`require_chef_api`). Periods day/week/month/year/overall (`app/services/statistik.py`). Shows pieces sold per POS category (bar chart as inline SVG, the same pattern as the RRP history in item details, no external library — rule 7/CDN-free frontend), estimated revenue, and an order recommendation (best-selling items alongside current stock).
  - **Revenue estimation method:** RRP at the time of sale (the most recent `Preis.datum` before it, otherwise the earliest known one) multiplied by the markdown automatically due at that point (rule 6, computable backward from the goods-receipt dates). A manually chosen markdown (`reduktionen_manuell`) has no history and is deliberately **not** included — nothing more than the sale time can be reconstructed; the response marks this explicitly (`einnahmen_ist_schaetzung: true`). Cancelled sales (counter-bookings) don't count. This simplification is an implementation decision, not a confirmed business decision — cross-check if needed.
  - Test-first: `tests/test_ablauf_statistik.py` (periods, category totals, revenue estimate, cancellation exclusion, rights). Checked in the browser against a separately set-up SQLite instance (login, chart, order recommendation, no console errors) — no PostgreSQL run.
- **Point 13, account management (2026-09-25):** new page `/konten`, head office only (`require_admin_page`/`require_admin_api`, new in `app/routers/auth.py`). Head office creates employee and branch-manager accounts (till number, name, role, password ≥ 6 characters for branch manager/head office, at least one branch for employee/branch manager) and deletes them (`app/services/konten.py`). Decided (2026-09-24): on deletion, all bookings stay in the database (name/till number are already just a snapshot there, not foreign keys), only `benutzer_lagerorte` gets cleaned up. Head office cannot delete itself. The minimum password length of 6 is an implementation decision — rule S2/`sicherheit.md` still leaves 6 vs. 10 open.
  - Test-first: `tests/test_ablauf_konten.py` (creating with/without password/branch, rights, deletion including self-protection, duplicate till number). Checked in the browser: login, form, live table, validation errors, no console errors — no PostgreSQL run.

Suite: 137 passed / 12 skipped.

## UI redesign after DESIGN.md – 2026-09-27/28

[DESIGN.md](../DESIGN.md) is the new design system (mission, rules, tokens, components, accessibility, migration plan for `app.css`); Geologica 300 added locally and registered for mixed-weight titles. Referenced from `docs/start.md`.

**Decision 2026-09-27:** formal address throughout — German consistently "Sie," French "vous." Affected 9 German and 2 French texts plus template fallbacks (`app/static/i18n/{de,fr}.json`, `articles.html`, `history.html`, `preview.html`).

**Full redesign across all pages** (commit `d62b11c`): tokens (`app.css` §2) — warm neutrals, new status tokens success/warning/info alongside danger, reduction-stage tokens (30/50/70, coupled to `etikett.py` roles), 3 radii + pill instead of 5, 4px spacing scale, 9-step type scale, elevation levels; light/dark kept in sync. All 18 raw font sizes mapped to `--fs-*` tokens; broken `prefers-reduced-motion` rule fixed (missing declaration block). Components: button variants (primary/secondary/ghost/danger/loading), form fields (44px, 16px against iOS zoom, helper/error pattern), panels without shadow (elevation 0), tables (sort icons, right-aligned numbers, selected row), notices with 4 status colors. New `.chip-stage` component (yellow/red/green) replaces the always-red `.reduktion-stufe`, wired via `reduktion-wahl.js` into all tables. Icon sprite (`app/static/img/icons.svg`, 27 icons) replaces all 7 Unicode symbols in CSS/JS and a duplicate sort implementation in `history.html`. Contour motif (`contours.svg`) on the login background and dashboard hero corner; dead `.welcome` CSS replaced by a real `.hero`. Mixed-weight titles (`.title-mixed`) on the dashboard greeting and the branch code in stock/markdown (replaces orange-on-white text that broke contrast rules).

**Follow-up (commit `47a4266`):** scan field (DESIGN.md §10.3, new `--icon-scan` component, 52px, barcode icon left) on the three real scanner fields (write off/enter/transfer `#ean`); empty state (§10.9, `.empty-state`, icon + sentence, centered) on the seven existing "no data" texts; loading state (§10.1) fixed — `.is-loading` no longer hides the label (was `color:transparent`), spinner now positioned before the text and takes `currentColor`, wired at all 13 existing "disabled during fetch" spots across 10 JS files. Checked via Playwright browser (light/dark, real accounts): scan field, empty-state icon, and loading spinner render as intended.

**Ultrareview fixes for PR #16** (commit `34b8f71`): `.warning-text`/`tr.warning` is also used for failed bookings, cancellation errors, and connection drops — the `--warning-*` switch made these real errors show amber instead of red; reverted to `--danger-*` per DESIGN.md §4.3 (a failed booking is danger, not warning); `.stat-warn` (genuine notices like "item without EAN") stays warning. Mixed-weight greeting searched the first name via `indexOf` in the already-interpolated sentence (false bolding if the name coincidentally matched fixed sentence text); now searches the `{name}` placeholder in the raw, untranslated text first — collision-safe.

**Verification throughout:** checked in the browser (Playwright/Chrome, light and dark, real accounts); no automated test changes (pure CSS/JS/markup, no new business logic) and no PostgreSQL/production run.

**Documentation translation (2026-09-28, commit `2e7712c`):** all project docs and `CLAUDE.md` translated German → English; no content/decision changes.

## Status check and next steps – 2026-09-28

Full review of GitHub, code, and documentation on 2026-09-28.

**GitHub:** PRs #8–#17 all merged, no open PR, no issues. `main` ends at
PR #17 (ultrareview fixes). `feature/warenwirtschaft-v2` is ahead of `main`
with the English documentation, HTTPS (S1), the phone feature set, and this
documentation update. `feature/schnellzugriffe` holds one unmerged German
doc commit (`2e91a8a`); its content (quick-access API and data model) is now
in the English `api-referenz.md` and `datenmodell.md`, so the branch can be
deleted. Remote branches `claude/sportfabrik-inventory-init-06df66` and
`fix/ultrareview-warning-danger` are fully merged.

**Tests:** `DATABASE_URL=sqlite:// .venv/bin/pytest -q` — 165 passed,
12 skipped (2026-09-28). Still no PostgreSQL run, no store deployment.

**Documentation fixed in this review:** API reference now lists the
quick-access API, the phone pages and phone gate, `/runterschreiben`,
`/empfehlungen`, and all status codes; data model documents
`users.schnellzugriffe` and account deletion; README reflects Phase D,
statistics, accounts, quick access, phone, HTTPS, and the design system;
the two HTML overviews in `docs/overviews/` replace the German copies from
2026-09-24 (without Google Fonts, security S9).

**Open business decisions at the time of the review** — all seven
decided the same evening, see the next section (details and code status:
[`anforderungen-inbox-2026-09-28.md`](anforderungen-inbox-2026-09-28.md)):

1. **Sale booking by employees** (K8) — the 2026-09-25 clarification
   implies employees may book sales; rule 9 reserves all write-offs for
   branch managers/head office.
2. **Minimum 30 % markdown** (K4, N1) — exact new thresholds, and how D-F2
   ("new delivery jumps back to 0 %") changes.
3. **Markdown rights of branch managers** (K6) — own branches only?
4. **"Pending" per branch** (N3) — how to treat item-master counts.
5. **Transfer as a delivery** (N4) — dispatch date, goods in transit,
   arrival confirmation at the destination; effect on rule 6.
6. **Arrival confirmation timing** — immediately or after unpacking.
7. **Minimum password length** 6 vs. 10 (S2).

**Next steps, in suggested order:**

1. Merge `feature/warenwirtschaft-v2` into `main` via a PR (phone, HTTPS,
   English docs); delete `feature/schnellzugriffe` and the two merged
   remote branches.
2. Fabian decides points 1–3 above; then implement K1, K2, K4/N1, K5, K6
   test-first (small, mostly isolated changes).
3. Short design for N4 (transfer as delivery) together with decision 6;
   then implement on desktop and phone.
4. N2 (markdown at goods entry) and N3 (pending per branch) after their
   questions are answered.
5. Store deployment preparation (Phase F): PostgreSQL test run of all
   migrations, S1 rest (invalidate sessions on password change), S3 Pillow
   12.3.0, S4 encrypted backups, S5–S8, network separation, VPN for
   off-site branch-manager access, server setup per `SERVER-SETUP.md`.
   Remove the temporary "−1" test button in the stock view
   (`bestand.minus_one`) once booking out has been tried in the store.
6. Test the phone pages on a real iPhone and Android with real labels
   (camera scan, duplicate-scan protection).
7. ~~Language rule for code comments and the management overview~~ —
   decided the same evening: both may stay German.
8. Ongoing: collect more supplier documents (delivery notes, scans),
   wireless scanner test device, label test on the Sato with the new roll,
   Intersport till interface (Phase G).

## Decisions and implementation – 2026-09-28, evening

Fabian's answers to the seven open decisions, implemented test-first on
`feature/warenwirtschaft-v2` (commits `c50166d`…`7e4415c`), checked in the
browser against a separate SQLite test instance (desktop and phone
emulation). Suite: 167 passed, 12 skipped. No PostgreSQL run, no store
deployment.

1. **Employees book out sales — only sales** (K8). All other reasons and
   cancelling stay with branch managers/head office; employees only in
   their branches. Write-off page, phone page, quick access, and navigation
   are open to employees; the reason list and the undo button follow the
   role (`c50166d`).
2. **Markdown levels: 30 % from arrival, 50 % after 18 months, 70 % after
   36 months** (K4/N1). Without a receipt date (external location, no
   clock) the level stays 0. D-F2 adjusted: a new delivery only raises a
   notice when the old stock was reduced by more than 30 %. The UI calls
   the time-based level "Automatic" instead of "Recommendation" (K5). The
   statistics revenue estimate uses the new levels (`145b81b`).
3. **Markdowns only in one's own branches — also for branch managers;
   head office all** (K6). Covers manual level, "done", and answering
   head-office recommendations; `/api/reduktionen` returns `darf_aendern`
   and the pages hide the buttons elsewhere (`42d7a7c`).
4. **"Pending" per branch** (N3). Missing EAN/category count only variants
   with stock in the active branch; head office without a branch sees the
   whole item master; the linked list filters by the same branch
   (`6a79a46`).
5. **Transfer as a delivery** (N4). The source dispatches with a dispatch
   date (removal booked at once), the destination gets an expected goods
   receipt and confirms the arrival like a delivery; date rules D13/D17/
   F10/F11 apply at arrival. Migration `f3a4b5c6d7e8`. Replaces F5
   ("booked by the receiving branch in one step") (`7e4415c`).
6. **Confirm arrival after unpacking and checking** — a working rule, no
   code change; the delivery pages say so in their intro text. The arrival
   date entered then starts the markdown clock.
7. **Minimum password length stays 6**, on condition that only the private
   store Wi-Fi or the VPN can reach the server (network separation
   becomes a hard prerequisite, `sicherheit.md` S2).

Also implemented from the 2026-09-25 clarifications: statistics show
removals other than sales per reason, the latest removals with the person
who booked them (K1), and open on "this week" (K2) (`fd33e9a`).

**Still open:** N2 — choosing the markdown at goods entry: should the
choice be stored as a manual markdown of the target branch (then the
label and stock use it)? Not implemented until answered. A cancelled or
wrongly addressed transfer in transit cannot be withdrawn yet (would need
a "cancel dispatch" action).

**Next steps:** ~~merge into `main` (PR); answer N2~~ (done 2026-09-29); store deployment
(Phase F: PostgreSQL run incl. migration `f3a4b5c6d7e8`, network
separation/VPN as the condition for decision 7, S1 rest, S3–S8); test
phones in the store; remove the temporary "−1" button after the in-store
trial.

## Decisions and implementation – 2026-09-29

PR #18 merged into `main`; obsolete remote branches deleted.

1. **N2 — markdown at goods entry** (decision 2026-09-29): manual entry
   (`/erfassen`, `/m/erfassen`) has an optional field per line
   (automatic / −30 / −50 / −70 %). The choice is stored as the manual
   markdown (`reduktionen_manuell`) of the target branch, in the same
   transaction as the goods receipt. Empty keeps an existing choice.
   Rights as on "Markdowns": own sales branches only, head office all;
   external locations reject it (409). `/api/erfassen/stammdaten` reports
   per location whether a markdown can be chosen (`reduktion`).
2. **Cancel a transfer in transit** (decision 2026-09-29): branch manager
   of the **source** branch, the person who **dispatched** it
   (`wareneingaenge.versendet_von`, decided later the same day), or head
   office. The open (not yet arrived)
   rest of each line goes back to the source as a new `umlagerung`
   movement (reason `zurueck:<destination>`), with the date it had at
   dispatch (`mitgebracht_datum`); no new markdown clock. Already arrived
   parts stay at the destination. The goods receipt gets status
   `storniert` (migration `a4b5c6d7e8f9`). Desktop only: section
   "In transit" on `/umlagern` with a two-click cancel.

**Decided later the same day:** whoever dispatched a transfer may also
cancel it (e.g. a branch manager who sent from GEWA). Cancelling stays
desktop only — not needed on the phone.

**Security and PostgreSQL, same day:** S1 rest (a new password ends all
sessions of the account: HMAC of the password hash in the session), S3
(Pillow 12.3.0), S5 (API docs off), S6 (`/db-test` only `{"ok": true}`),
S7 (security headers, strict CSP on HTML pages; all inline scripts and
`onsubmit` attributes moved into `/static/js`). All migrations ran on
PostgreSQL 18 in a throwaway Docker container (upgrade, downgrade of
`a4b5c6d7e8f9`, upgrade), plus an app smoke test (entry with markdown,
transfer, cancel, headers). Pages checked in headless Chromium (Brave):
16 pages without JS errors or CSP violations. Still open for the store:
S4, S8, network separation, deployment itself.

**S4, same day:** external backups are always encrypted with `age`
(decision 2026-09-29). The server keeps only the public key
(`backup-age-recipient.txt`, not in git); the private key stays on a USB
stick and on paper. `scripts/backup_inventory.py --external` writes one
`inventory-TIMESTAMP.tar.age` plus a `.sha256` file and refuses to copy
without a valid key. Checked with a real age round trip (encrypt, checksum,
decrypt). Setup and restore: `docs/BACKUPS.md`.

## Pending visibility — decision 2026-09-29

**Confirmed requirement; planned, not implemented by this documentation change.** This supersedes the earlier branch restriction for these two item-master notices only.

- **Without EAN** and **without checkout category**: show the shared, cross-branch totals to **all roles in every branch**, including employees and branch managers. Do not restrict these two counts to stock in the active branch. Their links must open the matching cross-branch lists so the listed variants match the counts.
- **All other Pending notices** (expected deliveries/transfers, negative stock, due and upcoming markdowns): keep them scoped to the selected branch. Do not turn these into cross-branch totals.
- This changes notice visibility, not editing or booking permissions. Existing permissions remain unchanged.
- Current checked code still filters the two item-master counts by the active branch; implementation remains a task.

Source: Fabian’s direct clarification on 2026-09-29.

## Head-office recommendations — planned extensions 2026-09-29

**Confirmed requirements; planning only, not implemented by this update.**

1. Show open head-office markdown recommendations in **Pending** on the overview, scoped to the selected recipient branch. A click should open the matching recommendations on the markdown page. This is a branch-specific notice, unlike the global missing-EAN and missing-category notices.
2. Allow **head office to withdraw recommendations**. Withdrawn recommendations should no longer be actionable or counted as open.
3. Allow head office to send the same recommendation **directly to all sales branches (SF1–SF4) in one action**, in addition to selecting one branch. Keep each branch’s response separate so acceptance/rejection remains visible per branch. External storage locations are not sales branches.

Existing response permissions and acceptance/rejection with a reason remain unchanged. No code changes or deployment requested.

**Details to settle before implementation:** whether withdrawal applies only to unanswered recommendations or also to answered ones, what happens to a markdown already accepted (do not infer automatic rollback), whether all-branch sending includes branches without stock of the model, and whether future-dated open recommendations appear immediately or only from their effective date. Preserve these as open questions rather than confirmed decisions.

Source: Fabian’s direct request on 2026-09-29.

### Dashboard redesign (2026-09-29)

Decision (Fabian): small charts are allowed on the dashboard; `DESIGN.md` §9.3 amended. `/api/dashboard` → `filiale` now also returns `stufen` (pieces per markdown stage by age of last receipt, no manual overrides), `verlauf` (sold pieces per day, last 14 days) and `bestseller` (top 5 models, last 7 days), all for the active branch only. The page shows them as three panels (`uebersicht.js`, `.insights` in `app.css`); "Aktuelles" is grouped by day. Test: `tests/test_ablauf_dashboard.py`. Docker image must be rebuilt (`docker compose --env-file .env.server up -d --build`) to see UI changes.

## Next-work decision — structural redesign, 2026-09-29

Fabian selected **Sportfabrik Inventory Redesign as the next work item**, ahead of previously queued features and deployment preparation. [Full requirements](redesign-2026-09-29.md) preserve the three local references, exact menu order, sidebar, stacked logo, function search, dashboard charts and Settings modal. Existing colors/design language and role/branch permissions remain. This is a new request beyond the earlier completed redesign; no implementation performed in this update.

### Redesign phases 1–3 implemented (2026-09-29)

Fabian confirmed the Phase 0 points (route `/anstehend`, Settings modal contents, chart metrics, reference images). Implemented: left sidebar from 901 px (stacked logo, groups Bestand / Wareneingang / Warenausgang / Belege / Verwaltung, order per [specification](redesign-2026-09-29.md)); below 901 px the top bar with "Menü" stays. The pages are static HTML, so the shell is `nav.js` + `app.css` §5b, not a template base. Role filters unchanged; `/anstehend` and Settings are prepared in `nav.js` but hidden until phases 4 and 6. Labels: `nav.articles` = Produkte/Produits/Products, new group keys in de/fr/en. Test `tests/test_navigation.py`. Open: phases 4–8.

## Decisions and implementation — 2026-09-30 (refinements after the redesign)

Merged into `feature/warenwirtschaft-v2` (183 tests pass), checked locally, no store deployment.

- **Sidebar and quick access (Fabian, 2026-09-30):** collapsible sidebar with a three-line icon (desktop; choice saved in the browser, set before first paint by `theme-init.js`), user name next to the user icon (expanded only), larger menu text and spacing, the separate Settings entry is removed (user icon and branch pill open the same dialog — supersedes the Settings entry of the redesign navigation). Quick-access cards moved above the greeting: title only, fixed height, stretched over the full width for any number of cards (`--anzahl`), small gear icon instead of the "Edit" text.
- **Pending visibility (decision 2026-09-29, implemented 2026-09-30):** `stamm` counts "without EAN" / "without checkout category" across the whole item master for all roles in every branch; the links carry no branch filter, so counts and lists match. Other notices stay branch-scoped.
- **Bell:** top right on every page (next to the function search), links to `/anstehend`, badge = number of Pending notices (one row = one notice, hidden at 0). `GET /api/anstehend/anzahl`; counting rule in `services/uebersicht.anzahl_meldungen` mirrors `anstehend-liste.js`.
- **Preset markdown scanning:** on Runterschreiben a stage (off/−30/−50/−70 %) can be chosen before scanning; a scan that finds exactly one model sets it to that stage immediately (server checks rights per branch as before, rule 9); several models → nothing is set, the list is shown.
- **Head-office recommendations (answers of Fabian, 2026-09-30):** (1) head office can withdraw a recommendation any time, before or after the answer; (2) no automatic rollback of a stage already set — head office sends a new recommendation with the old stage instead; (3) "send to all" goes to all sales branches including those without stock of the model, so a later delivery already finds the recommendation; (4) open recommendations show in the branch's Pending immediately, regardless of the effective date. Implemented: status `zurueckgezogen` (migration `b5c6d7e8f9a0`), `POST /api/empfehlungen/{id}/zurueckziehen`, `alle_filialen` on `POST /api/empfehlungen`, Pending notice `empfehlungen_offen` linking to `/runterschreiben#empfehlungPanel`.

## Capability review and next milestone — proposal 2026-10-01

Source: vault note "Sportfabrik Inventory – Capability Review and Improvement Priorities" (static review of 2026-09-30, status: recommendations not approved). Key findings re-checked in code on 2026-10-01: deleting a posted document deletes its stock movements (`importer.py:435`, conflicts with hard rule 2); counts use the balance at submission (`korrektur.py:95`); no retry protection on stock-changing requests; revenue estimates ignore manual markdowns; invoice and delivery note can both book the same goods; `bestellempfehlung` is a best-seller ranking.

Proposed milestone: **one branch reconciles a complete working day, recovers from mistakes, and restores its data.** Packages 0–5, acceptance examples, and open questions Q1–Q9: [roadmap-operational-reliability-2026-10-01.md](roadmap-operational-reliability-2026-10-01.md). Business questions answered by Fabian on 2026-10-01 (see below); no code changed. Existing decisions (30/50/70 % markdowns, optional purchase price, employee corrections in own branches, negative stock allowed, online-only phone use) stay unless Fabian decides otherwise.

### Answers to Q1–Q9 (Fabian, 2026-10-01)

Posted documents are cancelled (not deleted) by branch manager/head office. The delivery note comes with the goods, the invoice usually later; an invoice matching booked goods always asks "attach only" or "new goods". A stale count warns and asks for a recount; no approval for large differences. Pilot: **SF1**, sales scanned in the app in addition to the till. **No data loss**, downtime of a few hours acceptable — requires continuous replication/WAL archiving beyond the nightly backups. Customer returns for fit/taste: any employee in own branch; other reasons need branch manager/head office approval (confirmed). Lost in transit: branch manager/head office. Reorderable items: manual flag per item, delivery times per supplier. Details and consequences: [roadmap](roadmap-operational-reliability-2026-10-01.md), "Decisions". Package order 0–5 approved; Fabian owns the daily SF1 reconciliation.

## Inbox requirements 2026-10-01 (recorded, not implemented)

Ten new points from the vault (categories, forwarding a delivery before arrival, bug-report and unknown-document mail buttons, size normalization, CMP parser, replacing an internal EAN, Overview main-group bug, hiding Statistics/Pending for GEWA/VEBO/Dietikon). Per-point status. Answers of Fabian (2026-10-01): (5) the unknown-document mail button is allowed — explicit click, only to his own mailbox, an exception to rule 1; (3) a delivery can be redirected to another branch before arrival, booking still only on arrival at the destination; (8) a later EAN is added, not replaced — both EANs lead to the same variant. `docs/anforderungen-inbox-2026-10-01.md`. Test run of the same day: the CMP re-order file is an unknown layout; an arrival bug with duplicate variants was fixed (commit `385459f`).
