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

## Capability mapping

| Capability | Default groups |
| --- | --- |
| General analytics | `unihub-manager`, `unihub-analytics`, `unihub-admin`, `authentik Admins` |
| Management / Workforce / Planning | `unihub-manager`, `unihub-admin`, `authentik Admins` |
| Compensation | `unihub-hr`, `unihub-admin`, `authentik Admins` |
| Finance & P&L | `unihub-pnl`, `unihub-admin`, `authentik Admins` |
| Insight administration | `unihub-admin`, `authentik Admins` |

Group mapping is configurable through the production environment file. Admin capability does not silently create HR/P&L access unless the group is also present in those configured lists.

## Required negative tests

1. No Authentik session → redirect to login.
2. Identity headers without proxy secret → 401.
3. Wrong proxy secret → 401.
4. General analytics user calling Compensation or Finance directly → 403.
5. Shared dashboard containing a sensitive module without capability → absent/404.
6. User losing a group → capability disappears on the next verified request.
7. Browser-supplied `X-Authentik-*` and `X-UniHub-Proxy-Secret` headers are
   stripped by Caddy; only the API upstream receives the Caddy-injected secret.

## Secret handling

Generate with `openssl rand -hex 32`. Store the same value as
`UNIHUB_INSIGHT_TRUSTED_PROXY_SECRET` in `/etc/unihub-insight/insight.env` and
as `UNIHUB_INSIGHT_PROXY_SECRET` in the private Docker Caddy `.env`. Never put
it in Authentik claims, browser JavaScript, Git, systemd unit text or logs.
