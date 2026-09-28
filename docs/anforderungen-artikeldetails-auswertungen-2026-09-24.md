# Item details and reports – inbox from 2026-09-24

## Binding priority – 2026-09-24

Fabian has decided: **First implement the new requests from the inbox, then continue phase D.** The already-built markdown page stays as-is; this neither resets phase D nor marks it as complete.

Priority goes to the entire new requirements catalog "Item details and reports": clean up item details, simplify lists and workflows, personalize the overview and quick access, add statistics and account management. The explicitly requested manual markdowns (all staff, per branch, 30/50/70%, selection via EAN or stock list, shown in item details and stock) also belong to this pulled-forward package, even though they technically touch phase D.

Only after that come the remaining phase D work and open decisions. Mobile usage stays planned for the end of the project, as agreed. Required checks before store deployment remain in place. This is a priority decision, not a confirmation of implementation.

Requirements catalog: [Item details and reports](anforderungen-artikeldetails-auswertungen-2026-09-24.md).


Status: requirements consolidated; no code change from this sync. Existing open changes in the project come from other work and remain untouched.

## Requirements

1. **Item details:** Only open the POS category via "Edit" next to the item name; don't show the box by default.
2. **Item details:** Only open EAN and label details via a small button; don't show the box by default.
3. **Item details:** Show RRP history at the top, more compact; the associated small list is expandable, closed initially.
4. **Item details:** Remove item notes from the UI. This decides nothing about deleting existing notes data.
5. **Item details:** Show the lower list as this item's current stock across all sizes and colors.
6. **Item details:** Place "Delete item," with red warning text, at the very bottom; keep existing deletion rights and restrictions.
7. **Markdown:** Show the current markdown recommendation in item details, allow manual adjustment by all staff per branch to 30/50/70%, and show it immediately in stock.
8. **Recent activity:** Summarize delivery arrivals as a whole delivery; show transfers and removals with a reason other than sale, not every single receipt/removal individually.
9. **Statistics:** New statistics page for branch managers and head office only: quantities sold by category, revenue explicitly shown as an estimate based on the reduced sale price at the time, and hints on well-selling items/reorder needs; daily, weekly, monthly, yearly, and all-time view, with easy-to-read charts. Further metrics may be proposed during planning.
10. **Stock:** Link item names to their item detail page.
11. **Stock:** Show the markdown stage in the stock list; not required in the item search list.
12. **Markdown:** Allow manual item selection both via EAN and via the stock list.
13. **User management:** Head office should be able to add and delete employee and branch-manager accounts. How historical bookings are handled technically on deletion is still to be defined.
14. **Overview:** Store five quick-access shortcuts per user, freely selectable and sortable via drag-and-drop. All buttons the same height, based on the tallest needed content.
15. **Item search:** Align the list visually with stock; category first, merge brand and description, merge supplier item number and EAN.
16. **Write off:** Besides EAN entry, offer a stock list to browse and select from; keep existing write-off rights.
17. **Enter:** Restrict the supplier picker to five groups: 111 Intersport, 333 Retailer, 444 In-house, 555 ECOM, 999 Third-party retailer. No individual brand suppliers in this picker.

## Confirmed answers from 2026-09-24

- **Revenue:** Before the till connection, calculate as estimated revenue from items written off as "sale" and their reduced sale price at the time; show it explicitly as an estimate. Never equate it with actual till revenue.
- **Manual markdown:** All staff may switch between **30%, 50%, and 70%** per branch. This decision doesn't extend the existing branch assignments; no free-form percentages. Treat the recommendation and the manually chosen stage separately; stock shows the effective stage.
- **Quick access:** Store five functions and their order **per user**.

- **Delete account (point 13, answered on the evening of 2026-09-24):** All bookings stay in the database. The user's name stays on the old bookings, but no account is linked to it anymore.

The three follow-up questions are answered. Requirements not yet implemented; this task concerns documentation only.

## References

Original wording and screenshots are stored locally in the vault Main under `01 Projekte/Sportfabrik Inventory/Sportfabrik Inventory – Artikeldetails und Auswertungen.md`. No private screenshots copied into the repository.
