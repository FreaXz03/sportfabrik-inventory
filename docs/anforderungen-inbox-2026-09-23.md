# Requirements from the Obsidian inbox – 2026-09-23

Status: business requirements, no implementation implied by this documentation sync.

- Unify the header across all pages.
- Clean up item search and simplify it for users without PC experience.
- Auto-focus the EAN search field when the item page opens.
- Show size and color in separate columns in the stock view, plus the main group.
- Make the overview more polished: statistics, upcoming events, and recent activity.
- Remove items with quantity 0 from the stock view; keep them in the item master.
- Show write-offs as a list with timestamp, person who performed it, and reason.
- List manually, individually imported items; plan the requested full deletion and clarify how to handle history.
- Make items in the master deletable only by branch managers; clarify the conflict with permanent master retention before implementation.
- Add parsers for all sample documents in the vault; see the local document collection in the Obsidian vault.
- Apply usability and good readability throughout, for staff with glasses or little PC experience.
- Implement supplier groups and codes per the table below and print the codes on labels.

## Business specifications

Usability is a central project requirement: staff with glasses and/or little PC experience should be able to use the system easily. Good readability, clear navigation, and few, clear search parameters matter accordingly.

| Supplier group | Label code | Meaning |
| --- | --- | --- |
| Intersport | 111 | Direct order from Intersport |
| ECOM | 555 | Online shop returns from the Intersport shop |
| Retailer | 333 | Local sales shops that no longer need the items |
| Third-party retailer | 999 | Direct orders from brands, e.g. Puma, Alpina, Columbia, Salomon; the in-house brands listed below are excluded |
| In-house | 444 | Direct orders exclusively from Nike, Adidas, and Northface |

Label size reconfirmed: **8.4 cm × 4.7 cm = 84 × 47 mm**. No further change needed.

Desired behavior at quantity 0: remove the item from the stock view, keep it in the master. Separate request: make manually imported items fully deletable and restrict general deletion in the master to branch managers. **Open business question:** how should full deletion work when documents and stock movements already exist for the item? This conflicts with the existing rule "the item master stays forever"; no deletion strategy has been defined yet.


Sources in the local Obsidian vault Main: `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory – Anforderungen vom 23.09.2026.md` and `03 Ressourcen/Bilder Kassensystem Sportfabrik.md` (eight screenshots). Originals stay local in the vault; no images or documents copied into the repository.

## Implementation

- **Supplier groups and codes** (2026-09-24): group = `lieferanten.typ`, code derived from it (`app/core/lieferanten.py`), shown bold to the right of the supplier on the label and in the supplier picker during entry. One supplier per group for manual goods. **Limitation:** ECOM returns arrive in the Intersport layout and are still assigned by the parser to supplier INTERSPORT (code 111), until the parser recognizes them (reference "ret.Ecom").
- **Stock view** (2026-09-24): color and size in their own columns, plus the main group (untranslated, as in the till). Rows with quantity 0 no longer appear, the toggle for it is gone; booking a row down to 0 makes it disappear immediately. The item stays in the master, a negative stock figure stays visible.
- **List of write-offs** (2026-09-24): on the "Write off" page, all sales and removals from the journal, newest first, with time, item, branch, reason, and person; filterable by branch, with "Undo". API `GET /api/ausbuchungen`.
- **Item search** (2026-09-24): only two large fields at the top — "Scan EAN" (active on open, scan + Enter searches immediately and re-arms the field for the next scan) and "Quick search"; brand, supplier item number, description, category, and delivery date sit under "More filters".
- **Overview** (2026-09-24): greeting with branch and date, large quick-access buttons (write off, enter, transfer, deliveries, upload document), key figures for the active branch (units in stock, sold today), "Upcoming" (announced deliveries, negative stock to count, items aged into −50%/−70% or within the next 30 days, items without a category, variants without an EAN), and "Recent activity" (latest bookings with person). Service `app/services/uebersicht.py`.

## Decision of 2026-09-24 on item deletion

Deletion is mainly needed for **manually entered** items: if someone enters an item wrong, someone needs to be able to remove it again. Implementation:

- Only **branch managers and head office** may delete.
- An item can only be deleted if **no document** is attached to it (all its goods receipts are manual entries without a document). Items from documents stay in the master (rule 4) — there you correct the document, or delete the document.
- Deleting an item removes the item, variants, prices, notes, the manual goods-receipt lines, stock, and the associated stock movements — the mis-entry should leave no trace in stock. This is a deliberate exception to rule 2, only for this case; the action is logged (who, when, which item).
- **Implemented** (2026-09-24): "Delete item" button on the item page (branch manager/head office only, with a confirmation prompt), `DELETE /api/articles/{id}`, `app/services/artikel_loeschen.py`. In item search, under "More filters", the checkbox "Manually entered only" (`nur_manuell=true`). Items from documents show a note instead.
