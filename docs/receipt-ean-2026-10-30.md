# Receipt EAN prerequisite — 30 October 2026

## Confirmed scope

Fabian approved implementation after reading the server work plan. Only positively submitted quantities need EANs; other future partial deliveries may remain open. Internal generated EANs are permitted after manual confirmation. A later original EAN supplements the same unambiguous variant rather than replacing its internal label. Articles without EANs remain in the master and as open goods receipts.

The boundary for transfers, return/release, positive corrections and cancellation reversals remains undecided. Those paths, existing stock and historical movement records are unchanged. This task does not deploy, merge main, clean up real inventory or validate a physical POS.

## Implemented behavior

- Direct invoice/delivery import and manual desktop/phone entry resolve and save item masters, prices and original source snapshots first. If any positively submitted variant lacks an eligible identifier, the whole submitted batch is retained as expected receipt(s), with no stock movements, received quantities, arrival dates, delivery-date changes or receipt markdown changes.
- The caller receives `receipt_blocked` and `missing_eans`. The UI says that items were saved without stock. Manual entry links to the existing receipts page. Document import retains the pending result instead of navigating away as though stock had been booked.
- Expected receipt confirmation preflights the complete submitted positive quantities before mutations. It rejects mixed invalid submissions atomically; omitted or zero future quantities do not block a valid partial receipt. Existing transaction locks, permissions and operation-ID retries remain in place.
- Desktop receipt rows link to the existing item details/EAN tools. Missing identifiers include description, colour and size. Phone receipts now render manual records without a document and give computer correction guidance; phone EAN-edit permissions remain unchanged. Failed submissions keep the quantity inputs, so a second operator can correct identifiers and staff can submit again.
- Internal EAN generation has an explicit translated confirmation dialog. Cancellation of the dialog makes no assignment. The existing primary/additional-EAN services retain identifiers, check manual/additional EAN check digits and protect ownership. Later original EANs from import/manual entry can supplement a unique internal variant. Ambiguous missing/internal identity matches are rejected. Distinct manufacturer EANs keep the existing separate-variant behavior where supplier colour/size is absent.
- Supplier identifiers preserve the existing format rule: 8/12/13/14 ASCII digits. This task does not retroactively impose check-digit validation on all supplier identifiers or alter existing stock. Newly assigned manual/additional identifiers use the existing stricter validator.
- A deferred manual markdown remains in the original input snapshot and is applied on that row's first actual receipt at a sales location. Receipt dates are chosen when goods are actually booked; the original requested date remains in the audit snapshot.
- Cancelled-document replacement passes the same import guard; replacing a document does not bypass EAN requirements. No schema migration or mandatory EAN column was introduced.

## Verification

Verification is performed using synthetic documents, isolated in-memory SQLite databases and the actual app endpoints. The initial two new regression cases failed on the previous implementation before code changes. Existing tests that expected stock without EAN were changed to confirm EANs and receive the retained delivery, or to supply identifiers when stock is the purpose of the fixture.

Final verification: `DATABASE_URL=sqlite:// .venv/bin/pytest -q` with the local test-tool directory on PATH: **390 passed, 16 skipped**, one upstream Starlette deprecation warning, 140.04 seconds. The skipped cases remain optional unavailable checks; no private document fixtures were supplied. This includes both Chromium browser cases and JavaScript syntax/behavior checks. The focused receipt tests passed independently (11 cases). `git diff --check`, translation-key coverage and both overview addenda checks passed. PostgreSQL, production and physical phone/POS hardware were not tested. No migration was introduced.

The optional Chromium tests serve the app entirely through the isolated TestClient, without a listening server. They exercise desktop and narrow phone pages with real phone session restrictions, a mixed blocked receipt, retained quantities, EAN correction and successful receipt; desktop also cancels/accepts internal-EAN confirmation. Full Chromium mobile/touch emulation had scroll-coordinate/pointer interception problems. The passing responsive phone check uses a narrow viewport and phone user-agent/session with desktop layout-viewport emulation. Physical phone touch behavior, Sato labels, till/scanner acceptance and production/PostgreSQL are not verified by these checks.

## Documentation and environment

Working directory: `/home/sfadmin/projects/sportfabrik-inventory`, branch `working/entwicklung`, starting head after clean fast-forward `c0b0864`. Existing Git history provides source recovery. The push guard was installed. The development virtual environment and browser runtime were absent; Python venv support and missing Chromium shared libraries were installed, then dependencies, optional Playwright/Chromium and test tools were installed locally. No application service restart was needed.

