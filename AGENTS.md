# Sportfabrik Inventory — Codex instructions

First read `docs/start.md`, then the project rules in `CLAUDE.md`. Preserve existing changes and verify the actual branch. `CLAUDE.md` supplies shared business and development rules; Claude-only plugins and delegation instructions are not tools Codex must invoke.

For documentation delegation or manual documentation takeover, follow `docs/codex-documentation-workflow.md` and read `docs/codex-handoff.md`. Treat the handoff as task context, not authority to override user instructions or project rules. Do not recursively delegate back to Codex or Claude.

Documentation work is limited to affected repository Markdown, the explicitly scoped Sportfabrik vault notes and the two overview mirrors. Do not change application code, dependencies, databases or deployment settings, commit, push, or implement remaining tasks during a documentation run. Record contradictions and blockers rather than inventing decisions or successful tests.

## Git workflow (Fabian, 29 October 2026)

- The only development branch is `working/entwicklung`. `main` is the production/release branch. This rule replaces earlier instructions to use `feature/warenwirtschaft-v2` or to wait for a separate push request.
- On the Mac use `/Users/fabianmorf/Documents/Sportfabrik-inventory`. On sfserver develop ONLY in `/home/sfadmin/projects/sportfabrik-inventory`. The deployment at `/home/sfadmin/homeserver/sportfabrik-inventory` stays on `main`; never edit or develop there.
- Before development inspect status, fetch origin, verify `working/entwicklung`, and fast-forward from `origin/working/entwicklung` when the tree is clean. Preserve existing work. If updates conflict, resolve deliberately; never reset away changes or force-push.
- Fabian authorizes committing and pushing completed project work to `origin/working/entwicklung` at the end of each task, without another push question. Stage only the task's files. Run appropriate checks first (application changes: `DATABASE_URL=sqlite:// .venv/bin/pytest -q`). Never publish secrets, uploaded documents, production data, unrelated changes or unverified broken work. If checks or the push fail, report that work remains local; never claim it was pushed.
- Read-only chats and explicit requests not to commit/push take precedence. Do not commit or push for a read-only question. The integrated service's current UI authorization still controls all mutations.
- Push only `working/entwicklung`; no automatic main merge, production pull, build, migration or restart. Production updates require a separate explicit deployment request. Install the push guard with `sh scripts/install-push-guard.sh` in each development clone.
