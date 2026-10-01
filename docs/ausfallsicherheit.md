# Data safety and recovery (package 3 preparation, 2026-10-01)

Requirement (decision Q7, 2026-10-01): **no data loss**; **downtime of a few
hours is acceptable** (paper notes meanwhile, book later). This note scopes what
that means for the server, what is prepared, and what is still undecided.
Nothing here has run on a real server yet.

## What must survive

| What | Where it lives | Covered today |
|---|---|---|
| All business data (items, stock, movements, documents' parsed lines, counts, accounts) | PostgreSQL volume `postgres_data` | nightly dump, see below |
| Local certificate authority (every phone/PC trusts it) | volume `caddy_data` | **not** in `backup_inventory.py` — export once by hand (checklist in `pilot-sf1.md`) |
| Secrets (`POSTGRES_PASSWORD`, `SESSION_SECRET`) | `.env.server` on the server | not backed up by design; keep in the password safe. Losing `SESSION_SECRET` only logs everyone out |
| Backup decryption key | USB stick + paper, never on the server | see `BACKUPS.md` |
| **Original supplier PDFs** | **nowhere in the app** | see "Finding" |

### Finding: uploaded PDFs are not stored

The importer reads the PDF, stores the parsed lines (with a per-line source
snapshot in `wareneingang_positionen_quelle`), the file name and the SHA-256
hash — **not the PDF itself**. `backup_inventory.py` zips `Recchnungen/` and
`uploads/`, which do not exist inside the server container, so on the server
`original-pdfs.zip` will be empty. "Restore database + original documents"
(roadmap, package 3) therefore only works if the originals are kept elsewhere
(mail, paper, a shared folder).

Options — **decision needed (Fabian):**

1. *Accept:* originals stay where they are today; the database holds everything
   the app needs. Simple, but a parser fix later cannot re-read old documents,
   and "copies of uploaded documents as they arrive" is the business's job.
2. *Archive in the app (recommended):* on a successful import, save the PDF as
   `documents/<sha256>.pdf` in a new Docker volume, include that volume in the
   backup, and show a download link on the document page. Small change (one
   volume, one write after commit, one read endpoint); documents stay on the
   server (rule 1). Not built — waiting for the decision.

## Recovery point: what "no data loss" can mean

Today: a nightly dump → up to a day of bookings can be lost. Not enough.

| Option | Loss if the server disk dies | Cost / risk |
|---|---|---|
| A. WAL archiving to a second machine (`pg_receivewal` or pgBackRest) + weekly base backup + nightly dump | seconds to a minute (last unarchived WAL) | needs a second machine/NAS; restore = base backup + WAL replay (point-in-time) |
| B. Streaming replica on a second machine (asynchronous) | seconds | second machine; failover is manual; replica must be monitored |
| C. Synchronous standby (`synchronous_standby_names`) | none | writes **block** if the standby is unreachable unless relaxed to async — a network hiccup stops the store; needs someone to switch it |

Recommendation: **A**, because a few hours of downtime are acceptable, a manual
restore is fine, and it also gives point-in-time recovery (undo a bad import).
`pg_receivewal --synchronous` can be added later if "seconds" is not good
enough. **Needs a second machine and an owner for it** — open decision.

Sketch (untested, to be verified in the restore drill; PostgreSQL 18 in
`compose.yaml`):

```yaml
  db:
    command: >
      postgres -c wal_level=replica -c max_wal_senders=4
               -c wal_keep_size=1GB
```

plus a `replicator` role with `REPLICATION` and `pg_hba` access from the second
machine only, then on that machine `pg_receivewal -h SERVER -U replicator -D
/backup/wal --synchronous`, a weekly `pg_basebackup`, and an encrypted copy of
both (same `age` key as `BACKUPS.md`). Do not enable this on the live server
before the base-backup + WAL restore has been rehearsed once.

## What is prepared in the repo

| Piece | Purpose |
|---|---|
| `deploy/systemd/sportfabrik-backup.{service,timer}` | nightly 22:00: dump, PDFs, age-encrypted external copy — on the server itself, not a local Codex task |
| `deploy/systemd/sportfabrik-checks.{service,timer}` | 06:15 daily: `betrieb.py pruefe` (stock = sum of movements) and `check_backup_age.sh` (newest backup < 26 h). Failing run shows in `systemctl --failed` |
| `deploy/systemd/sportfabrik-restore-drill.{service,timer}` | Sundays 03:00: restore the newest local backup into a throwaway PostgreSQL container and verify it |
| `scripts/restore_drill.sh` | the drill itself (also for a `.tar.age` from the external drive, with `--key`) |
| `scripts/check_backup_age.sh` | exit 1 if the newest backup is missing or too old (tested locally) |
| `scripts/betrieb.py pruefe` | `bestand` vs `lagerbewegungen`, exit 1 on any mismatch (tested) |

Install on the server (user `sportfabrik` in the `docker` group, project in
`/opt/sportfabrik-inventory`, external drive mounted at
`/mnt/sportfabrik-backup` — adjust `EXTERNAL_DIR` in the service):

```sh
sudo cp deploy/systemd/sportfabrik-* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sportfabrik-backup.timer sportfabrik-checks.timer sportfabrik-restore-drill.timer
systemctl list-timers 'sportfabrik-*'
sudo systemctl start sportfabrik-backup.service        # first run by hand
```

Monitoring is deliberately simple: failed units. Someone must look at
`systemctl --failed` (or add mail/notification later) — name that person in
`pilot-sf1.md`.

## The restore drill (acceptance: "one demonstrated full restore")

Do this once before the pilot, on an isolated machine or the server itself with
the throwaway container (never into the live database):

1. `scripts/restore_drill.sh` (newest local backup) — must end with
   `RESTORE-DRILL BESTANDEN`.
2. Repeat with the **external** copy and the private key from the USB stick:
   `scripts/restore_drill.sh /mnt/sportfabrik-backup/inventory-…tar.age --key /path/to/sportfabrik-backup-key.txt`.
3. Start an app container against the restored database in an isolated
   network, log in, open a document, the stock page and `/statistiken`; compare
   three items and one document with the live system.
4. Write the result into the table below. A drill that was never run does not
   count.

| Date | Backup used | Who | Result | Notes |
|---|---|---|---|---|
| | | | | |

The drill script has not been run yet: this environment has no Docker daemon.
The SQL consistency check was verified against SQLite; the checksum and archive
checks run in plain Python.

## Outage

Procedure for staff and IT: `pilot-sf1.md`, section "Outage procedure".
