# Repository reconciliation and workflow setup — 29 October 2026

## Decisions and completed work

Compared the Mac repository, GitHub and three homeserver copies. The initially inspected server development clone was stale (`8de830d`). Additional work was found in the production source directory without Git metadata; matching three selected files had not established whole-tree equality.

Recovered the additional server code into the Mac development repository: INTERSPORT/Adidas delivery parser, local OCR and barcode EAN recovery, explicit replacement of cancelled documents (migration `a20261028`), and unified article search. The server code already included the four newer Mac commits. Preserved unrelated local instruction/reviewer changes. Fixed offline PostgreSQL SQL generation in the recovered migration locally; no production migration was executed during reconciliation.

Committed the recovery as `d5a9f4b`, pushed five pending commits to GitHub and merged PR #19 into main (`1ac8c9a`). Created `working/entwicklung` from that main commit. Removed the other Mac and GitHub branches after saving their refs and complete Git history. Old linked worktree directories were detached and retained, including their untracked files; this was branch cleanup, not file deletion.

Linked `/home/sfadmin/homeserver/sportfabrik-inventory` to GitHub on `main`. Initial linkage changed Git metadata only; subsequently added missing documentation and aligned the one known migration source difference after backup. Did not rebuild/restart the Sportfabrik app or modify its database. The already-running image remained the image built on 28 October.

Updated `/home/sfadmin/projects/sportfabrik-inventory` to `working/entwicklung` and removed its obsolete development branch. Configured a repository-specific SSH deploy key with write access and a pinned GitHub host key; no credentials were committed or printed. Added a pre-push guard on the Mac and in both server clones. Ordinary pushes are permitted only from `working/entwicklung` to the same remote branch; main, tags and branch deletion are rejected. These are local accident-prevention hooks, not GitHub branch-protection rules.

Committed shared instructions and tooling as `96acee4` on `working/entwicklung`; the server development clone was fast-forwarded to that commit. The main branch intentionally does not receive working-branch documentation/tooling commits automatically.

## Integrated KI-service

Added `/home/sfadmin/homeserver/codex-chat/sportfabrik-workflow.md` and included its policy in each turn's prompt. Applies to both Codex and Claude and existing chats. Sportfabrik development must use the separate development clone. When UI write permission is enabled, completed and verified task changes are to be selectively staged, committed and pushed to working before the final answer. Read-only questions cause no mutation; failed checks/pushes must be reported. This is an agent work instruction, not an unconditional background auto-commit job.

Checked that no chat was busy, backed up `server.py`, validated Python syntax, changed only the prompt-construction expression and restarted only `homeserver-codex-chat.service`. Existing UI authorization and sandbox logic were preserved. HTTP access to the service was verified after restart.

A working push does not merge main or deploy. A release and a production update each require explicit user authorization. Never automatically pull, rebuild, migrate or restart production at task completion.

## Verification actually performed

- Combined application source: **378 passed, 15 skipped** on SQLite in an isolated Mac source copy. The 24 integrated source paths matched that tested copy. Private-document regressions were not enabled; no new production/PostgreSQL migration test was run in this session.
- Installed `zxing-cpp==3.1.1` in the Mac development environment. Targeted parser/reimport tests passed after adding the dependency.
- Offline migration regression passed after its local fix.
- Push-guard shell syntax and allowed/rejected inputs checked; real pushes against a disposable local bare repository confirmed working succeeds and main is blocked. Server GitHub push dry-run succeeded; production guard rejected main.
- Verified GitHub branch heads after push/merge/cleanup. KI-service HTTP check succeeded. Sportfabrik app and database health checks remained healthy; the app was not restarted by workflow setup.
- This documentation update uses targeted Markdown/diff checks only; earlier application results are recorded history, not a new application test run.

## Recovery copies

- Mac: `/Users/fabianmorf/Documents/Sportfabrik-reconciliation-20261029/` contains original local source, recovered server source, `local-history.bundle`, `before-branch-cleanup.bundle`, branch refs and application validation output. Source archives exclude credentials and production data.
- Server Git linkage: `/home/sfadmin/backups-sportfabrik/git-link-20261029/`, including the migration's previous source and a manifest recording the previously absent documentation file.
- KI-service: `/home/sfadmin/homeserver/codex-chat/backup-git-workflow-20261029T150151Z/server.py`.

## Current exception to preserve

A subsequent HTTPS change was recorded separately in the vault and confirmed during this documentation update: the production clone is on main with **uncommitted `Caddyfile` and `compose.yaml` changes**. Its development clone was clean on working. Preserve these production overrides before any future pull/deployment; they have not been incorporated into GitHub by this documentation task. HTTPS backup location recorded in the vault: `/home/sfadmin/backups-sportfabrik/https-20261029T152401Z`. App and database were healthy at the documentation check.

Operational rules and locations: [Development and production workflow](version-locations.md). Older dated branch/status descriptions are historical; the current development branch is `working/entwicklung`. The unrelated pending documentation-delegation checkpoint in `codex-handoff.md` was not performed or marked complete here. No interface/goods-flow behavior changed in this task, so HTML overviews were not regenerated.
