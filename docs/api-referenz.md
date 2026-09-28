# API reference

All endpoints except `/login`, `/logout`, `/static/*`, and `/db-test`
require a valid login; those marked 🔒 additionally require a branch
manager or admin role (internally still `chef`/`admin`). Page endpoints
(HTML) redirect to `/login` when not logged in; JSON endpoints respond
with HTTP 401 or 403 — see `architektur.md`, section "Security model".

Error messages (`detail`) are localized server-side: when logged in, in
the user's account language; otherwise (e.g. `/login`) based on the
`Accept-Language` header — see `architektur.md`, section "Multilingualism
(i18n)".

## Login

| Method | Path | Purpose |
|---|---|---|
| GET | `/login` | Login page |
| POST | `/login` | Checks till number (+ password for branch managers/admin), sets the session. Response `{"requires_password": true}` if a branch-manager/admin till number was sent without a password. After 5 wrong passwords the account is locked for 20 minutes: response **429** with the remaining wait time, even with the correct password (security S2) |
| POST | `/logout` | Ends the session, redirects to `/login` |
| GET | `/api/me` | The logged-in person: `{kassennummer, name, role, role_label, language, lagerort, lagerorte, kann_alle_filialen_waehlen}`. `role_label` and error messages are translated into `language` (`de`/`fr`/`en`). `lagerort` is the active branch (`{id, code, name}`, or `null` = "all branches", possible only for admin); `lagerorte` are the branches the user may switch between (admin: all) |
| POST | `/api/active-lagerort` | Switches the active branch for the session. Body `{"lagerort_id": <id or null>}`; `null` is allowed only for admin (= "all branches"), otherwise the branch must be assigned to the user (otherwise 403) |
| POST | `/api/language` | Sets the logged-in account's language. Body `{"language": "de"｜"fr"｜"en"}`, otherwise HTTP 422. Response `{"language": "..."}` |
| GET | `/api/schnellzugriffe` | Quick-access shortcuts of the logged-in account (point 14, decision 2026-09-24): `{schnellzugriffe: [...], verfuegbar: [...]}`. `schnellzugriffe` is the saved selection, filtered by role; without an own choice, the previous default (`ausbuchen, erfassen, umlagern, wareneingaenge, upload`, also role-filtered). `verfuegbar` lists every function key selectable for the role (`app/core/schnellzugriffe.py`). `/api/me` returns the same effective list as `schnellzugriffe` |
| PUT | `/api/schnellzugriffe` | Saves selection and order. Body `{"schnellzugriffe": ["erfassen", "bestand", ...]}`: 1–5 entries, no duplicates, only functions allowed for the role — otherwise HTTP 422. Response `{"schnellzugriffe": [...]}` (the saved selection). Stored in `users.schnellzugriffe` |

The `next` parameter of `/login?next=…` (where to redirect after login) is
checked client-side against a whitelist of known routes
(`app/static/js/login-redirect.js`) — this prevents a tampered link from
redirecting to a foreign site after login (open redirect).

## Overview

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Overview page (dashboard) |
| GET | `/api/dashboard` | Key figures (number of variants/documents/lines, total quantity delivered) + the last 5 imported documents; plus `lagerort` and `filiale` (pieces, sold/removed today, negative stock, expected deliveries, `reduktionen` per level with `faellig`/`bald`) for the active branch, `aktuelles` (up to 8 combined entries: `art` = `lieferung` per goods receipt and day, `umlagerung` per transfer with `von`/`nach`, `abgang` per write-off without a sale; delivery/transfer with `positionen` and `stueck`), and `stamm` (`ohne_kategorie`, `ohne_ean`) |

## Items

