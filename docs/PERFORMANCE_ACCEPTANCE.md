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

The gate requires seven clean days and at least 100 real requests per main route. Demo and synthetic load timings do not qualify. Instrumentation, live health and the bounded concurrency probe are present; the complete seven-day 1.0 gate over all specialized modules is not yet closed.

## Measurement

- API records route-template, method, status class and duration only.
- Browser reports only LCP and INP with finite rating/navigation labels.
- Prometheus scrapes the local `/metrics` endpoint.
- Query profiling uses `pg_stat_statements` and `EXPLAIN (ANALYZE, BUFFERS)` on a production-like copy when possible.
- Request IDs correlate Caddy, API and database investigation without logging sensitive payloads.

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

Chart POC also measures ECharts bundle/chunk, first render, resize, frame time and browser memory at 1180/1440/1920/ultrawide, including a 100×36 heatmap and scatter up to the documented Canvas threshold. Canvas/SVG is selected from evidence.

### Canvas POC — 2026-08-06

The reproducible Chromium case in `apps/web/e2e/critical-surfaces.spec.ts` renders a 10-widget Regional Manager dashboard with a 3,600-cell heatmap and a 5,000-point scatter, then performs 20 width changes and three Configurare ↔ Vizualizare remount cycles. The gate is first render <8,000 ms, resize blocking p95 <200 ms and post-GC heap growth <64 MiB.

Final focused evidence: first render 5,608.9 ms, resize blocking p95 166.8 ms, heap 110,365,609 → 106,961,052 bytes (−3,404,557 bytes). Canvas remains the supported renderer; this synthetic pass does not authorize SVG and does not count toward the production RUM gate.

Reproducible functional browser coverage runs with `npm run browser:qa`. It does not replace the production RUM/load gate or owner visual acceptance.

Run the bounded synthetic API/concurrency probe on the primary against the private UDS, after loading the root-only runtime environment without printing it:

```bash
set -a
source /etc/unihub-insight/insight.env
set +a
/opt/unihub-insight/current/apps/api/.venv/bin/python \
  /opt/unihub-insight/current/ops/scripts/load-gate.py \
  --period 2026-08 --iterations 20 --concurrency 5
```

The probe covers Overview, every native module, one 10-widget mixed batch and concurrent inspect/CSV/XLSX traffic. Its JSON is explicitly marked `synthetic`; passing it closes only the bounded concurrency check, never the seven-day/100-real-request RUM and API SLI gate.

## Failure criteria

- any ordinary request exceeds the hard deadline;
- p95 regression above 20% during import/export activity;
- unbounded metric labels or URLs in Prometheus;
- monotonically growing browser/API memory after repeated navigation;
- query plan performs an avoidable raw full scan where an approved aggregate exists;
- future actual data is rendered as repeated values instead of gaps;
- timeout or cancellation leaves a database query running beyond its server timeout.
