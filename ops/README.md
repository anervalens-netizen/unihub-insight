# UniHub Insight Operations

This directory contains the complete pre-deploy package. No script executes against a server automatically.

## Runtime ownership

- `/opt/unihub-insight/releases/<SOURCE_SHA>` — immutable release directories;
- `/opt/unihub-insight/current` — atomic active symlink;
- `/opt/unihub-insight/schema-current` — forward-only migration-runner symlink;
- `/etc/unihub-insight/insight.env` — root-only API runtime secrets, mode `0600`;
- `/etc/unihub-insight/migration.env` — separate root-only migration
  credential, mode `0600`; never loaded into the API service;
- `unihub-insight-api.service` — read API;
- `unihub-insight-migrate.service` — one-shot metadata migration;
- PostgreSQL authorities `unihub_insight_reader`, `unihub_insight_metadata`,
  `unihub_insight_migrator` — NOLOGIN, explicit and non-owning;
- PostgreSQL owner `unihub_insight_schema_owner` — NOLOGIN owner of schema
  `insight`, activated only with `SET LOCAL ROLE` by the migration runner;
- process login identities — separate analytics, metadata and migration
  connections; no direct object ACLs or ownership;
- Docker PostgreSQL `unihub_postgres` remains the database runtime; the host
  API reaches its published `127.0.0.1:5432` port;
- Docker Caddy `unihub-caddy` and Authentik remain the public identity
  boundary. The API binds only to `/run/unihub-insight/api.sock`; Caddy mounts
  that runtime directory read-only and exposes only `/metrics` on its
  unpublished Docker-network port `8100` for Prometheus. The systemd runtime
  directory is preserved across API restarts so Caddy keeps the same inode.

## First installation sequence

1. As the `unihub` database owner, create the Insight authorities, process
   identities and pre-owned `insight` schema with
   `postgres/roles-before-migration.sql.template`.
2. Create the two root-owned `0600` files from
   `env/insight.production.example` and `env/migration.production.example`;
   generate the proxy secret with `openssl rand -hex 32`.
3. Install the systemd units from `systemd/` and run `systemctl daemon-reload`.
4. Add `caddy/unihub-insight.caddy.template` to the existing Docker Caddyfile;
   mount `/opt/unihub-insight:/opt/unihub-insight:ro` and
   `/run/unihub-insight:/run/unihub-insight:ro` in `unihub-caddy`; set
   `UNIHUB_INSIGHT_PROXY_SECRET` in Caddy's private `.env`.
5. On Dell, run `scripts/prepare-release.sh` to install, verify and build one
   exact source SHA. Transfer that immutable artifact to primary and run
   `scripts/deploy-release.sh SOURCE_DIR SOURCE_SHA` there.
6. Run `postgres/metadata-grants-after-migration.sql` only as a compatibility
   check: migration `001` grants metadata CRUD explicitly on `dashboards`.
7. Run `scripts/preflight.sh` and `scripts/smoke.sh`.
8. Run `scripts/load-gate.py` through the active release Python environment for the bounded synthetic concurrency gate; keep the seven-day real-traffic SLI verdict separate.

## Release guarantees

`prepare-release.sh` is the only step that needs Node/npm: it runs on Dell,
verifies the exact checkout and production build, records `release-evidence.json`
and removes build-time dependencies. On primary, `deploy-release.sh` checks that
evidence, uses `/opt/unihub-insight/bin/uv` (or an explicitly configured `uv`) to
sync only locked runtime Python dependencies, seals the release read-only,
switches the symlink atomically, applies immutable migrations and restores the
previous application release if health checks fail. Primary needs no
Node/npm/nginx. Metadata migrations are forward-only; application rollback is
allowed only while the previous release accepts the current metadata schema.
The migration unit follows `schema-current`, not the rolled-back application,
so a reviewed N-1 remains restartable after an additive migration.

## Authentik boundary

Caddy imports the existing `authentik_outpost` and `authentik_forward` snippets,
strips browser-supplied `X-Authentik-*` and `X-UniHub-Proxy-Secret` headers, then
injects `UNIHUB_INSIGHT_PROXY_SECRET` only on the API upstream. The public client
must never choose identity headers or the proxy secret. Keep the API value in
`/etc/unihub-insight/insight.env` and the Caddy value in its private `.env`,
never in Git. The migration DSN exists only in root-only
`/etc/unihub-insight/migration.env`; systemd reads it for the one-shot
migration service.

## Backups

Run `backup-metadata.sh` before every migration and daily afterward. It enters
the isolated schema owner through PostgreSQL's `--role` option, keeps 30 days
by default, and never reads Retail business data. `restore-metadata.sh`
requires `--confirm`, stops the API, restores only schema `insight`, restarts
and runs smoke checks.

## Remaining server-only validation

The repository can be completed without server access, but these gates cannot be closed truthfully before installation: exact schema privileges, Authentik header names, live total reconciliation, query plans and latency on production volume, public TLS/routing and seven-day RUM/API SLI evidence.