| Method | Path | Purpose |
|---|---|---|
| GET | `/articles` | Item search page |
| GET | `/api/brands` | List of all brands that occur |
| GET | `/api/articles` | Item search; filters: `q`, `brand`, `ean`, `supplier_article_no`, `description`, `kategorie_id`/`kategorie_fehlt` (POS category, or "none yet"; `kategorie_fehlt=true` overrides `kategorie_id`), `last_delivery_from`/`last_delivery_to` (date range on the last delivery), `ohne_ean=true` (variants without an EAN only); sorting `sort_by` (`brand`, `description`, `supplier_article_no`, `ean`, `color`, `size`, `first_seen`, `last_seen`) + `sort_dir` (`asc`/`desc`); pagination `page`/`page_size` (max. 100) |
| GET | `/api/articles/export` | Same filters as `/api/articles`, but **without** pagination: returns a ready-formatted Excel file (`.xlsx`) with all matches for download |
| GET | `/api/articles/{product_id}/history` | Full delivery history of an item **including all color/size variants with the same brand + supplier item number**, newest invoice first; sortable (`sort_by`/`sort_dir`, see below) |
| GET | `/api/articles/{product_id}/prices` | Price history (UVP/RRP per invoice/unit) for the item group |
| GET | `/api/articles/{product_id}/kategorie` | The item's POS category: category set, `manuell` (chosen manually, or suggested from the FEDAS code), `fedas_code`, and the current `vorschlag` (suggestion) |
| PUT | `/api/articles/{product_id}/kategorie` | Set the category manually (`{"kategorie_id": 12}`) or clear it again (`{"kategorie_id": null}`); any logged-in user, including employees (rule 9/D21) |
| GET | `/api/articles/{product_id}/notes` | Notes on the item group, paginated (`page`, 20 per page), newest first |
| POST | `/api/articles/{product_id}/notes` | Create a new note (`body`, max. 2000 characters) |
| PUT | `/api/articles/{product_id}/notes/{note_id}` | Edit a note; requires the `version` of the last-read note (optimistic locking, otherwise HTTP 409); own note only, or as branch manager |
| DELETE | `/api/articles/{product_id}/notes/{note_id}` | Delete a note; requires `version`; own note only, or as branch manager |

`sort_by` for line-item lists (invoice detail and item history, see
below) accepts: `position`, `invoice_date`, `description`, `ean`,
`article_no`, `color`, `size`, `quantity`, `unit`, `uvp`. Missing values
are sorted to the end; `size` recognizes common clothing sizes
(`XS`…`5XL`) as well as mixed numbers/text (e.g. shoe sizes) and sorts
them sensibly instead of purely alphabetically. `article_no` (the former
INTERSPORT-internal item number) is no longer kept as its own column
since the new data model (Phase A, item 3) — here the value, if present,
comes from the line's unchanged original snapshot.

