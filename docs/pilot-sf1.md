# SF1 operating pilot — plan and checklists (package 3, prepared 2026-10-01)

Goal (roadmap): **one branch (SF1) reconciles a real working day** — receipts,
sales, returns, transfers and closing counts — **and a restore works.** The other
three branches do **not** start on the migrated balances. Those are historic
receipts without sales, not a starting balance.

Decided (2026-10-01): pilot branch **SF1**; staff **scan every sold item in the
app** in addition to the till (Q6); **Fabian reconciles the app against the till
report daily**; **no data loss**, **downtime of a few hours** is acceptable with
paper notes (Q7).

Status: the code side is done (cancel instead of delete, delivery linking, retry
protection, stale-count check, reports below). What remains is on site, and a few
open decisions. Everything marked ☐ is still to do.

## Open decisions

| # | Decision | Needed from | Default if nobody decides |
|---|---|---|---|
| D1 | Second machine for WAL archiving (what, where, who looks after it) | Fabian / IT | pilot cannot claim "no data loss" — only nightly backups (up to a day) |
| D2 | Archive original PDFs in the app (see `ausfallsicherheit.md`) | Fabian | PDFs not stored; originals stay in mail/paper |
| D3 | Network separation: how is the guest Wi-Fi kept away from the server (VLAN / separate router / firewall) and who configures it | IT | **blocker** — the 6-character password rule depends on it (`sicherheit.md`, S2) |
| D4 | Who looks at `systemctl --failed` / backup status each morning | Fabian | nobody → backups can fail silently |
| D5 | Pilot start date and the closing-count sample (see "Pilot day") | Fabian | — |
| D6 | Remote access for branch managers (VPN) | later | not part of the pilot; store network only |

## 1. On site tomorrow — what only you can do

☐ **Server and network** (answers D3, feeds the setup below)
  - What hardware will be the store server? Is it on, reachable, with Docker
    available? (If not, a PC with Docker is a fine pilot stand-in — see
    `SERVER-SETUP.md`, "Test locally".)
  - Which router/switch exists? Can the guest Wi-Fi be put on its own network?
    Write down: device model, who has the admin login, store Wi-Fi name.
  - Fix the server's address: a reserved IP for the server in the router. This is
    `APP_HOST` (exactly what people type; changing it issues a new certificate).

☐ **Phones with real labels** (iPhone + Android)
  1. Server running and `https://APP_HOST` reachable from the store Wi-Fi.
  2. Trust the root certificate on one iPhone and one Android phone
     (`SERVER-SETUP.md`, "Trust the root certificate"). Compare the fingerprint first.
  3. Log in with a till number, open `/m`, allow the camera.
  4. Scan 10 real labels each (different brands, small and large codes, dim
     light): `/m/ausbuchen` (a sale), `/m/zaehlen` (count). Note every label that
     does not scan.
  5. Check the new safeguards on the phone: turn Wi-Fi off right after tapping
     "book" on a sale, then turn it on and tap again — the stock must go down by
     **one**, not two. In `/m/zaehlen` count an item, let a colleague sell one of
     it meanwhile, then book — you must get the "stock has changed" warning.

☐ **Hardware scanner on a PC** — in `/ausbuchen` the scan field must accept the
  scanner (it types the EAN plus Enter). Scan 10 labels, including one internal
  EAN (starts 20–29).

☐ **Label printer (Sato CL4NX Plus)** — print a test label for an item with an
  internal EAN (the app produces the PDF at label size), then scan the printed
  label with phone and scanner. Note the label size and the roll used.

☐ **Staff and rights** — list the SF1 accounts to create: till number, name,
  role (employee/branch manager). Employees: stock, count, sales only; transfers,
  other write-offs, cancelling, documents: branch manager or head office.

☐ **Opening-count preparation** — decide when SF1 is counted (outside opening
  hours if possible), who counts, how many phones/people, and which areas
  (shelves/zones) so nothing is counted twice.

☐ **Paper** — print the outage sheet (section 5) and the reconciliation sheet
  (section 4) and put them at the till. A pen on a string.

Write findings into this file (section 8) or a note; they decide what is built next.

## 2. Server setup (server admin; follows `SERVER-SETUP.md`)

