# Authentik Integration

## Boundary

UniHub Insight trusts identity only when Docker Caddy has completed Authentik
forward-auth and injected the shared proxy secret. The API rejects forwarded
identity headers without the secret.

## Provider configuration

Create or reuse a Proxy Provider for `https://insight.unihub.ro` and attach it to the existing embedded/outpost topology. Confirm that the auth response exposes:

- `X-Authentik-Uid` — stable subject;
- `X-Authentik-Email`;
- `X-Authentik-Name`;
- `X-Authentik-Groups` — pipe-delimited groups, per the Authentik proxy
  contract (commas and semicolons are accepted only for compatibility).

The Caddy site imports the existing `authentik_outpost` and
`authentik_forward` snippets. `authentik_forward` removes browser-supplied
identity headers before copying the trusted Authentik response headers. Adapt
the Caddy site only if the live outpost uses different response-header names;
do not change application headers without updating proxy-auth tests and docs.

## Allowlist mapping

Production has one application-access decision: an exact allowlist containing the owner and general director. Each allowlisted subject receives all existing capabilities (Analytics, Management, Compensation, Finance/P&L and Insight administration) so legacy capability checks cannot hide a module, endpoint, inspect response or export. Module-specific groups such as `unihub-hr` and `unihub-pnl` are not product permissions for Insight.

## Required negative tests

1. No Authentik session → redirect to login.
2. Identity headers without proxy secret → 401.
3. Wrong proxy secret → 401.
4. Either allowlisted user can call every module, inspect and export endpoint and receives complete data.
5. A non-allowlisted authenticated identity receives 403 for the application and API.
6. Removing a subject from the allowlist takes effect on the next verified request.
7. Browser-supplied `X-Authentik-*` and `X-UniHub-Proxy-Secret` headers are
stripped by Caddy; only the API upstream receives the Caddy-injected secret.

## Secret handling

Generate with `openssl rand -hex 32`. Store the same value as
`UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET` in `/etc/unihub-insight/insight.env` and
as `UNIHUB_INSIGHT_PROXY_SECRET` in the private Docker Caddy `.env`. Never put
it in Authentik claims, browser JavaScript, Git, systemd unit text or logs.