## POS category

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/kategorien` | All 35 POS categories (main group × sport area, rule 8) in the till's order: `{"items": [{"id": 1, "hauptgruppe": "Textil", "sportbereich": "Velo"}, …]}` — bike and food have `sportbereich: null` |

The category hangs off the **item** (rule 4: shared across branches, for
all colors and sizes), but is addressed via the variant id (`product_id`)
like notes and prices. Normally the invoice's FEDAS code suggests it
(`app/core/fedas.py`); if it's missing or unknown, it's chosen manually
(`PUT …/kategorie`, see above). Once chosen manually, it counts as
binding: no later import overwrites it again. Clearing it restores the
initial state, and a later document with a known code may suggest again.
Unknown category → HTTP 422, unknown variant → HTTP 404, unknown fields
in the body → HTTP 422.

The category can also be supplied during manual entry (field
`kategorie_id` per line, see below) — there is no FEDAS code there. It
only fills in a category that is still empty.

## Invoices

| Method | Path | Purpose |
|---|---|---|
| GET | `/invoices` | Invoice list page |
| GET | `/invoices/{id}` | Invoice detail page |
| GET | `/articles/{id}/history` | Item history page (including notes and price history) |
| GET | `/api/invoices` | Invoice list; filter `q` (invoice number), pagination |
| GET | `/api/invoices/{invoice_id}` | Invoice details including all lines; sortable (`sort_by`/`sort_dir`, see above) |
| DELETE | `/api/invoices/{invoice_id}` | 🔒 Irrevocably delete an invoice including lines and original snapshots; affected item metrics are recalculated |

## Upload & import

| Method | Path | Purpose |
|---|---|---|
| GET | `/preview` | 🔒 Upload page (supports several PDFs at once, see "Batch import" below) |
| POST | `/upload-preview` | 🔒 Upload one PDF, recognize supplier/document type, and return the lines as a preview (max. 20 MB, no DB change) |
| POST | `/validate-preview` | 🔒 Re-validate manually corrected lines (see `corrections`) against the same file before importing; requires `expected_hash` |
| POST | `/import-invoice` | 🔒 Confirm the import; requires `expected_hash` (SHA-256 of the checked file), `confirmed=true`, optionally `corrections` (JSON, see below) and optionally `lagerort_id` (target of the goods receipt, see below). Without `lagerort_id`, booking goes against the account's active branch (`GET /api/me`, `lagerort`) — without a chosen branch (possible only for admin, all branches) HTTP 400 |
| GET | `/invoice-import-status` | 🔒 Checks, via file hash (`file_hash`) or via document number **at the recognized supplier** (`invoice_number` **and** `parser_key`, both from the preview response), whether an invoice has already been imported — used by the batch-import queue to skip already-imported files. Without `parser_key`, only the file hash counts: the same document number can be a completely different invoice at a different supplier |

**Warnings and hints per line**: each line in the response has two
lists — `warnings` (blocks the import until checked/corrected) and
`hints` (non-blocking, currently: line without an EAN, rule 5). Plus the
counters `rows_with_warnings` and `rows_with_hints`. `/import-invoice`
rejects a document only because of `warnings`, never because of `hints`.

**Target storage location (`/upload-preview`, `/validate-preview`,
`/import-invoice`)**: the preview returns `lagerort_suggestion`
(recognized from the delivery address, with `code`, `name`,
`from_delivery_address`, and the matched features — `null` if nothing
unambiguous was found), `lagerort_options` (what this account may book
against, own branch first), and `lagerort_active` (active branch).
`/import-invoice` takes the form field `lagerort_id` for this; if
missing, booking goes against the active branch. An unknown storage
location results in HTTP 403 (D19, see `docs/architektur.md`).

**Recognized supplier (`/upload-preview`, `/validate-preview`)**: besides
the lines, the response contains `parser_key` (the responsible parser
module = `lieferanten.parser_key`), `supplier_name` (shown in the
preview), and `document_type` (`rechnung`, `lieferschein`,
`auftragsbestaetigung`, `bestellung` — `null` if the type can't be
recognized in the document). If the layout is unknown, the upload
responds with HTTP 422 and a message that the document layout isn't
known yet (see `docs/architektur.md`, "PDF parsing").

**Corrections (`corrections`)**: JSON object
`{"<line number>": {"<field>": "<new value>"}}`. Allowed fields: `brand`,
`supplier_article_no`, `article_no`, `ean`, `description`, `color`,
`size`, `quantity`, `unit`, `uvp` — `ean`, `color`, and `size` may stay
empty (rule 5). The server fully re-validates every line (required
fields, EAN format if an EAN is entered, number format) instead of
blindly trusting the submitted values; every actual change is
permanently stored with the line as `correction_audit` (before/after,
who, when).

**Batch import**: the upload page allows selecting several PDFs at once.
Each file goes through preview → check → confirmation individually; the
browser automatically works through the queue as soon as one file has
been imported, and visibly marks files that are already imported or
faulty (states: waiting, ready, duplicate, error, imported). Server-side
this is not a special function — every file runs through the same
upload/validation/import flow as a single upload.

## Expected deliveries (goods receipt)

| Method | Path | Purpose |
|---|---|---|
| GET | `/wareneingaenge` | "Expected deliveries" page (any login) |
| GET | `/api/wareneingaenge` | Open (expected) deliveries of the active branch including lines; without an active branch (admin) all of them |
| POST | `/api/wareneingaenge/{id}/ankunft` | Confirm arrival: `{"mengen": {"<line id>": "<quantity>"}, "eingangsdatum": "YYYY-MM-DD"}`. Books the receipt, sets the receipt date (retroactively if needed), and closes the delivery once no line is open anymore. The response includes `mehrlieferungen`: for each line where more arrived than expected, the line id plus expected, arrived, and surplus quantity — it is booked regardless |

**Employees** may confirm too (D21) — this is warehouse work, not a
document privilege. Implausible quantities, foreign lines, or an already
fully arrived delivery result in HTTP 409, an invalid date HTTP 422;
nothing is booked in either case.

## Stock

| Method | Path | Purpose |
|---|---|---|
| GET | `/bestand` | "Stock" page (any login) |
| GET | `/api/bestand` | Stock per variant × storage location. Parameters: `lagerort_id` (the active branch if not given), `alle=true` (across all branches), `q` (brand, description, supplier item no., EAN), `nur_vorhanden` (default `true`, hides rows with quantity 0; the UI always sets it), `nur_negativ=true` (negative stock only), `reduktion` (50/70) with `reduktion_status` (`faellig`/`bald`, needs a branch; the same selection the overview counts under "Upcoming"), `artikel_von` (variant id; shows all sizes and colors of the same item, for the item detail page, 404 for an unknown id), `limit` (max. 500), and `offset`. Response: `zeilen` (rows; each row also has `hauptgruppe`, `artikel_id`, and `reduktion` with `empfehlung`/`manuell`/`wirksam`, `null` for external storage locations), `total`, `summe`, `gewaehlt`, `lagerorte`, `limit`, `offset`, `hat_mehr` |

**Any login may read all branches** (confirmed 2026-09-22) — even the
ones the account cannot switch to. An unknown `lagerort_id` results in
HTTP 404. Quantities come as text (`"5.00"`), never as a number; a
negative stock is shown, not hidden.

## Write-off

| Method | Path | Purpose |
|---|---|---|
| GET | `/ausbuchen` | "Write off" page (branch manager/head office) |
| GET | `/api/ausbuchen/stammdaten` | Storage locations that can be booked (`lagerorte`, own first), `lagerort_aktiv`, `gruende` (`verkauf` sale, `defekt` defective, `diebstahl` theft, `eigenbedarf` own use, `retoure` return, `sonstiges` other) |
| POST | `/api/ausbuchen` | Write off one piece. JSON: `grund`, exactly one of `ean` or `varianten_id`, `freitext` (required for `sonstiges`), `lagerort_id` (the active branch if not given). Response: `bewegung_id`, `typ`, `grund`, item data, `lagerort`, `bestand_vorher`, `bestand_nachher`, `bestand_reicht_nicht`. 409 for an unknown EAN/variant or unknown reason — nothing is booked then |
| GET | `/api/ausbuchungen` | Sales and removals, newest first. Parameters: `lagerort_id` (the active branch if not given), `alle=true`, `limit` (max. 200), `offset`. Per row: timestamp, item, storage location, reason, person (`benutzer_name`), `storniert` |
| POST | `/api/ausbuchen/{bewegung_id}/storno` | Reverse a write-off via a counter-booking (`korrektur`, `storno:<id>`); 409 if already reversed or not a write-off |

The reason `test` belongs to the temporary "−1" button on the stock
view and isn't listed in `gruende`.

## Delete item

| Method | Path | Purpose |
|---|---|---|
| DELETE | `/api/articles/{id}` | Fully remove a mis-entered item (variant id) — branch manager/head office only, only without a document (otherwise 409). Removes item, variants, prices, notes, manual goods-receipt lines, stock, and stock movements. `GET /api/articles/{id}/history` reports `product.manuell` for this |

`GET /api/articles` has a matching filter `nur_manuell=true` (items
without a document only).

## Correct

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/korrektur/gruende` | `gruende`: `inventur` (stock-take), `falsch_gebucht` (booked wrong), `gefunden` (found), `sonstiges` (other) |
| POST | `/api/korrektur` | Book a counted quantity. JSON: `varianten_id`, `lagerort_id` (the active branch if not given), `gezaehlt` (text, ≥ 0), `grund`, `freitext` (required for `sonstiges`). Response: `bestand_vorher`, `bestand_nachher`, `differenz`, `gebucht` (`false` if stock was already correct), `bewegung_id`. 409 for an invalid quantity, unknown reason, or unknown variant |

