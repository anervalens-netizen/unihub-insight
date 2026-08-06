# UniHub Insight authorization boundary

The browser never supplies trusted identity. Docker Caddy is the only public
boundary:

1. `authentik_outpost` serves the Authentik callback paths.
2. `authentik_forward` performs forward-auth and copies only trusted
   `X-Authentik-*` response headers.
3. Caddy strips browser-supplied identity headers and
   `X-UniHub-Proxy-Secret`.
4. Only the API reverse proxy adds `X-UniHub-Proxy-Secret` from the private
   `UNIHUB_INSIGHT_PROXY_SECRET` environment value.
5. FastAPI verifies the secret and derives capabilities from the copied groups.

The API secret is `UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET` in
`/etc/unihub-insight/insight.env`; the Caddy variable is
`UNIHUB_INSIGHT_PROXY_SECRET`. They must match and must never appear in Git,
browser JavaScript, Authentik claims, systemd unit text or logs.

The migration DSN is isolated in root-only `/etc/unihub-insight/migration.env`.
It is absent from the API runtime environment; systemd reads it only for the
one-shot migration service, while root-owned backup/restore scripts load it
directly.

The analytics reader receives only the enumerated reporting/read-model tables.
Bootstrap explicitly revokes legacy grants on raw sales, salary, visit,
Finance-generation and planning-authority tables; preflight fails if any such
direct `SELECT` privilege reappears.

At the 2026-08-05 baseline, application access is explicitly limited to Andrei, Alexandra and Bogdan. Release evidence must verify the exact Authentik application-group membership as well as capabilities; adding another identity is a security change, not a UI configuration.

Capability defaults and required negative tests live in
[ops/authentik/README.md](../ops/authentik/README.md). Production must verify
no-session redirect, forged-header 401, capability 403, sensitive-module
omission and public 404 responses for `/livez`, `/readyz`, `/metrics`, `/docs`,
`/redoc` and `/openapi.json`.

Dashboard sharing does not replace authorization. `dashboard_acl` enforces subject permission, capability and scope ceiling at read/query/inspect/export; a share cannot grant a data capability or scope the recipient did not already have. Revocation is server-side and versioned. Production acceptance still requires the real three-user negative matrix after RC1 deploy.
