# Preparation for Linux

The server files are prepared. A Docker build, data migration, and a
backup restore have not yet been performed. The Windows app and
its `.env` remain usable in the meantime.

## Files

- `Dockerfile`: app without development mode, running as a non-root user;
  also installs Tesseract OCR (for scanned paper invoices without a
  text layer) — no manual step is needed for this on the server,
  unlike the local Windows setup (see `README.md`).
- `requirements-server.txt`: server packages, separate from the Windows installation.
- `compose.yaml`: app and PostgreSQL 18, persistent data volume, startup checks.
- `.env.server.example`: template for server settings.
- `.dockerignore`: only app code and server dependencies go into the image.

## Test locally once Docker and the Compose plugin are present

In the project folder:

```powershell
Copy-Item .env.server.example .env.server
```

In `.env.server`, enter a new, long password between the single quotes for
`POSTGRES_PASSWORD`. Do not reuse the tutorial password.
Do not modify the existing `.env`. Then:

```powershell
docker compose --env-file .env.server config --quiet
docker compose --env-file .env.server up -d --build
docker compose --env-file .env.server ps
```

Test address: https://localhost (the browser warns until the root certificate
is trusted, see "HTTPS" below). The containers use a new, separate
database. Initially there are no invoices. The Windows app on port
8000 and its existing data stay separate.

## Later on Linux

1. Server administration provisions Docker Engine and the Compose plugin.
2. Create a project folder, for example `/opt/sportfabrik-inventory`.
3. Transfer `app/`, `Dockerfile`, `requirements-server.txt`, `compose.yaml`, and the
   settings template. Do not copy the Windows `.env` or `.venv` into the image.
4. Copy the template as `.env.server`, set the password, and protect the file with
   `chmod 600 .env.server`.
5. Start with the Compose commands above. Docker must start at system boot.
   `restart: unless-stopped` will then restart the services unless they were
   deliberately stopped.

## Data migration and backups: next, separate step

Before the migration, check the major version of the Windows PostgreSQL
installation. The target must support at least the same major version. The template uses
PostgreSQL 18, matching the currently verified Windows version 18.6. If the source is newer,
adjust the target version and volume path accordingly before the
first start. Do not simply reuse an existing volume with a
different PostgreSQL major version.

Create a full backup with `pg_dump` and first restore it into an empty
test database with `pg_restore`. Compare items, invoices, line items,
and original texts. Pause new uploads before the final export
so no invoices are missing between the backup and the migration.

Original PDFs also live in the Windows folder `Recchnungen/` and must be
backed up separately and transferred if needed.
Backup automation (systemd timers), the restore drill script and the daily
checks are prepared in `deploy/systemd/` and `scripts/` — see
[`ausfallsicherheit.md`](ausfallsicherheit.md) and the pilot checklist
[`pilot-sf1.md`](pilot-sf1.md); not yet run on a server. Retention and an offsite
backup location are still outstanding. A Docker volume is not a backup.

## Access from the four PCs

Only after a successful test, set `APP_BIND_IP` and `APP_HOST` to the internal
server IP and run `docker compose --env-file .env.server up -d` again. Access
is then `https://SERVER-IP` (see "HTTPS" below). Neither the app nor
PostgreSQL publishes a port; only the HTTPS proxy does (80 and 443).

Login follows the POS-system pattern: employees log in with just their
till number; managers additionally with a password. Only branch managers and
head office may upload, import, and delete documents; booking rights per role
are described in `architektur.md`, "Booking rights as of 2026-09-24". Network
access should still only be granted to authorized store PCs (and, for phones,
the approved store Wi-Fi), with no internet port forwarding. Server
administration must review Docker port exposure and firewall rules together.
Per the security review of 2026-09-24, HTTPS, a limit on failed logins, and
network separation from the guest Wi-Fi are **mandatory before deployment in
the store**. HTTPS (below) and the login lockout are built; network
separation happens during server setup — see [`sicherheit.md`](sicherheit.md),
S1/S2/S5–S7.

## HTTPS (security S1, 28.09.2026)

The `proxy` service (Caddy, `Caddyfile`) terminates HTTPS and forwards to the
app inside the Docker network. Caddy runs its own local certificate authority
("Sportfabrik Inventory - 2026 ECC Root", valid 10 years); the server
certificate is issued for `APP_HOST` and renewed automatically. The app sets
the session cookie `Secure` (`SESSION_HTTPS_ONLY=true` in `compose.yaml`), so
logging in over plain HTTP is no longer possible. Plain HTTP on port 80 only
redirects to HTTPS and hands out the root certificate.

- `APP_HOST` must be exactly what people type in (IP or internal host name).
  Changing it issues a new server certificate; devices keep trusting the root.
