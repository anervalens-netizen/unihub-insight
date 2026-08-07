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
5. FastAPI verifies the secret and checks that the subject belongs to the explicit Insight allowlist.

The API secret is `UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET` in
`/etc/unihub-insight/insight.env`; the Caddy variable is
`UNIHUB_INSIGHT_PROXY_SECRET`. They must match and must never appear in Git,
browser JavaScript, Authentik claims, systemd unit text or logs.

The migration DSN is isolated in root-only `/etc/unihub-insight/migration.env`.
It is absent from the API runtime environment; systemd reads it only for the
one-shot migration service, while root-owned backup/restore scripts load it
directly.

The analytics reader receives only enumerated, versioned reporting/read-model tables. Those contracts must expose all business detail required by the two authorized users, including person-level Compensation and actual/estimated Finance. Keeping arbitrary raw-table grants revoked is a database-hardening rule, not authorization to suppress rows or fields from complete reporting contracts.

The target production allowlist contains exactly two roles: owner and general director. Their exact Authentik subjects are verified during deployment, and both receive the same complete data access. Adding any other identity remains an explicit security change.

Once Authentik admits either allowlisted subject, `insight:analytics` is the only data-read capability used by module routes, query planning, custom dashboards and exports. Legacy `management`, `hr` and `pnl` claims may remain in the identity payload for compatibility, but they do not hide modules or rows.

Allowlist mapping and required negative tests live in [ops/authentik/README.md](../ops/authentik/README.md). Production must verify no-session redirect, forged-header 401, non-allowlisted identity 403, complete module visibility for both authorized users and public 404 responses for `/livez`, `/readyz`, `/metrics`, `/docs`, `/redoc` and `/openapi.json`.

Dashboard sharing does not replace application authorization. `dashboard_acl` may control read/edit/admin over a saved layout, but it must not reduce the business-data visibility of an allowlisted user. Revocation is server-side and versioned. Production acceptance verifies the two authorized subjects plus one non-allowlisted negative identity.

## Boundaries that remain

These controls do not hide business data from the owner or general director:

- Authentik login, exact two-subject allowlist and forged-header/proxy-secret rejection;
- read-only access to Retail, parameterized SQL, timeouts and finite query/export bounds;
- no database credentials, SQL or secrets in the browser;
- sensitive business values are never copied into application logs or monitoring labels;
- missing values stay missing, and `actual`, `estimated`, `legacy`, `draft`, coverage and cutoff remain explicit;
- a filter is unavailable only when the source has no meaningful grain (for example agent allocation in P&L), never because of the user's role;
- `Cartele`, `TR %`, draft and unallocated rows may stay outside a specifically defined KPI, but must remain available in dedicated detail/inspect/export.
