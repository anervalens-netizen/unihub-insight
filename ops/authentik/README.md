# Authentik Integration

## Boundary

UniHub Insight trusts identity only when Nginx has completed Authentik forward-auth and injected the shared proxy secret. The API rejects forwarded identity headers without the secret.

## Provider configuration

Create or reuse a Proxy Provider for `https://insight.unihub.ro` and attach it to the existing embedded/outpost topology. Confirm that the auth response exposes:

- `X-Authentik-Uid` — stable subject;
- `X-Authentik-Email`;
- `X-Authentik-Name`;
- `X-Authentik-Groups` — comma-delimited groups.

Adapt the Nginx template only if the live outpost uses different response-header names. Do not change application headers without updating proxy-auth tests and documentation.

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
7. Browser-supplied `X-Authentik-*` and proxy-secret headers are overwritten by Nginx.

## Secret handling

Generate with `openssl rand -hex 32`. Store the same value in `/etc/unihub-insight/insight.env` and a root-readable Nginx snippet. Never put it in Authentik claims, browser JavaScript, Git, systemd unit text or logs.