## Transfer

| Method | Path | Purpose |
|---|---|---|
| GET | `/umlagern` | "Transfer" page (branch manager/head office) |
| GET | `/api/umlagerung/stammdaten` | `quellen` (all storage locations), `ziele` (bookable targets, own first), `ziel_aktiv`, `heute`; per storage location `verkauf` |
| POST | `/api/umlagerung` | Book a transfer on receipt. JSON: `quelle_id`, `ziel_id` (the active branch if not given), `eingangsdatum` (optional, `YYYY-MM-DD`, not in the future; only determines where the clock starts), `positionen` (`varianten_id`, `menge` as text; identical variants are summed). Response: `quelle`, `ziel`, `positionen` (per variant, stock before/after and `uhr_start`), `fehlbestand`, `stueck`. 409 for the same source and target storage location, an invalid quantity, or an unknown variant — nothing is booked then |

## Manually entering goods (without a document)

| Method | Path | Purpose |
|---|---|---|
| GET | `/erfassen` | "Enter goods" page (any login) |
| GET | `/api/erfassen/stammdaten` | Selection lists: bookable storage locations (own first, D26), suppliers only as five groups (`id`, `gruppe`, `code` 111/333/444/555/999; 2026-09-24), POS categories (rule 8), today's date from the server |
| GET | `/api/erfassen/variante?ean=<ean>` | Lookup for the scanner: `{"gefunden": true, "variante": {…}}` with brand, description, color, size, unit, last UVP/EK, and the existing category as a suggestion; an unknown EAN gives `{"gefunden": false, "variante": null}` |
| POST | `/api/erfassen` | Book all lines as **one** goods receipt without a document (D27) |

