# Pre-install Gate

## Scope

This gate separates work that can be completed in Git from facts that require the UniHub production server. The repository must not be called production-ready while a server-only gate remains unverified.

## Completed before installation

- Desktop-only analytical shell and URL-persistent global scope.
- Overview plus Sales, Performance, Campaigns, Workforce, Compensation, Finance and Planning contracts.
- Deterministic demo repositories for every module.
- Read-only PostgreSQL adapters over canonical Retail reporting sources.
- Server-side capability matrix and trusted-proxy identity boundary.
- Compensation aggregate suppression and Retail salary-average threshold.
- Versioned metric/widget contracts and compatible chart enforcement.
- Personal/shared dashboard persistence with optimistic concurrency.
- Drag/resize, local filter semantics, inspect-data and CSV export.
- Immutable metadata migrations and checksum registry.
- systemd, Docker Caddy/Authentik, database-role, backup, rollback, smoke and preflight templates.
- Finite-cardinality API/RUM metrics and JSON request logs.
- Local format, lint, strict typing, tests and production build workflow.

## Server-only inputs

The installation operator must supply:

1. Exact PostgreSQL connection endpoints and generated passwords.
2. Existing Authentik outpost URL/provider and verified response header names.
3. DNS/TLS configuration for `insight.unihub.ro` and the existing Cloudflare/Caddy path.
4. The production service account, `/opt/unihub-insight` paths, Caddy site include and read-only mount conventions.
5. A representative set of approved live scopes for reconciliation.

## Installation gate

The first release is `GO` only when all checks below pass:

- analytics role reports `transaction_read_only=on` and cannot create, update or delete;
- metadata role cannot read Retail salary/P&L source tables directly;
- migration registry has no pending, unknown or checksum-mismatched files;
- unauthenticated requests are redirected by Authentik;
- forged identity headers without the proxy secret return 401;
- direct Finance/Compensation endpoints return 403 without their capability;
- network, firm, RM, store and agent control totals reconcile with Retail;
- Compensation scopes below three people return no values or export rows;
- `/livez`, `/readyz`, `/metrics` and public UI smoke checks pass;
- Docker Caddy imports `authentik_forward`, strips/replaces all identity headers and injects the proxy secret only upstream;
- one rollback drill restores the previous application SHA;
- one metadata backup/restore drill succeeds on a disposable database.

## Post-install evidence

Production acceptance remains open until seven consecutive days provide:

- at least 100 requests for each main analytical route;
- warm p95 Overview below 1 second;
- ordinary analytical p95 below 2 seconds;
- no normal request above the configured 8-second deadline;
- no sustained 5xx rate;
- LCP and INP distributions inside the thresholds in `PERFORMANCE_ACCEPTANCE.md`;
- no unexplained divergence from Retail control totals.