☐ Docker Engine + Compose; user `sportfabrik` in group `docker`; project in `/opt/sportfabrik-inventory`
☐ `.env.server` (`chmod 600`): `POSTGRES_PASSWORD`, `SESSION_SECRET`, `APP_HOST`, `APP_BIND_IP` = the server's LAN IP
☐ `docker compose --env-file .env.server up -d --build`; `ps` shows `db`, `app`, `proxy` healthy
☐ **Firewall:** allow 443/80 only from the store network; deny from the guest network; no internet port forwarding (D3)
☐ Accounts: `scripts/manage_users.py add-chef …` / `add-mitarbeiter …` (assign SF1)
☐ Export the Caddy CA once and store it with the backup key: `docker compose --env-file .env.server cp proxy:/data ./caddy-data-export` (then encrypt with `age`; losing it means every device must trust a new root)
☐ `pip-audit -r requirements-server.txt` before go-live; S8 hash pins: on a machine with Python 3.13 run `pip-compile --generate-hashes requirements-server.txt -o requirements-server.lock`, switch the Dockerfile to `pip install --require-hashes -r requirements-server.lock`, rebuild and run the tests (open, `sicherheit.md`)
☐ Backups: install the timers (`ausfallsicherheit.md`), run the first backup by hand
☐ **Restore drill** passed once, result entered in `ausfallsicherheit.md`
☐ D1: WAL archiving to the second machine, rehearsed (point-in-time restore) — or the pilot is explicitly run with "up to one day" and Fabian accepts that in writing

## 3. Opening count for SF1 (stock starting point)

The migrated quantities are **not** a starting balance. Before the pilot every
SF1 stock line is counted once; sales and counts from then on are trusted.

1. **Mark the start:** note the date and time, e.g. `2026-10-05 06:30`. Everything
   counted from then on counts for the opening count.
2. **Count with the phones** (`/m/zaehlen`, reason "Inventur / Zählung"): scan or
   search the item, enter the quantity on the shelf, book. A count without
   difference is recorded too ("counted, no difference").
3. If the shop is open while counting, the stale-count check protects you: when
   a sale happened meanwhile the app says so and books nothing — count again.
4. **Progress**, any time, on the server:
   ```sh
   docker compose --env-file .env.server exec -T app python scripts/betrieb.py zaehlstatus SF1 --seit "2026-10-05 06:30"
   docker compose --env-file .env.server exec -T app python scripts/betrieb.py zaehlstatus SF1 --seit "2026-10-05 06:30" --liste
   ```
   `--liste` prints every line with stock in the system that was **not** counted
   yet: either it is somewhere in the shop and still to count, or it is not
   there — then count it as 0.
5. **Items found in the shop that the system does not know:** enter them by hand
   (`/erfassen`, branch SF1) first, then count.
6. **Done when:** `zaehlstatus` shows 0 open (or each remaining line was looked
   at on purpose and counted as 0), and the stock check is clean:
   ```sh
   docker compose --env-file .env.server exec -T app python scripts/betrieb.py pruefe SF1
   ```
   Fabian signs off with date and time. Record it in section 8.
7. From now on, the other branches keep their migrated balances and are treated
   as **unverified** until they have their own opening count.

## 4. Pilot day — daily routine and reconciliation

**Morning (before opening):** `systemctl --failed` shows nothing; the 06:15 check
passed (stock = sum of movements, newest backup < 26 h) — or run
`scripts/betrieb.py pruefe` and `scripts/check_backup_age.sh` by hand.

**During the day:**
- Every sold item is scanned in the app (`/m/ausbuchen`, reason "verkauf"), in
  addition to the till. One tap = one piece; a wrong scan is cancelled by a branch
  manager (`/ausbuchen`, "Cancel").
- Deliveries: documents are uploaded by branch managers; the delivery note
  attaches to the delivery already expected, the invoice later attaches to it too
  (the preview asks); arrival is confirmed on `/m/lieferungen` after unpacking.
- Customer returns: for now by hand — put the item aside, **note it on the paper
  sheet**, do not put it back on the shelf. (Since 2026-10-05 returns can be booked on `/retouren`: fit/taste goes into inspection, other reasons wait for the branch manager. Decide with Fabian whether SF1 uses it from day one.)
- Transfers: dispatched on `/m/umlagern`, confirmed at the destination.