Body of `POST /api/erfassen`:

```json
{
  "positionen": [
    {"marke": "Nike", "bezeichnung": "Poloshirt Court", "menge": "3", "uvp": "39.90",
     "ean": "4006632041234", "farbe": "Weiss", "groesse": "M", "einheit": "Stk",
     "lieferanten_artikelnr": "A1", "ek": "19.95", "kategorie_id": 3}
  ],
  "lagerort_id": 1,
  "lieferant_id": null,
  "eingangsdatum": "2026-09-21"
}
```

Only `marke`, `bezeichnung`, `menge`, and `uvp` are required (D23);
everything else may be missing (rule 5/10). `kategorie_id` sets the POS
category **only** if the item doesn't have one yet — an existing one
stays untouched; an unknown id results in HTTP 409 and books nothing.
Quantities and prices are **text**, so nothing goes through `float`
(commas are accepted). Unknown fields are rejected (HTTP 422). Without
`lagerort_id` the active branch applies; `eingangsdatum` defaults to
today if not given — in a storage location without sale it stays empty
(rule 6).

Response: `{"wareneingang_id": …, "lagerort": {…}, "positionen": 2,
"neue_varianten": 1, "bekannte_varianten": 1, "eingangsdatum": "2026-09-21"}`.

**Employees** may enter goods too (rule 9/D21) — no document is created.
Implausible input (a missing required field, quantity ≤ 0, invalid EAN,
date in the future) results in HTTP 409 and books **nothing**; a
storage location without access results in HTTP 403, an invalid date
format HTTP 422.

