# Development and production workflow

Owner decision and setup: 29 October 2026.

## Locations and branches

| Location | Branch | Purpose |
| --- | --- | --- |
| Mac: `/Users/fabianmorf/Documents/Sportfabrik-inventory` | `working/entwicklung` | Development; commit and push verified completed tasks. |
| sfserver: `/home/sfadmin/projects/sportfabrik-inventory` | `working/entwicklung` | Development by integrated Codex/Claude service; same completion rule. |
| sfserver: `/home/sfadmin/homeserver/sportfabrik-inventory` | `main` | Production source linked to GitHub. No development here. |
| sfserver: `/opt/sportfabrik-inventory` | Historical | Old unused clone retained for recovery; do not use. |

The service receives a scoped Sportfabrik workflow reminder on every turn, including existing chats and both providers. Its existing UI authorization still controls mutations. Completed, verified implementation tasks are committed and pushed to `origin/working/entwicklung` without a new push request. Failed checks or push attempts must be reported; read-only questions cause no push.

Read `AGENTS.md` and `CLAUDE.md`. Before changes: inspect status, fetch, verify the working branch and fast-forward when clean. Stage only the task files, preserve unrelated edits and never force-push. Never publish PDFs, databases or credentials.

## Push guard

Run `sh scripts/install-push-guard.sh` in each development clone. It installs `.githooks/pre-push` as the repository pre-push hook while preserving existing post-checkout/post-commit hooks. It permits only `working/entwicklung` to the same remote branch and blocks main, tags and deletion. The production clone has the same guard and cannot push from main. This prevents ordinary accidental pushes; administrators can still change local hooks.

## Releases

A working-branch push does not deploy. Merge to main only when explicitly requested. Update production only on a separate deployment request: preserve server environment, backup the database and files, inspect pending migrations, then deliberately pull/build/migrate/restart and verify health. Never put an automatic production pull or restart in a development completion hook.

The Git linkage itself did not rebuild/restart Sportfabrik or run any database migration. The already-running image remains the image built on 28 October; the production source is attached to main, with the offline migration-script fix aligned separately. A future deliberate deployment will rebuild from that source.

## Recovery

Original server source, original Mac source and Git history: `/Users/fabianmorf/Documents/Sportfabrik-reconciliation-20261029`. Branch deletion snapshot: `before-branch-cleanup.bundle`. Server Git-link backups: `/home/sfadmin/backups-sportfabrik/git-link-20261029`. KI gateway backup is stored beside that service under `backup-git-workflow-*`. Keys and secrets are never stored in the repository.

Validation: combined application source previously passed 378 SQLite tests, 15 skipped. Workflow setup checks cover shell syntax and accepted/rejected push destinations. No production database writes are part of this setup.

## Session record and later production overrides

See [the reconciliation/setup record](reconciliation-2026-10-29.md) for commits, backups, checks and limitations. A later read-only check confirmed uncommitted HTTPS changes in the production clone (`Caddyfile`, `compose.yaml`); preserve them before any release update. The clone is on main but its deployment configuration is therefore not byte-for-byte identical to GitHub.
