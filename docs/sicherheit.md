# Security — review and open measures

As of: security review from **2026-09-24** (branch `feature/warenwirtschaft-v2`,
commit `229e8b6`). Reviewed: secrets (code and full git history),
injection (SQL, XSS, commands, paths, deserialization), login and
permissions, configuration (Docker, headers, endpoints), dependencies
(`pip-audit`), AI usage, and data protection.

**Result:** no critical and no high findings. Four medium items
should be done **before deployment in the store** (roadmap phase F — operations),
plus five low ones. Fixed: the login lockout from S2 (2026-09-24).

This file is updated on every fix (status column).

## Open measures

| # | Level | Topic | Measure | Status |
|---|---|---|---|---|
| S1 | medium | Login over HTTP, 5-year session | HTTPS via local reverse proxy (e.g. Caddy with an internal certificate), cookie with `https_only=True`; invalidate sessions server-side on password change | open — before store deployment |
| S2 | medium | Login with no limit on failed attempts | Lock account for 20 minutes after 5 wrong passwords (decision 2026-09-24); server reachable only on the store network. Not yet decided: minimum password length 10 instead of 6, uniform error message | **lockout implemented** (2026-09-24, migration `b9c0d1e2f3a4`); network separation on server migration |
| S3 | medium | Pillow 12.2.0 with 13 known vulnerabilities | Update to 12.3.0 (`requirements-server.txt`, `requirements.txt`) | open |
| S4 | medium | Backups unencrypted | Encrypt backup before copying to external media (`age` or `gpg --symmetric`), store key separately | open |
| S5 | low | API docs with no login | Disable `/docs`, `/redoc`, `/openapi.json` in operation | open |
| S6 | low | `/db-test` with no login | Return only `{"ok": true}` (needed by the Docker health check) | open |
| S7 | low | No security headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'self'` | open |
| S8 | low | Server packages without transitive pins/hashes, images without digest | `pip-compile --generate-hashes`, `pip install --require-hashes`, pin images with `@sha256:` | open |
| S9 | low | Overview pages load Google Fonts | Remove links in `docs/aktualisiert/*.html` (and the vault versions), use a system font | open |

### Details

**S1 — HTTP and long session.** The app currently runs under
`http://SERVER-IP:8080` (`docs/SERVER-SETUP.md`). Branch managers' passwords
and the session cookie therefore travel unencrypted across the
network. The cookie is valid for 5 years (`SESSION_MAX_AGE` in `app/routers/auth.py`,
deliberately "until logout" like at the till) and contains only the user ID;
an intercepted copy therefore remains valid even after logout or a password change.
With HTTPS on the store network, interception is practically ruled out.

**S2 — Login.** *Implemented on 2026-09-24:* after 5 wrong passwords, an account is locked for 20 minutes (response 429, also for the correct password; counted per account in the database, `app/services/anmeldung.py`). Before that, `/login` didn't count failed attempts. Each password attempt
costs the server about half a second of compute time due to PBKDF2 (600,000 rounds),
and only one worker runs. Responses distinguish between
"till number unknown" and "password required." Employees deliberately
log in with just the till number (till pattern, D8) — the real
protection is therefore that only store PCs can reach the server (no guest WiFi,
no port forwarding to the internet).

**S3 — Pillow.** Barely exploitable today: `app/services/ocr.py` only feeds Pillow
raw pixels from PyMuPDF (`Image.frombytes`); the affected image decoders
are not used. It becomes relevant as soon as, for example, JPEG uploads are opened
directly with Pillow. The update is small.

**S4 — Backups.** `scripts/backup_inventory.py` stores the database dump and
`original-pdfs.zip` in plaintext, including on the external medium
(`docs/BACKUPS.md`). A lost storage medium would contain all
supplier documents, purchase prices, and accounts.

## Notes requiring no action

- `text(f"SELECT pg_advisory_xact_lock({ADVISORY_LOCK_ID})")` only inserts a
  fixed number — no SQL injection.
- Stock search (`app/services/bestand.py`) does not escape `%` and `_` (the
  item search already does) — affects only match results, not security.
- `.gitignore` does not yet cover `.venv-1/`, `.coverage`, `*.pem`, `*.key`, and `.env.*`
  — none of these are versioned.
- `CLAUDE.md` contains a local path with the Mac username.
- Booking rights since 2026-09-24: employees enter and correct stock only in
  their assigned branches; booking out, cancelling, and transferring only for
  branch managers and head office (checked server-side, `tests/test_rechte_lager.py`).
- Test passwords exist only in the tests.

## What's good

- No secrets in code or git history; `.env.server` is ignored,
  readable only by the owner, both secrets are 64 characters long.
- Database access only via SQLAlchemy with parameters; sorting as a fixed
  allow-list; item search escapes wildcards.
- Frontend without `innerHTML`/`eval`, output via `textContent`, no
  external scripts (enforced by test), login redirect verified (test).
- All data endpoints require login; documents only for branch managers and
  head office; storage-location rights checked server-side.
- Passwords with PBKDF2-SHA256, 600,000 rounds, salt, and constant-time
  comparison; session is renewed on login; `SameSite=Lax` and strict
  content-type checking protect against cross-site requests.
- Excel export keeps formulas as text; upload limit 20 MB and 200 pages;
  password-protected PDFs are rejected.
- Docker: app runs without root, database not reachable from outside, default only
  `127.0.0.1`, no `--privileged`, no `:latest` images.
- No outgoing HTTP calls, no AI in operation (rule 1), no
  insecure deserialization, backup script without a shell.

## Ongoing

- Run `pip-audit -r requirements-server.txt` before every server update.
- HTTPS, network separation, and encrypted backups are mandatory items for
  phase F (operations).