## EAN and labels

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/varianten/{id}/ean` | Set the EAN: `{"generieren": true}` generates an internal EAN-13 (GS1 20–29, D24); `{"ean": "4006381333931"}` records an existing one (format **and** check digit are checked) |
| GET | `/api/varianten/{id}/etikett` | What would be on the label (preview for the UI), plus selection lists for size and markdown; `rolle` says which pre-printed roll to load (`{"prozent": 50, "farbe": "rot"}`), parameter `reduktion` as with the PDF |
| GET | `/api/varianten/{id}/etikett.pdf` | Label as a PDF in label size. Parameters: `groesse` (only `47x83`, the pre-printed roll), `reduktion` (0/30/50/70, determines the roll), `anzahl` (1–100), `muster=true` also draws the pre-print for preview |
| GET | `/api/wareneingaenge/{id}/etiketten.pdf` | All labels of a goods receipt — `je_stueck=true` (default) prints one per piece, otherwise one per line |
| GET | `/api/artikel/{artikel_id}/etiketten.pdf` | Markdown printing (Phase D): one label per piece in the branch's stock, for all colors and sizes of the item. Parameters `reduktion` (determines the roll), `lagerort_id` (the active branch if not given). 404 without stock |
| GET | `/runterschreiben` | Markdowns page (Phase D): due list, confirmation, manual level, label printing |
| GET | `/api/reduktionen` | Markdown printing (Phase D): items of a branch (`lagerort_id`, otherwise the active one) that have reached −70%/−50% (`stand: faellig`) or will in 30 days (`bald`), each with `stufe`, `rolle`, `stueck`, `varianten`, `eingang`; plus the selectable branches and `manuell` (the branch's manually chosen levels with `prozent`, `gesetzt_von`, `gesetzt_am`) |
| GET | `/api/articles/{varianten_id}/reduktion` | Per branch with sale: `empfehlung` (rule 6), `manuell` (30/50/70 or `null`), `wirksam`, `darf_aendern` (own branch, as for entry/correction) |
| PUT | `/api/reduktion/manuell` | Set the level manually: `varianten_id`, `lagerort_id`, `prozent` (30/50/70, otherwise 422). All roles; employees only in assigned branches (403); external storage locations 409. Response: `empfehlung`, `manuell`, `wirksam` |
| DELETE | `/api/reduktion/manuell?varianten_id=&lagerort_id=` | Revert to the recommendation; same rights |

Both PDF responses come as `application/pdf` with `Content-Disposition:
inline`, one page per label; the page size is the label size, so the
printer doesn't scale anything.

Model year and markdown suggestion come from the last goods receipt **at
the branch in question** (rule 6): from the active branch for a single
label, from the goods receipt's own branch for a goods receipt. An
existing EAN is never overwritten (HTTP 409), a wrong check digit is
likewise rejected; an unknown variant results in HTTP 404, an unknown
size or markdown level HTTP 422. **Employees** may do both too (rule 9)
— no document is created.

## Statistics (2026-09-25)

Branch manager/head office only. `GET /statistiken` (page),
`GET /api/statistik?zeitraum=tag|woche|monat|jahr|gesamt&lagerort_id=`
(optional; all branches if none given). Response: `zeitraum` (start/end),
`kategorien` (pieces sold per POS category), `einnahmen_geschaetzt` +
`einnahmen_ist_schaetzung: true`, `bestellempfehlung` (top-10 best-selling
items with current stock), `lagerorte` (branch selection). The revenue
estimate uses the UVP and the markdown automatically due at the
respective time of sale (`app/services/statistik.py`); a manually chosen
markdown has no history and isn't included.

## Account management (2026-09-25)

Head office only (`admin`). `GET /konten` (page), `GET /api/konten`
(list), `POST /api/konten` (`kassennummer`, `name`, `role`, optional
`password`, `lagerort_ids`), `DELETE /api/konten/{id}`. Deleting removes
the account and its branch assignments; past bookings stay unchanged
(they store name/till number as a snapshot). Head office cannot delete
itself (`409`).

## Phase D — open questions (2026-09-25)

- **D-F1 Confirm:** `POST /api/reduktionen/bestaetigen` (`artikel_id`,
  `lagerort_id`, `stufe`) — same rights as manual markdown. The model
  disappears from the due list (`GET /api/reduktionen`) until the next
  level becomes due.
- **D-F2 Hints:** `GET /api/dashboard` additionally returns `hinweise`
  (new delivery on stock already marked down, only with an active
  branch). No dedicated endpoints to create these — they arise
  automatically when booking a delivery (import or arrival confirmation).
- **D-F3 Head-office recommendation:** page `GET /empfehlungen` and
  `GET/POST /api/empfehlungen` (head office only; list, or set with
  `artikel_id`, `lagerort_id`, `prozent`, `ab_datum`; unknown item or
  location 404, invalid level 422) and `POST /api/empfehlungen/{id}/antwort`
  (`status`: `uebernommen`/`abgelehnt`, `grund` required on rejection;
  same rights as manual markdown). `GET /api/reduktionen` additionally
  returns `empfehlungen` (open ones, for the active branch).

## Phone pages (2026-09-28)

A login from a phone (user agent `iPhone|iPod|Mobi|Windows Phone`) sets
the session flag `phone`. The dependency `phone_gate`
(`app/routers/auth.py`), registered for every route, then allows only
the pages under `/m` and the API calls listed in `PHONE_ROUTES`
(`app/core/handy.py`). Anything else: page requests redirect (303) to
`/m`, API calls get **403** with the translated message
`errors.phone.not_available`. The flag survives "Request desktop site".
Tablets are not matched and keep the desktop version. Roles and branch
limits apply on top, unchanged.

| Method | Path | Purpose |
|---|---|---|
| GET | `/m` | Phone home screen: large tiles per role, installable as home-screen app |
| GET | `/m/suche` | Article search and scan: price, sizes/colours, stock per location, reduction level |
| GET | `/m/zaehlen` | Count and correct stock in the active branch (books only the difference) |
| GET | `/m/lieferungen` | Confirm arrival of expected deliveries, partial or full (everyone, D21) |
| GET | `/m/umlagern` | 🔒 Transfer between locations |
| GET | `/m/ausbuchen` | 🔒 Write off a sale or removal (cancelling stays desktop-only) |
| GET | `/m/erfassen` | Manual goods entry without a document (label printing stays desktop-only) |
| GET | `/m/runterschreiben` | Due markdowns, "done" confirmation, manual 30/50/70 % |

Allowed APIs for phones: login/logout, `/api/me`, `/api/active-lagerort`,
`/api/language`, `/api/articles`, `/api/bestand`, article prices and
reduction, `/api/korrektur` (+ `gruende`), `/api/wareneingaenge` and
`.../{id}/ankunft`, `/api/umlagerung` (+ `stammdaten`), `/api/ausbuchen`
(+ `stammdaten`), `/api/erfassen` (+ `stammdaten`, `variante`),
`/api/reduktion/manuell` (PUT/DELETE), `/api/reduktionen` (+
`bestaetigen`), `/api/dashboard`. The phone pages use exactly these
desktop APIs — there is no separate phone API.

## Miscellaneous

| Method | Path | Purpose |
|---|---|---|
| GET | `/db-test` | Health check: verifies the database connection is up (no auth needed; used by the Docker healthcheck) |
| GET | `/static/{path}` | Static files: `css/`, `js/`, `fonts/`, `img/` |
| GET | `/docs`, `/redoc`, `/openapi.json` | Automatically generated FastAPI documentation (Swagger/ReDoc) |

## Error format

JSON error responses follow the FastAPI standard
`{"detail": "<message>"}`, localized as described at the top (a few
older messages are still German-only). Typical status codes: `400` (e.g.
import without a chosen branch), `401` (not logged in), `403` (wrong
role, no branch assignment, or a function not available on phones),
`404` (invoice/item/note not found), `409` (import rejected, e.g.
duplicate or hash conflict; the note was changed in the meantime; own
account deletion), `413` (file too large), `422` (PDF could not be
read/parsed, or invalid data), `429` (login locked, S2), `503` (database
unreachable).


## Booking rights as of 2026-09-24

Employees may manually book in and correct stock, but only in their
assigned branches. Booking out a sale/removal, cancelling, and
transferring are reserved for branch managers and head office. Their
existing cross-branch booking rights remain in place; read rights are
unchanged.

`/ausbuchen`, `/api/ausbuchen/stammdaten`, `POST /api/ausbuchen`,
`POST /api/ausbuchen/{id}/storno`, as well as `/umlagern` and all
`/api/umlagerung` endpoints require branch manager/head office. The
write-off list (`GET /api/ausbuchungen`) stays readable for everyone.
`GET /api/erfassen/stammdaten` offers employees only their assigned
branches; entry/correction also enforce this boundary server-side.
`GET /api/bestand` additionally returns `rechte.ausbuchen` and
`rechte.korrektur_lagerorte`, which determine which actions are shown.