- The root certificate and its key live in the Docker volume `caddy_data`.
  **Back it up.** If it is lost, every PC and phone must trust a new root.
- Camera scanning in the browser only works over trusted HTTPS.

### Trust the root certificate once per device

Download: `http://APP_HOST/sportfabrik-ca.crt`. Before trusting it, compare its
SHA-256 fingerprint with the one on the server:

```sh
docker compose --env-file .env.server exec proxy cat /data/caddy/pki/authorities/local/root.crt \
  | openssl x509 -noout -fingerprint -sha256
```

- **iPhone/iPad:** open the link in Safari, allow the download. Settings →
  "Profile Downloaded" → Install. Then Settings → General → About →
  Certificate Trust Settings → switch on "Sportfabrik Inventory - 2026 ECC Root".
- **Android:** download the file, then Settings → Security (and privacy) →
  More security settings → Encryption & credentials → Install a certificate →
  CA certificate → select the file. Menu names vary by manufacturer. Chrome
  uses it; Firefox for Android needs "Use third party CA certificates" in its
  secret settings.
- **Windows PC:** double-click the file → Install Certificate → Local Machine →
  "Trusted Root Certification Authorities". Chrome and Edge use it.
- **Mac:** double-click, then in Keychain Access set the certificate to "Always Trust".

### Local test without Docker (e.g. the current Windows setup)

Run the app as before (`fastapi dev app/main.py`, listens only on
`127.0.0.1:8000`) with `SESSION_HTTPS_ONLY=true` in `.env`, and start Caddy
(single binary from caddyserver.com) in the project folder:

```powershell
$env:APP_HOST = "192.168.1.20"          # this PC's LAN IP
$env:APP_UPSTREAM = "127.0.0.1:8000"
$env:CADDY_CA_DIR = "$env:AppData\Caddy\pki\authorities\local"
caddy run --config Caddyfile
```

Allow Caddy through the Windows firewall for the private network only. Phones
in the same WLAN then open `https://192.168.1.20` after trusting the root.

### Create the first accounts

`SESSION_SECRET` must be set in `.env.server` (see `.env.server.example`),
otherwise the app won't start. Afterwards, create at least one
manager account in the running container:

```sh
docker compose --env-file .env.server exec app python scripts/manage_users.py add-chef 910199 "Fabian Morf"
docker compose --env-file .env.server exec app python scripts/manage_users.py add-mitarbeiter 910141 "Anna Muster"
```

Further commands: `list` (show all accounts), `set-password <kassennummer>`
(reset a manager's password), `remove <kassennummer>` (remove an account).

## Operation

```sh
docker compose --env-file .env.server ps
docker compose --env-file .env.server logs --tail=100 app
docker compose --env-file .env.server stop
docker compose --env-file .env.server start
```

`docker compose down` keeps the data volume. **Do not use `down -v` if
data should be preserved.** Changing the password in `.env.server` does not
automatically change the password of an already-initialized database.

The app no longer creates tables itself. The database schema is managed with Alembic
(folder `migrations/`). The container automatically runs
`alembic upgrade head` on startup, before the app starts (see `Dockerfile`).

## Alembic: one-time switch-over on the existing Windows database

The local Windows database already got its tables through the old
`create_all()` logic, before migrations were introduced. So that
Alembic doesn't try to create the same tables a second time, run this once
in the project folder (with `.venv` activated):

```powershell
alembic stamp head
```

This only records, in a new `alembic_version` table, that the current
state ("baseline schema") has already been reached — it does not change any
existing data or tables. On a new, empty database (e.g. on the
first start on the Linux server), `alembic upgrade head` (run automatically
on container start) instead builds all tables from scratch.

## Future schema changes

1. Adjust the model in `app/core/models.py`.
2. Generate a migration: `alembic revision --autogenerate -m "short description"`.
3. Review the generated file in `migrations/versions/` (autogenerate
   doesn't reliably detect everything, e.g. renames).
4. Test locally: `alembic upgrade head`.
5. Commit the migration together with the code change. On the next deployment
   the container will apply it automatically.

## Mail for bug reports and unknown documents (2026-10-01)

The "Report a problem" button and "Send document to Fabian" send mail to **fabian_morf@icloud.com only** (fixed in `app/services/mail.py`, never taken from input). Without `SMTP_HOST` the buttons show "not set up".

Environment: `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (default `SMTP_USER`), `SMTP_STARTTLS` (1) or `SMTP_SSL=1` for port 465. The store network needs outbound access to that SMTP server; documents are sent only on an explicit click (rule 1 exception, 2026-10-01). Limit: 10 messages per account per hour.
