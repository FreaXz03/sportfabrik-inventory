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

Test address: http://127.0.0.1:8080. The containers use a new, separate
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
Backup automation, retention, an offsite backup location, and the
restore test are still outstanding. A Docker volume is not a backup.

## Access from the four PCs

Only after a successful test, set `APP_BIND_IP` to the internal server IP
and run `docker compose --env-file .env.server up -d` again.
Access is then via `http://SERVER-IP:8080`. PostgreSQL does not publish a port.

Login follows the POS-system pattern: employees log in with just their
till number; managers additionally with a password. Only manager accounts may
upload, import, and delete invoices; employees can search
items and view invoices. Network access should still only be granted to authorized
store PCs, with no internet port forwarding. Server administration must
review Docker port exposure and firewall rules together. Per the security review
of 2026-09-24, HTTPS is **mandatory before deployment in the store**
(otherwise passwords and sessions travel in cleartext on the network), as is a limit on
failed login attempts and network separation from the guest WiFi — see
[`sicherheit.md`](sicherheit.md), S1/S2/S5–S7. Original note: add HTTPS as needed before
go-live.

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
