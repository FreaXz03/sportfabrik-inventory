# Automatic Backups

The daily run is set up in Codex for 20:00 (Europe/Zurich).
It is bound to this local Codex task, not a Windows or Linux system service.
The PC, Codex, and Docker must be available for the run. When moving to
Linux, a dedicated server schedule must be set up and tested.

Manually, from the project folder:

```powershell
.\.venv\Scripts\python.exe scripts/backup_inventory.py
```

Target: `backups/automatic/inventory-TIMESTAMP/` (timestamp in UTC).
Each complete folder contains `database.dump`, `original-pdfs.zip`,
`archive-contents.txt`, and `manifest.json` with SHA-256 checksums.

The database backup also includes users and password hashes. The PDF backup
picks up files from `Recchnungen/` and `uploads/`; only uploaded PDF files
not stored there cannot be included in the backup. Configuration secrets
such as `.env.server` are not copied into the backup and must be kept
safe separately.

Checks: successful pg_dump, readable table of contents via pg_restore --list,
ZIP CRC. These checks do not replace a regular full restore test.
On error, no incomplete folder is published as a finished backup.

There is currently no automatic deletion. Monitor storage usage.
A copy outside the PC is not yet set up (owner: later).
Once a target is ready:

```powershell
.\.venv\Scripts\python.exe scripts/backup_inventory.py --external "E:\InventoryBackups"
```

The external folder must exist. When the target is set up, also update the
Codex automation.

## Encrypted external copy (S4, 2026-09-29)

The copy on the external drive is **always encrypted with
[age](https://age-encryption.org)** — there is no unencrypted external copy.
The script packs the finished backup folder into one file,
`inventory-TIMESTAMP.tar.age`, encrypts it with the **public** key, copies it,
compares checksums, and writes `inventory-TIMESTAMP.tar.age.sha256` next to
it. Local backups under `backups/automatic/` stay unencrypted for a quick
restore on the server itself.

Two keys:

- **Public key** (`age1…`): only encrypts. Lives on the server in
  `backup-age-recipient.txt` (project folder, not in git) or is passed with
  `--recipient age1…`.
- **Private key** (`AGE-SECRET-KEY-1…`): the only way to open the backups.
  **Never on the server.** Keep it on a USB stick in the head office and as
  a paper printout in a second place. Losing it means the external backups
  can never be opened.

### Set up once

1. Install age on the server (Linux: `sudo apt install age`, Mac:
   `brew install age`, Windows: `winget install FiloSottile.age`).
2. On a **different** PC create the key pair:
   `age-keygen -o sportfabrik-backup-key.txt`. It prints the public key
   (`Public key: age1…`).
3. Copy `sportfabrik-backup-key.txt` to the USB stick, print it, then delete
   it from that PC.
4. On the server put only the public key into `backup-age-recipient.txt`
   (one line `age1…`).

### Restore from the external drive

```bash
shasum -a 256 -c inventory-TIMESTAMP.tar.age.sha256      # file intact?
age -d -i /path/to/sportfabrik-backup-key.txt -o backup.tar inventory-TIMESTAMP.tar.age
tar -xf backup.tar                                          # gives inventory-TIMESTAMP/
```

Then restore `database.dump` with `pg_restore` and unpack
`original-pdfs.zip` as usual. Test a full restore at least once after
setup.

Without a valid public key or without age installed, `--external` stops
with an error; the local backup is kept.
