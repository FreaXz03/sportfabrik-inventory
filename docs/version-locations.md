# Source and deployment locations

Verified 29 October 2026 via read-only SSH and local comparison.

## Development source

The Mac repository at `/Users/fabianmorf/Documents/Sportfabrik-inventory`, branch `feature/warenwirtschaft-v2`, now combines local commit `7bfe0ca` and the additional source recovered from the running server directory. Existing uncommitted instruction/agent changes were preserved separately.

Recovered work includes INTERSPORT delivery parsing, local OCR and barcode EAN decoding, explicit cancelled-document replacement (migration `a20261028`), and unified article search. A local fix makes the new migration support PostgreSQL offline SQL generation; it has not been deployed. Install requirements before running. Apply pending migrations to a backed-up local development database before local app use; reconciliation did not modify any database.

## Server locations

| Path on sfserver | Role and observed status |
| --- | --- |
| `/home/sfadmin/homeserver/sportfabrik-inventory` | Running deployment source; no Git metadata. Contains additional work from 28 October. Preserve this directory, `.env.server`, backups and Compose project `sportfabrik`. |
| `/home/sfadmin/projects/sportfabrik-inventory` | Stale development clone at `8de830d`; do not use as latest source until explicitly synchronized. |
| `/opt/sportfabrik-inventory` | Historical clone at `94e5085`; not the Compose working directory of the running app. Retained for recovery. |

The running image was created on 28 October 2026 at 14:49 UTC. Reconciliation did not change server files, containers, images, databases, volumes or services. No migration was run against production.

## Recovery and workflow

Original server source, original local source and local Git history were saved in `/Users/fabianmorf/Documents/Sportfabrik-reconciliation-20261029`. Archives exclude production data, uploads and credentials.

Use Git to transfer reviewed development changes between machines. Keep production deployment separate and deploy only deliberately, after backups and migration checks. Do not develop directly in the deployment directory. The older server clones remain in place until their consumers and backup references have been checked; no deletion or directory move was performed.

GitHub has not been updated by this reconciliation. At inspection, the remote working branch was `8de830d` and main was `884c36c`.

Validation on the isolated combined source: **378 passed, 15 skipped** (SQLite). Private document regressions were not enabled. PostgreSQL production migrations were not rerun. App and database remained healthy after reconciliation.
