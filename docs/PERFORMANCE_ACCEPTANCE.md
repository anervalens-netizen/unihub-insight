# Performance Acceptance

## Budgets

| Surface | Initial production gate |
| --- | --- |
| Overview warm p95 | < 1,000 ms |
| Sales / Performance warm p95 | < 2,000 ms |
| Other ordinary analytical routes p95 | < 2,000 ms |
| Hard request deadline | 8,000 ms |
| UI interaction blocking task | < 200 ms |
| Layout drag/resize | local, no network dependency |
| LCP p75 | < 2,500 ms |
| INP p75 | < 200 ms |

The gate requires seven clean days and at least 100 requests per main route. Demo timings do not qualify.

## Measurement

- API records route-template, method, status class and duration only.
- Browser reports only LCP and INP with finite rating/navigation labels.
- Prometheus scrapes the local `/metrics` endpoint.
- Query profiling uses `pg_stat_statements` and `EXPLAIN (ANALYZE, BUFFERS)` on a production-like copy when possible.
- Request IDs correlate Nginx, API and database investigation without logging sensitive payloads.

## Optimization order

1. Confirm the business result and scope.
2. Remove duplicate requests and calculations.
3. Use canonical daily/monthly reporting models.
4. Batch independent reads under the same request deadline.
5. Add or change an index only with measured plans before/after.
6. Add materialization only for a proven repeated scan.
7. Consider caching or another analytical datastore only after the preceding options fail.

## Load scenarios

Measure at minimum:

- five concurrent Overview users;
- three mixed-module custom dashboards with 8–12 widgets;
- one Finance dashboard and one Compensation dashboard under authorized users;
- export/inspect-data while ordinary dashboards load;
- current open month and a 12-month historical interval;
- broad network scope and narrow store/agent scope.

## Failure criteria

- any ordinary request exceeds the hard deadline;
- p95 regression above 20% during import/export activity;
- unbounded metric labels or URLs in Prometheus;
- monotonically growing browser/API memory after repeated navigation;
- query plan performs an avoidable raw full scan where an approved aggregate exists;
- future actual data is rendered as repeated values instead of gaps;
- timeout or cancellation leaves a database query running beyond its server timeout.
