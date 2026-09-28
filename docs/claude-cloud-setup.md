# Setting up Claude Code in cloud sessions

Locally installed Claude Code plugins only apply on your own machine.
Cloud sessions (claude.ai/code, `claude --cloud`, GitHub triggers) start in
a fresh container and bring none of that with them. This guide sets
them up there.

## Why the repo setting alone isn't enough

The obvious move would be to write `enabledPlugins` and `extraKnownMarketplaces` into
`.claude/settings.json`. That does **not** work for cloud sessions —
the Claude Code documentation explicitly lists "Plugins and marketplaces declared in your
repo's `.claude/settings.json`" as *not* carried over
([Cloud environments → What carries over from your setup](https://code.claude.com/docs/en/cloud-environments#what-carries-over-from-your-setup)).

Timing is what matters: plugins are loaded when Claude Code starts. Anything
installed only *during* startup — by a SessionStart hook, for instance — isn't
there yet in that same session. Only the environment's **setup script**
runs before that.

| | Setup script | SessionStart hook |
| --- | --- | --- |
| Configured in | claude.ai/code → environment selector → gear icon | `.claude/settings.json` in the repo |
| Runs | before Claude Code starts | after it starts |
| Applies to | cloud sessions only | local and cloud |
| Responsible here for | system packages, database, plugins | starting the service, Python dependencies |

After the setup script runs, the filesystem is snapshotted; later sessions start
directly from that image and skip the script. It runs again if you
change the script or the network permissions, and after about seven days.

The snapshot holds **files, not processes**. Installed packages and the
created database are present in every later session; a service
started in the setup script, however, is not — that belongs in the hook.

## 1. Register the setup script

On [claude.ai/code](https://claude.ai/code), in the row above the
message field, click the cloud icon with the environment name, hover over the
environment in the **Cloud** section, click the **gear icon**, and copy the
contents of [`scripts/claude-cloud-setup.sh`](../scripts/claude-cloud-setup.sh)
into the **Setup script** field. There is no settings page or direct URL
for this.

The script is deliberately self-contained — it doesn't touch anything from the repo, because
at that point there's no guarantee the clone already exists. It
does three things: system packages (PostgreSQL, Tesseract with DE/FR for OCR),
the test database `sportfabrik_dev` plus its user, and the plugins.

Everything comes from a single marketplace:
[`FreaXz03/claude-plugin-marketplace`](https://github.com/FreaXz03/claude-plugin-marketplace).
It bundles the official Anthropic plugins and the ones from third-party repos in one
place; except for `markitdown`, it points to the
original repos via `git-subdir`, so the plugins stay up to date on their own.

**The marketplace and the source repos it links to must be public.**
The container has no git credential helper and no `gh`; a private repo
fails with `could not read Username`. Because every call in the script is followed by
`|| true`, that otherwise goes unnoticed — the plugin is simply missing.

Installed:

| Plugin | What for |
| --- | --- |
| `pyright-lsp` | live type checking, matching `pyrightconfig.json` |
| `code-review` | `/code-review` with specialized agents |
| `commit-commands` | `/commit`, `/commit-push-pr`, `/clean_gone` |
| `claude-md-management` | maintain `CLAUDE.md` |
| `security-guidance` | security hints while editing |
| `frontend-design` | UI, matching vanilla JS/CSS |
| `playwright` | browser control; Chromium is preinstalled |
| `markitdown` | convert documents to Markdown |
| `caveman` | terse answers |
| `context-mode` | conserve the context window |
| `context7` | library documentation on hand |
| `claude-mem` | memory across sessions |

The first ten run entirely inside the container. The last two do not:
`context7` fetches documentation from an external service, `claude-mem` sends
session data to cmem.ai and reads it back from there. Rule 1 in `CLAUDE.md`
allows this: it requires local processing for **document data**, not for the
development tools.

One restriction still applies, though: `claude-mem` transmits whatever the session
touches. Anyone working in a session with real documents from `uploads/` or
`Rechnungen/` — for example while building a new parser — sends their
contents along too. With Graphify as well, the selection of the content actually processed is decisive; `--code-only` is optional, and automatic document analysis remains excluded (see `docs/obsidian-graphify.md`). For
such sessions, disable `claude-mem` (`/plugin`) or remove those two lines from
the plugin list.

**Listed in the marketplace, but deliberately not installed:**

- `obsidian` — the vault lives on the work machine, useless in the container.
- `security-sweep` — the source repo listed in the manifest,
  `onomeaj/security-sweep-plugin`, cannot be cloned anonymously (`git ls-remote`
  asks for a username). If it needs to go into the cloud, the plugin would have to live
  directly in our own marketplace repo, like `markitdown`, instead of being linked via `git-subdir`.

**Not available at all:** desktop-bound plugins (Desktop Commander,
pdf-viewer, cowork-plugin-management) have no basis in the container.

## 2. Register the SessionStart hook

Without this step, neither the test suite nor the app runs in a cloud session:
the Python packages are missing, and PostgreSQL, while installed, is
not started. Create `.claude/settings.json` (or add the `hooks` block to an
existing file):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/scripts/claude-session-deps.sh"
          }
        ]
      }
    ]
  }
}
```

[`scripts/claude-session-deps.sh`](../scripts/claude-session-deps.sh) starts
PostgreSQL, creates a `.venv`, installs `requirements.txt` plus pytest, and
sets the path for the session. Locally it exits immediately
(`CLAUDE_CODE_REMOTE`), leaving the existing `.venv` untouched.

**Why a `.venv` and not the system Python:** there,
`pip install -r requirements.txt` reproducibly fails with
`Cannot uninstall PyYAML 6.0.1, RECORD file not found. Hint: The package was
installed by debian` — even with `--break-system-packages`. `pyrightconfig.json`
points to `.venv` anyway.

The hook runs synchronously: the session doesn't start until it finishes. Measured
at around 22 seconds the first time, then about 4 afterwards, because `.venv` already
exists and only the service still needs to come up. Anyone who prefers a faster start
can run the hook asynchronously, at the cost of an early `pytest` call
running against nothing.

## Verified

In a fresh HOME, i.e. the way a new container starts:

- `claude plugin validate .` against the marketplace → "Validation passed."
- Marketplace added and the ten purely local plugins from it installed:
  all ten succeeded, `security-sweep` was the only failure (source repo
  not clonable anonymously, see above).
- A session prepared this way also loads the plugins in the project directory —
  verified with an earlier version of the script: `code-review:`, `commit-commands:`
  (three), `claude-md-management:` (two), `frontend-design:`. `pyright-lsp`,
  `security-guidance`, and `playwright` don't bring skills, but rather an LSP,
  hooks, or an MCP server respectively.
- `context7` and `claude-mem` were **not** trial-installed — the
  development session's auto mode prevented it, because `claude-mem`
  transmits session data externally. Instead, it's verified that both are
  listed in the marketplace manifest and that the script issues the right commands.
  The first real run is the one in your environment.
- Hook: exit code 0, 22 seconds on the first run, 4 seconds with an existing
  `.venv`. Cross-checked with the service stopped beforehand — afterwards `pg_isready`
  reports "accepting connections," and `CLAUDE_ENV_FILE` contains the `.venv` path.
- Database reachable: `create_engine(DATABASE_URL)` connects as
  `sportfabrik` to `sportfabrik_dev`.
- Afterwards `pytest -q` → 369 passed, 19 skipped;
  `pyright app/services/corrections.py` → 0 errors.

Also confirmed in the running container: `psql` and `tesseract` (with `deu`,
`fra`) are present and the database still exists — so the system packages and
the data do survive in the snapshot. The PostgreSQL service, however, was
down, and the Python packages were missing: the `pip` call in the setup script fails on
Debian's PyYAML and is swallowed there by `|| true`. The hook closes exactly
these two gaps.

## If something is missing

- `claude plugin list` shows what's loaded; `/plugin` is the UI for that.
- The setup script must exit with 0, otherwise the session won't start — that's
  why every call is followed by `|| true`.
- After a change to the script, it runs again on the next session start, and the
  saved image is rebuilt.
