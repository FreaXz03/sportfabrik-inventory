# Homeserver development instance

Installed on 30 October 2026 on explicit user request. Production remains separate and unchanged.

## Access and isolation

- Development URL: `https://sfserver.tailb8a158.ts.net:8454` (private Tailscale access only).
- Source: `/home/sfadmin/projects/sportfabrik-inventory`, `working/entwicklung`.
- Compose definition: `compose.development.yaml`, project `sportfabrik-inventory-dev`.
- Runtime configuration: `/home/sfadmin/homeserver/sportfabrik-inventory-dev`. Newly generated database/session secrets stay in the private server environment file there; never print, commit or reuse production credentials.
- App image: `sportfabrik-inventory-dev:working`; host binding only `127.0.0.1:8097`.
- Tailscale Serve provides HTTPS on port 8454 and forwards to that loopback port. No Funnel/public endpoint was enabled.
- PostgreSQL 18 database/user: `inventory_dev`; database has no host port.
- Separate Compose network `sportfabrik-inventory-dev_development`, database volume `sportfabrik-inventory-dev_dev_postgres_data` and file volume `sportfabrik-inventory-dev_dev_files`.
- App runs as non-root `inventory` (UID 10001); its own `/srv/inventory/uploads` volume is writable. No production files, volumes or networks are attached.
- `SESSION_COOKIE_NAME=sportfabrik_dev_session` and an independent session secret prevent the browser from mixing development and production sessions on the same hostname. Ports alone do not isolate cookies. The default cookie name remains `session`, and Secure/HttpOnly/SameSite behavior is unchanged.
- The app's current upload flow does not permanently retain source PDFs; the dedicated volume does not change that behavior.

The initial database contains reference data from migrations but no articles, documents, movements or user accounts. Existing accounts/credentials were not copied. Account identity and role were requested from the owner and remain pending; no new account or administrative rights were silently granted. A password must be set interactively on the server, not sent in chat.

The containers restart after a host reboot, but code updates are deliberate. There is no automatic branch watcher, Git pull, production deployment or background change agent.

## Deliberate development updates

First inspect status and the branch, fetch origin and fast-forward only when clean. Preserve unrelated edits. Use the development repository only. Back up development data before migrations once test data needs to be retained. Then, on an explicit development deployment request:

```sh
cd /home/sfadmin/projects/sportfabrik-inventory
docker compose --env-file /home/sfadmin/homeserver/sportfabrik-inventory-dev/.env.server -f compose.development.yaml config -q
docker compose --env-file /home/sfadmin/homeserver/sportfabrik-inventory-dev/.env.server -f compose.development.yaml up -d --build
docker compose --env-file /home/sfadmin/homeserver/sportfabrik-inventory-dev/.env.server -f compose.development.yaml ps
```

Do not run Compose's expanded configuration output: it would expose secrets. `config -q` validates without displaying values. The image embeds the source at build time; a later Git push alone does not update the running app. Production's default `compose.yaml`, main branch and source directory must not be used for these commands.

## First account

After the owner explicitly specifies the desired account identity and role, use the existing interactive account-management command. For example, replace the placeholders with the approved values and select the appropriate role command:

```sh
docker exec -it sportfabrik-inventory-dev-app-1 python scripts/manage_users.py add-admin APPROVED_NUMBER "APPROVED_NAME"
```

The example does not authorize creating an admin. Manager/employee roles use the existing `add-chef` / `add-mitarbeiter` commands and branch assignments. Existing authentication and role checks apply.

## Stop and recovery

Stop only this stack while retaining its volumes:

```sh
cd /home/sfadmin/projects/sportfabrik-inventory
docker compose --env-file /home/sfadmin/homeserver/sportfabrik-inventory-dev/.env.server -f compose.development.yaml stop
```

To remove only its Tailscale route, an authorized server administrator can run `tailscale serve --https=8454 off`. Never reset all Serve routes. The pre-change Serve metadata recovery copy is `/home/sfadmin/homeserver/sportfabrik-inventory-dev/tailscale-serve-before.json` (protected permissions). Existing routes were compared against this copy and verified unchanged. Never use `down -v` when development data must be retained. Source changes are recoverable through Git; no production data restore is needed for this separate initial setup.

## Verification on 30 October 2026

- Development Compose validated without displaying secrets; both new containers healthy.
- All migrations applied on the empty PostgreSQL 18 development database, through `a20261028`.
- HTTPS login returned HTTP 200 through the new Tailscale endpoint; local database health returned HTTP 200. Remote-device connectivity still depends on the existing tailnet membership/access rules and was not independently tested from another device.
- Own mounts/network and loopback-only app port verified; database port not published. Writable file-volume check passed as the app user.
- Production app/database/proxy container IDs, start times and image identities were unchanged. Production app/database remained healthy.
- Every pre-existing Tailscale Serve entry was preserved; no public Funnel was enabled.
- A separate temporary `inventory_dev_validation` database was migrated and used for synthetic receiving checks: mixed EAN receipt rejected atomically, received quantities/status/date unchanged on rejection, valid partial receipt accepted, internal and additional EAN assignment accepted, retry booked once and stock reconciled. An initial synthetic additional identifier had an invalid check digit and was correctly rejected; the fixture was corrected and the complete check passed from a fresh temporary database. The temporary database was dropped afterwards.
- Actual development database verified empty of articles, documents, stock movements and accounts after validation.
- New cookie-name regression failed before implementation and passed after the optional setting was added; the default cookie and secure settings remain unchanged.
- Full isolated application suite: **391 passed, 16 skipped**, one upstream Starlette deprecation warning. No private document fixtures were supplied.
- Vault files were not edited. Production was not rebuilt, restarted, migrated or updated.

Account provisioning and a signed-in browser walkthrough remain pending the owner's account/role decision. Physical phone, scanner and POS acceptance are separate checks; this PostgreSQL smoke test is not a complete PostgreSQL concurrency or restore test suite.
