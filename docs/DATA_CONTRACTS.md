# Data Contracts

## Response metadata

Every analytical response includes period/range, comparisons, scope, `analytical_snapshot_id`, data mode, currency and generated time. Source metadata is domain-specific and includes cutoff, final/open state, coverage numerator/denominator, source generation, authority/head, rule/metric version, status and warnings. `as_of` is the last covered business date, not response time; Sales cutoff is never reused implicitly for Finance, HR or Forecast.

One dashboard render resolves one eligible snapshot from `completed/promoted` generations. All widget queries, inspect and export reuse it. Consumer compatibility is additive N/N-1 across Retail publisher and Insight consumer.

## Bounded query contract

The request is finite: metric IDs + versions, dimensions, time range/grain, filters by stable entity IDs, simultaneous comparisons, sort and limit. A server-side batch contains at most 12 widgets, resolves and rechecks one eligible snapshot under one deadline/cancellation context, and returns data/error independently per widget. SQL, arbitrary formulas and client-provided functions are invalid.

Saved widgets persist `metric_id`, `metric_version` and `query_contract_version`. Inspector and exports execute the same query and snapshot server-side; they do not reconstruct analytical rows from UI payloads.

## Initial metric definitions

| ID | Definition | Unit | Missing policy |
| --- | --- | --- | --- |
| `sales.total` | Sum of net `total_sales` in scope | RON | zero only for known covered empty scope |
| `target.total` | Sum of store target represented by scope | RON | target absence remains distinguishable |
| `target.progress_pct` | `sales.total / target.total * 100` | % | null when target <= 0 |
| `forecast.linear` | `sales.total / covered_day * days_in_month` | RON | actual for finalized month; null without cutoff |
| `receipts.total` | Sum of canonical receipt counts | integer | same coverage rule as sales |
| `receipt_2plus_pct` | `receipt_2plus_count / receipt_count * 100` | % | null when receipt count is zero |
| `quantity.total` | Sum of net accessory quantity | integer | returns reduce quantity |

The linear forecast is explicitly labeled run-rate; it is not the persisted AI forecast used elsewhere in UniHub.

## Comparison semantics

- `previous-month`: same scope against the immediately preceding calendar month.
- `previous-year`: same calendar month one year earlier.
- `none`: comparison fields are null.

For an open current period, future actual points are null, never repeated last values.

## Scope rules

- Hierarchy: company → RM → ASM → store → agent.
- Store selection is ordered, deduplicated and supports multiple `site_code` values.
- `site_code` is the stable operational store key.
- Current agent identity can use reporting label plus site scope only for the bounded current slice; stable effective-dated entity IDs are mandatory before cross-store longitudinal analysis.
- Selected store can dominate historical parent filters where the Retail contract requires it.

## Retail invariants inherited

- `Cartele` are excluded from normal accessory KPIs.
- Distribution / `TR %` locations are excluded from ordinary Retail KPI scope.
- Quantities are net.
- Identical source rows are not deduplicated as transactions.
- Snapshot and historical fallback coverage are explicit.
- Salary totals follow the Retail salary contract.

## Risk and alerts

Initial alerts are deterministic rules, not machine-learning scores. They expose the rule outcome and entity label. Thresholds move into the versioned metric/rule catalog before production expansion.

## Domain contracts and privacy

- Campaign mechanisms remain separate and carry their own cutoff/status/eligibility authority; they are not summed without a defined metric.
- Workforce movements come from official effective-dated events, never inferred only from missing sales.
- Compensation reads an aggregate Retail view only. No direct `salary_records`, `agent_salary_links`, names or private IDs remain granted. Total uses all rows, average uses values at least 2,000 RON, median uses all values; cohorts of one or two are suppressed across KPI, series, inspect and export, including differencing attacks through filters.
- Finance explicitly marks `actual`/`estimated` and authority. `__FINANCE_UNALLOCATED__` belongs in company totals and never in store/RM detail. Shadow or unpromoted generations are unavailable, not actual.
- Planning forecast identifies run, horizon, method/model, input cutoff and coverage. Target scenarios identify scenario, revision, status, rule-set hash and snapshot; drafts are not implicitly shared truth.

Retail migration 047 is intentionally additive for consumer N/N-1. Insight RC1 reads only the approved v1 views, while legacy Finance/Planning raw grants are revoked only after two compatible Insight releases and a verified B→A rollback. This temporary publisher compatibility does not authorize new Insight code to query raw tables.

## Export contract

XLSX/CSV/PNG apply the same capability, scope ceiling, ACL, snapshot and suppression as the API. Tabular exports are bounded/paged, cancellable and audited, use native numeric cells, neutralize formula injection and carry metadata/warnings. PNG is non-persistent by default and its filename/options are sanitized.

## Metric catalog fields

`id`, `version`, display name, description, unit, aggregation, formula reference, allowed dimensions/grains, compatible analytical shapes/`ChartSpec`, comparison policy, missing policy, suppressibility, capability, source authority and effective dates.
