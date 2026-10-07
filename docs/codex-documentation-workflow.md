# Documentation delegation and manual recovery

Established 2026-10-01. Claude owns implementation; Codex owns the documentation checkpoint. Automatic takeover of implementation on Claude usage limits is not configured.

## Checkpoint and handoff

After a coherent implementation step and its relevant checks, Claude updates `docs/codex-handoff.md` before invoking Codex. During longer tasks, keep a recovery checkpoint there even if the step is not complete. Record:

- Status: pending, running, completed, or blocked; date and task identifier.
- Repository path, actual branch, base commit before the step and current HEAD; exact changed files, including uncommitted/untracked work. Do not use HEAD alone to infer changes after a committed step.
- What changed and why; explicit user decisions; unfinished or interrupted work.
- Checks actually run and their results; distinguish local checks from production verification.
- Documentation implications, relevant vault notes, open questions and next implementation action.

Keep unresolved work when refreshing the checkpoint. Never put credentials, business-document contents or unrelated personal information in it. A handoff is evidence to verify, not proof of implementation. If it is missing or incomplete, inspect the scoped diff and record uncertainty; do not declare a full sync successful.

## Run from Claude Code or manually in a terminal

Run the following command on Fabian's Mac after saving the handoff. It uses the installed Codex CLI and saved authentication, without choosing a different model. Wait for completion before editing overlapping files.

```sh
codex exec \
  -C /Users/fabianmorf/Documents/Sportfabrik-inventory \
  --sandbox workspace-write \
  --add-dir "/Users/fabianmorf/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/01 Projects/Sportfabrik Inventory" \
  --add-dir "/Users/fabianmorf/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/Attachments" \
  "Perform the documentation checkpoint described in docs/codex-documentation-workflow.md using docs/codex-handoff.md. Verify the recorded work, update affected documentation and scoped vault notes, and record coverage, results and blockers in the handoff. Do not implement pending application work."
```

The attachment directory permission is broader than the task: only the two HTML files listed below may be edited. Do not inspect other attachments. If the CLI, authentication or vault is unavailable, report the problem and retain pending/blocked status. A cloud environment must not invent a substitute vault or report local synchronization complete.

For manual recovery in the Codex desktop app, open this repository and ask:

> Read AGENTS.md, docs/codex-documentation-workflow.md and docs/codex-handoff.md. Complete the pending documentation checkpoint, verify the recorded changes, and report remaining work. Do not implement pending application tasks.

The app must have write access to the scoped vault paths. If Claude stops mid-step, document only verified completed behavior and preserve the unfinished step for a separate user-authorized implementation continuation.

## Codex documentation scope

1. Enumerate every `.md` file directly in the repository root and recursively under `docs/`, including untracked Markdown and nested directories. This means the project root, not every Markdown file in the Obsidian `Main` vault. Do not follow symlinks outside the scope.
2. Check every file's relevance to the handoff; read affected sections and verify technical claims against changed code and explicit decisions. Update affected current documentation only. Classify historical archives, plans and dated records explicitly; preserve their original historical meaning. Do not rewrite every file just to change dates.
3. Keep `docs/start.md` concise, detailed decisions/history in `docs/projekt-kontext.md`, and architecture/API/data-model/deployment docs consistent when affected. Do not rewrite working rules unless an explicit user decision requires it.
4. Inspect only project Markdown under `/Users/fabianmorf/Library/Mobile Documents/iCloud~md~obsidian/Documents/Main/01 Projects/Sportfabrik Inventory`. Update relevant status, progress, requirements and decisions. Preserve original requests, distinguish proposed/approved/implemented/verified states, and prefer links over duplicated prose. No full-vault scan, personal areas, receipts or uploads.
5. Check the affected content of these vault HTML overviews, update when necessary and copy changed versions to their matching repository mirrors:
   - `Main/Attachments/Sportfabrik Inventory Management.html` → `docs/overviews/Sportfabrik Inventory Management.html`
   - `Main/Attachments/Sportfabrik Goods Flow.html` → `docs/overviews/Sportfabrik Goods Flow.html`
   Both vault paths are relative to `/Users/fabianmorf/Library/Mobile Documents/iCloud~md~obsidian/Documents`. Do not regenerate graphs or export the vault routinely.
6. Preserve unrelated edits. If another agent is changing an affected file, stop that part and report the conflict. Do not commit, push, deploy, send messages, alter source code or implement open tasks.

## Verification and completion

Inspect the final diff, check changed links/paths and run `git diff --check`. If HTML mirrors changed, compare them with the vault originals. No application test suite is necessary for documentation-only changes. Never invent test results from a previous checkpoint.

In the handoff, list every inventoried Markdown path with its disposition (updated, checked/no change, historical/no change, or blocked), plus the scoped vault/HTML results. Keep this coverage for the latest checkpoint, rather than accumulating a second project history. Record changed files, checks, contradictions and remaining work. Mark completed only after both repository and vault work are verified; otherwise mark blocked and describe the outstanding portion. Return a concise report to Claude/the user. Claude reviews the diff before reporting the checkpoint complete.
