# UniHub Insight Operations

This directory contains the complete pre-deploy package. No script executes against a server automatically.

## Runtime ownership

- `/opt/unihub-insight/releases/<SOURCE_SHA>` — immutable release directories;
- `/opt/unihub-insight/current` — atomic active symlink;
- `/etc/unihub-insight/insight.env` — root-owned runtime secrets, mode `0640`;
- `unihub-insight-api.service` — read API;
- `unihub-insight-migrate.service` — one-shot metadata migration;
- PostgreSQL authorities `unihub_insight_reader`, `unihub_insight_metadata`,
  `unihub_insight_migrator` — NOLOGIN, explicit and non-owning;
- PostgreSQL owner `unihub_insight_schema_owner` — NOLOGIN owner of schema
  `insight`, activated only with `SET LOCAL ROLE` by the migration runner;
- process login identities — separate analytics, metadata and migration
  connections; no direct object ACLs or ownership;
- Nginx and Authentik remain the public identity boundary.

## First installation sequence

1. As the `unihub` database owner, create the Insight authorities, process
   identities and pre-owned `insight` schema with
   `postgres/roles-before-migration.sql.template`.
2. Create `/etc/unihub-insight/insight.env` from `env/insight.production.example`; generate the proxy secret with `openssl rand -hex 32`.
3. Install the systemd units from `systemd/` and run `systemctl daemon-reload`.
4. Configure the Authentik provider/outpost and adapt `nginx/unihub-insight.conf.template` to the existing UniHub environment.
5. Deploy one exact source SHA with `scripts/deploy-release.sh SOURCE_DIR SOURCE_SHA`.
6. Run `postgres/metadata-grants-after-migration.sql` only as a compatibility
   check: migration `001` grants metadata CRUD explicitly on `dashboards`.
7. Run `scripts/preflight.sh` and `scripts/smoke.sh`.

## Release guarantees

`deploy-release.sh` installs locked dependencies, runs the full repository verification, builds the exact release, switches the symlink atomically, applies immutable migrations and restores the previous application release if health checks fail. Metadata migrations are forward-only; application rollback is allowed only while the previous release accepts the current metadata schema.

## Authentik boundary

Nginx performs forward-auth, copies only response headers from the trusted outpost and overwrites `X-UniHub-Proxy-Secret`. The public client must never choose identity headers or the proxy secret. Keep the secret in a root-readable Nginx snippet and `/etc/unihub-insight/insight.env`, never in Git.

## Backups

Run `backup-metadata.sh` before every migration and daily afterward. It enters
the isolated schema owner through PostgreSQL's `--role` option, keeps 30 days
by default, and never reads Retail business data. `restore-metadata.sh`
requires `--confirm`, stops the API, restores only schema `insight`, restarts
and runs smoke checks.

## Remaining server-only validation

The repository can be completed without server access, but these gates cannot be closed truthfully before installation: exact schema privileges, Authentik header names, live total reconciliation, query plans and latency on production volume, public TLS/routing and seven-day RUM/API SLI evidence.
