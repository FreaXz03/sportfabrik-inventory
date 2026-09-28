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

**Open (security review 2026-09-24, S4):** The backup on the
external drive is also unencrypted (database dump and all original PDFs).
Add encryption before the first external backup, see
[`sicherheit.md`](sicherheit.md).

The external folder must exist. After copying, the checksums are
compared. A copy error leaves the local backup intact and reports an
error. When the target is set up, also update the Codex automation.