**Evening — reconciliation (Fabian):**
1. Export the day:
   ```sh
   docker compose --env-file .env.server exec -T app python scripts/betrieb.py tagesabschluss SF1 > abschluss-2026-10-05.csv
   ```
   One row per kind and item: `verkauf` (net of cancelled scans), `ausbuchung`
   (other write-offs with the reason), `korrektur` (counts that changed stock),
   `zugang`, `umlagerung`. The summary line on the screen gives the total pieces sold.
2. Compare the `verkauf` rows with the **till report** for the same day:
   total pieces first, then per item.
3. For every difference decide and write down (sheet below): forgotten scan →
   book it now with the right reason and note the late booking; double scan →
   cancel; wrong item scanned → cancel and book the right one; return not noted →
   check the paper sheet.
4. Run `scripts/betrieb.py pruefe SF1` — must say OK.

**Reconciliation sheet** (one line per difference):

| Date | Item / EAN | Till | App | Cause | Action | Who |
|---|---|---|---|---|---|---|
| | | | | | | |

**Closing count (sample):** at the end of the pilot day count a sample — suggest
the 20 fastest sellers plus 10 random lines (D5) — with `/m/zaehlen`. The
difference per line must be explained or ≤ the agreed tolerance (Fabian sets it).

**Pilot acceptance (roadmap):** one real day of receipts, sales, returns and
transfers reconciles with the till, the sample count reconciles, and the restore
drill passed. If not, list the causes (section 8) — they become the fixes before
other branches start.

## 5. Outage procedure (print this page)

**When:** the app does not load, bookings fail, or the server is off.

**Staff (any time):**
1. Keep selling at the till as usual. The till is the source for sales.
2. Write every sold, written-off, received or transferred piece on the **outage
   sheet**: time, item (EAN or description + size/colour), quantity, what
   (sale / write-off + reason / receipt / transfer), your name.
3. Do not scan again later "to be safe" before the system is back — book from the
   sheet in step 6, so nothing is booked twice.
4. Tell the branch manager. Branch manager calls the IT contact: ______________.

**IT:**
1. `docker compose --env-file .env.server ps` and `… logs --tail=100 app`.
2. Database down or disk full: free space / restart the service. Data corrupt or
   server dead: restore (`ausfallsicherheit.md`, restore drill procedure, but into
   the live stack), then bring the app up. Accepted downtime: a few hours.
3. After it is up: `scripts/betrieb.py pruefe` must say OK.

**After recovery (branch manager):**
5. Announce "system is back".
6. Book the outage sheet: sales on `/m/ausbuchen` (reason "verkauf"), others with
   their reasons, receipts via the delivery list or `/erfassen`. Tick each line on
   the sheet when booked. Late bookings carry the booking time of today, so the
   daily report for the outage day will differ from the till — note the outage on
   the reconciliation sheet.
7. Reconcile that day as usual (section 4).

**Outage sheet:**

| Time | Item (EAN / description, size) | Qty | What (sale / write-off + reason / receipt / transfer) | Name | Booked ✓ |
|---|---|---|---|---|---|
| | | | | | |

## 6. Roles

| Role | Who | Responsible for |
|---|---|---|
| Pilot owner, reconciliation | Fabian | daily reconciliation, sign-off, decisions D1–D5 |
| Server / network | ______ | section 2, firewall, backups, restore drill |
| SF1 branch manager | ______ | accounts, cancelling, documents, outage booking |
| Counting team | ______ | opening count |
| Backup/monitoring watcher | ______ (D4) | `systemctl --failed` each morning |

## 7. After the trial

- Remove the temporary "−1" stock button (`bestand.minus_one`, `app/static/js/bestand.js`) once the in-store trial is done.
- Decide package order again with the findings (section 8): returns/held stock (package 4) is next in the roadmap.
- Other branches: their own opening count, then their own pilot day. Not before.

## 8. Findings and sign-off (fill in during the pilot)

| Date | What was checked | Result | Follow-up |
|---|---|---|---|
| | Phone scan, iPhone | | |
| | Phone scan, Android | | |
| | Hardware scanner | | |
| | Label printer | | |
| | Retry test (Wi-Fi off after booking) | | |
| | Stale-count warning | | |
| | Opening count signed off (date/time) | | |
| | Restore drill | | |
| | Pilot day reconciliation | | |