Updated repository working rules, orientation, architecture, API, phone documentation, context and both HTML overviews. The HTML copies incorporate the existing vault preparation section and a repository-only implementation addendum. The explicit chat instruction forbids vault edits, so the vault notes and HTML originals were only read; no claim of complete vault synchronization is made. The automatic conversation archive can capture the confirmed decisions and results.

## Remaining work

Decide the EAN boundary for other stock increases and reversals. Verify physical phone/till/scanner workflows and, when separately authorized, prepare a production release. Later packages remain complementary document matching, history/replacement UI, the SF1 pilot and historical price snapshots/reporting. Missing quantities versus genuine zero-quantity catalogues are part of that later document workflow, not changed here.


## Later PostgreSQL verification during development deployment

The separately authorized homeserver development instance subsequently passed a focused receiving smoke check on an isolated temporary PostgreSQL 18 database, including atomic rejection and retry behavior. This supplements the original SQLite/browser evidence; it does not establish full PostgreSQL concurrency or physical POS acceptance. See [development-instance.md](development-instance.md). Production remained unchanged.

## Bulk internal EANs from receiving — 30 October 2026

Desktop receiving provides “Generate all required EANs” per open supplier/manual receipt. An explicit confirmation precedes assignment. Only variants on this receipt with a positive entered arrival quantity are selected; existing eligible identifiers are retained, repeated requests are harmless, and collisions roll back the complete assignment. Invalid existing identifiers require manual review. Existing receipt location permissions apply; phone restrictions and transfer behavior stay unchanged.

The operation uses the shared transaction lock and creates no stock, arrival quantities or dates. Receiving inputs and the selected date remain visible after refreshing identifiers. Arrival remains a separate explicit action. Imported documents in the preview queue link directly to receiving, including orders saved without stock. No schema migration is required.

Bulk verification: initial endpoint regression tests failed before implementation. Scope/permissions, repeated requests, no stock/date/quantity changes and atomic collision rollback pass. Chromium confirms dialog cancellation/acceptance, retained partial quantity/date and separate successful arrival. Full SQLite suite: **369 passed, 41 skipped** (Node absent from the initial PATH); all **34** operating/frontend checks then passed with the existing Playwright Node runtime on PATH. The three focused bulk cases passed separately after strengthening the rollback fixture. No private document fixture was used.

The owner requested continued work in the separate development app. Its winter order was already imported as four expected receipts; aggregate inspection found 237 variants without primary EANs and zero stock movements before this update. The development app alone was rebuilt/recreated; the previous image is retained as `sportfabrik-inventory-dev:before-bulk-ean-20261030`. Database health and HTTPS asset hash match were verified; unauthenticated access to the new endpoint returned 401. No real EANs or stock were assigned during verification. No migrations or production updates were performed.


## Undo accidental internal labels and separate winter brands — 30 October 2026

The receiving page also provides a confirmed “Delete internal EANs” action for variants with positive entered arrival quantities. The request includes the displayed variant IDs and exact identifiers to prevent stale requests from removing a changed number. Only the system's deterministic primary internal number, still marked internal, can be removed. Manufacturer/additional EANs remain. The shared transaction lock protects the complete operation; any affected variant with historical stock movements rejects the entire batch. Scope, open supplier/manual receipt checks, location permissions and computer-only access match bulk generation. Repeated removal of an already missing primary is harmless. The dialog explains that the item master is shared across branches and printed labels must no longer be used. Quantities and dates remain intact; receiving without a replacement identifier is blocked again.

The winter plan parser now removes the leading brand from the description and recognizes the known multiword brand Body Glove. Full original supplier/article identifiers, raw source lines, document number/hash, prices and quantities remain unchanged. This parser change applies to newly parsed input; existing imported master descriptions are not automatically rewritten.

Verification for this follow-up: four initial parser/removal regressions failed before implementation. Focused parser/receipt tests: 20 passed. Chromium and frontend/operating checks: 37 passed, including cancelled/accepted removal, retained partial quantity/date, blocked receipt after deletion, regeneration and successful receipt. The full SQLite suite with the existing Node runtime on PATH passed: **397 passed, 16 skipped**, one upstream deprecation warning. Removal tests also verify location permissions, stale values, original/additional EAN preservation, repeat requests and atomic rejection when a variant has already been booked.

The separate development app was updated; running parser and HTTPS JavaScript hashes match the checked source, database health passed and unauthenticated removal returned 401. Recovery image: `sportfabrik-inventory-dev:before-ean-undo-20261030`. No real identifiers, article names or stock were modified by these checks. Existing imported names require a separately scoped cleanup if desired. No migration or production update was performed. No private PDF was needed for tests.
