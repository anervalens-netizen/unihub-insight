# UniHub Insight deployment

Insight is built and fully verified on `dell-standby`, then copied as an
immutable artifact to the primary server. The primary does not need
Node/npm/nginx. It needs Docker, the host PostgreSQL client, systemd and the
pinned runtime `uv` at `/opt/unihub-insight/bin/uv` (or `UNIHUB_INSIGHT_UV`).

## Dell release preparation

Run from a clean checkout at the exact commit to deploy:

```bash
SHA="$(git rev-parse HEAD)"
ops/scripts/prepare-release.sh "$PWD" "$SHA" "/var/tmp/unihub-insight-releases/$SHA"
```

The script runs `npm ci`, locked Python sync, `npm run verify` and the
production build on Dell. It records the host, source SHA, verification state
and a digest of `apps/web/dist` in `release-evidence.json`, then removes build
dependencies from the artifact.

Copy the resulting directory to the primary without modifying its contents.
The destination must be unique for that SHA:

```bash
rsync -a "/var/tmp/unihub-insight-releases/$SHA/" \
  server:"/var/tmp/unihub-insight-releases/$SHA/"
```

## Primary topology

Install the units from `ops/systemd/` and configure the root-owned `0600` files
`/etc/unihub-insight/insight.env` and `/etc/unihub-insight/migration.env`.
The API unit loads only the first; migrations and backups use only the second.
The API listens only on `/run/unihub-insight/api.sock`; PostgreSQL is the
Docker container `unihub_postgres` published to host `127.0.0.1:5432`.
Metadata backup/restore runs PostgreSQL 18's `pg_dump`/`pg_restore` inside that
container, avoiding host-client version drift.

`/opt/unihub-insight/current` selects the application release. The separate
`/opt/unihub-insight/schema-current` pointer only advances on deploy and drives
the migration unit. Code rollback never rewinds it, so N-1 can restart or
survive a reboot after an explicitly approved additive migration.

The live `/opt/Mobiup/infra/caddy/Caddyfile` includes the site represented by
`ops/caddy/unihub-insight.caddy.template`. The `unihub-caddy` Compose service
already has these read-only mounts:

```yaml
- /opt/unihub-insight:/opt/unihub-insight:ro
- /run/unihub-insight:/run/unihub-insight:ro
```

The API unit preserves the runtime directory inode across service restarts so
the Caddy bind mount remains valid. Caddy serves the application through the
socket and exposes `/metrics` plus `/ready-metrics` only on its unpublished
Docker-network port `8100` for Prometheus. Both paths remain public `404`.

Set the same random value in the API environment as
`UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET` and in the private Caddy environment as
`UNIHUB_INSIGHT_PROXY_SECRET`. Validate/reload the Docker Caddy configuration
after the site block and mount are installed. The release scripts do not edit
the live Caddyfile or its secrets.

## Install and verify

```bash
sudo install -o root -g root -m 0644 ops/systemd/*.service /etc/systemd/system/
sudo install -o root -g root -m 0644 ops/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo env UNIHUB_INSIGHT_UV=/opt/unihub-insight/bin/uv \
  /var/tmp/unihub-insight-releases/$SHA/ops/scripts/deploy-release.sh \
  /var/tmp/unihub-insight-releases/$SHA "$SHA"
sudo /opt/unihub-insight/current/ops/scripts/preflight.sh
sudo /opt/unihub-insight/current/ops/scripts/smoke.sh
```

`preflight.sh` checks the Dell evidence, immutable build digest and public
`build-info.json`, Docker PostgreSQL/Caddy state, Caddy configuration, the API
socket and internal metrics bridge, migration registry and read-only database
boundary. `smoke.sh` checks local
liveness/readiness, public SPA reachability and public 404 responses for
diagnostics.

For a non-destructive restore drill, restore the latest custom-format dump
into a disposable database. Seed only the empty `public.sales_transactions`
contract required by `insight.monthly_review_item_month`, restore with
`--exit-on-error --no-owner --no-privileges`, verify the migration registry and
metadata relations, then drop the disposable database. Never use the production
restore command for this drill.

Rollback is code-only and keeps the database at its current schema. Before
switching the symlink it verifies that the target contains every applied
migration with the recorded checksum. A migration absent from N-1 is accepted
only when the active release declares its exact version and checksum in
`ops/rollback-compatible-migrations.txt`; this allowlist is reserved for
reviewed additive changes that N-1 can read safely. Any undeclared or checksum-
mismatched migration refuses rollback without stopping the active release:

```bash
sudo /opt/unihub-insight/current/ops/scripts/rollback.sh PREVIOUS_SOURCE_SHA
```

The migration service continues to validate through `schema-current` after
rollback. Reinstall the checked-in systemd units when upgrading an older host
whose migration unit still points at `current`; `deploy-release.sh` refuses
that unsafe topology. On that one-time upgrade, create `schema-current` as an
atomic symlink to the active release before replacing the migration unit; the
next successful deploy advances it.

The database role/grant SQL and `migrate.py` remain Terra-owned and are not
changed by this deployment lane.

## Recurring production release gates

The runtime, roles, secrets, service account, Caddy/Authentik, Cloudflare routing and monitoring are live. Every production candidate must still verify rather than assume:

- approved grants/migrations and the read-only boundary;
- exact artifact SHA/digest and immutable current symlink;
- Caddy config, UDS, Authentik access and public diagnostic 404s;
- representative live reconciliation and authorization negatives;
- backup/restore readiness, metrics/alerts, smoke and rollback path.
