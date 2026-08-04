---
title: UniHub Insight roadmap
status: active
created: 2026-08-04
---

# Objective

Deliver a professional, desktop-only Retail intelligence product over the complete UniHub Retail data domain, while preserving one operational source of truth and a maintainable analytical foundation.

## Delivery principles

- Vertical slices before broad placeholder implementation.
- One metric catalog, one scope model, one authorization boundary.
- Read-only by default; operational actions deep-link to Retail.
- Every phase has observable acceptance gates.
- No platform expansion without measured need.

# P0 — Foundation and first truth path

## P0.1 Repository and engineering baseline — implemented

- monorepo with `apps/web` and `apps/api`;
- pinned runtimes and dependencies;
- format, lint, strict typecheck, test and build commands;
- manual verification workflow to conserve GitHub Actions minutes;
- canonical architecture, product, data and deployment documentation.

**Gate:** clean checkout installs and `npm run verify` passes.

## P0.2 Desktop analytical shell — implemented

- full-width desktop workspace;
- collapsible sidebar and persistent theme;
- typed navigation;
- global period/comparison/firm/RM/ASM/store/agent filters in URL;
- dependent filter options and reset behavior;
- explicit minimum desktop viewport.

**Gate:** search URL reproduces the same scope after refresh and navigation.

## P0.3 Overview vertical slice — implemented in demo, live adapter prepared

- coherent Overview endpoint;
- KPI cards, target pace, linear run-rate forecast and comparison;
- contribution, priority table and deterministic alerts;
- 24-column drag/resize dashboard;
- View/Edit mode, reset and versioned local persistence;
- deterministic demo repository;
- PostgreSQL read-only repository over canonical Retail read models.

**Gate:** demo contract/API tests pass; live results reconcile against Retail for the same scope.

## P0.4 Production identity and live data — next

- Authentik BFF/session integration aligned with UniHub Retail;
- dedicated PostgreSQL read role;
- live filter and Overview reconciliation fixtures;
- server-side roles for general analytics, management, HR and P&L;
- request IDs, structured logs and metrics in production runtime.

**Gate:** zero write privilege, role-matrix tests and exact reconciliation for representative network/RM/store/agent scopes.

# P1 — Core analytical product

## P1.1 Metric catalog and dashboard persistence

- versioned metric registry with unit, aggregation, dimensions and permissions;
- widget configuration schema;
- Insight-owned tables for dashboards, widgets, layouts and presets;
- optimistic concurrency and layout migration;
- personal and shared read-only dashboards.

**Gate:** changing a metric definition cannot rewrite historical saved meaning silently.

## P1.2 Sales Intelligence

- Pace: MTD actual, target, forecast and benchmarks;
- Trend: monthly/YTD/annual comparison;
- Mix: category, subcategory, brand and product;
- Transactions: receipts, 2+ accessories, average receipt, returns;
- Calendar: day/week/month heatmaps.

**Gate:** every total reconciles to Retail and all charts expose the backing table.

## P1.3 Performance

- network → RM → ASM → store → agent drill-down;
- rankings, distributions, heatmaps and scatter plots;
- consistency and volatility over time;
- explicit rule-based attention states;
- visit indicators where FieldOps contracts permit them.

**Gate:** drill-down conserves totals and transfers follow documented historical identity rules.

## P1.4 Custom dashboards

- widget catalog and compatible visualization choices;
- local filters with visible inherit/augment/override/ignore state;
- duplicate, resize, reorder, fullscreen and inspect-data;
- Director, RM, Finance and Risk templates;
- CSV/XLSX/PNG export contracts.

**Gate:** invalid metric/dimension/chart combinations are impossible to save.

# P2 — Commercial and people intelligence

## P2.1 Campaigns

Promo, Incentive, Concurs, Focus and Folii premium: target/actual, coverage, adoption, discount, contribution, rankings and participation gaps. No unsupported causal claims.

## P2.2 Workforce

Active headcount, entries, exits, transfers, tenure, staffing coverage, days worked, productivity and stability.

## P2.3 Grile and compensation

Grile trends and distributions; salary structure, median/average, variable/fixed components, payroll/sales and payroll/profit; strict HR authorization and aggregate suppression.

**P2 gate:** sensitive contracts remain inaccessible without server-side capability, including direct endpoint calls and exports.

# P3 — Finance and planning

## P3.1 Finance & P&L

Revenue, cost, profit, margin, actual/estimate, reconciliation, waterfall, profitability, break-even and salary ratios. Store selection preserves historical identity rules.

## P3.2 Planning

Current and 12-month forecast, target gap, accuracy history, versioned base/upside/downside scenarios and sensitivity to staffing, salary, VAT and margin.

**P3 gate:** financial values reconcile to cent and rules are effective-dated/versioned.

# P4 — Operational maturity

Production RUM/web vitals, API/query SLI dashboards, bounded exports, accessibility/browser regression, backup/restore for Insight metadata, canary/rollback and optimization only for measured hotspots.

# Definition of 1.0

UniHub Insight reaches `1.0` when Sales, Performance, Campaigns, Workforce, Finance and Planning are live; dashboard configuration is persisted server-side; access controls and exports are verified; and the seven-day production performance gates pass on representative usage.
