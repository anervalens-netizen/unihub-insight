# Data Contracts

## Response metadata

Every analytical response includes period/range, comparisons, scope, `analytical_snapshot_id`, data mode, currency and generated time. Source metadata is domain-specific and includes cutoff, final/open state, coverage numerator/denominator, source generation, authority/head, rule/metric version, status and warnings. Queries that combine domains expose every required source, not only the primary module source. `as_of` is the last covered business date, not response time; Sales cutoff is never reused implicitly for Finance, HR or Forecast. Every catalog metric carries a stable versioned `formula_reference`; the generic legacy reference is not accepted for active metrics.

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
| `visits.total` | Count of eligible FieldOps visits, grouped by visit-author Team Leader snapshot | integer | missing period remains missing |
| `visits.distinct_stores` | Distinct visited `site_code` values in scope | integer | missing period remains missing |
| `visits.avg_completion` | Visit-count-weighted FieldOps completion average, derived from the 19 canonical visit fields | % | null without eligible visits |
| `visits.checklist_score` | Visit-count-weighted mean of the five boolean checklist checks | % | null without eligible visits |

The linear forecast is explicitly labeled run-rate; it is not the persisted AI forecast used elsewhere in UniHub.

## Comparison semantics

- `previous-period`: same scope against the immediately preceding calendar period.
- `previous-year`: same calendar month one year earlier.
- `recent-average`: arithmetic mean of the previous three available primary points; the current point is excluded and missing points are not replaced with zero.
- `target`: the approved target carried by the same analytical row.
- `forecast`: the approved Planning forecast and only for catalog combinations that expose it; it is never synthesized from a missing authority.

The five tokens may be requested simultaneously only when the metric's versioned `allowed_comparisons` permits them and the query has the `time` dimension. Each becomes a separate typed dataset dimension/series; one token never overwrites another. Unsupported combinations fail per widget instead of returning a silently null or semantically different series. Temporal references execute with the same scope and eligible snapshot as the primary query. A source that is missing or `unavailable` is classified before repository fetch and remains unavailable, including native module routes.

For a wider range, the range bounds the time-series and matrix rows. Current KPI, mix and ranking cards remain explicitly labeled for the selected end period; they are not presented as range aggregates unless their metric contract defines that aggregation.

For an open current period, future actual points are null, never repeated last values.

## Scope rules

- Hierarchy: company → RM → ASM → store → agent.
- Store selection is ordered, deduplicated and supports multiple `site_code` values.
- `site_code` is the stable operational store key.
- Current agent identity can use reporting label plus site scope only for the bounded current slice; stable effective-dated entity IDs are mandatory before cross-store longitudinal analysis.
- Selected store can dominate historical parent filters where the Retail contract requires it.
- Visits add `team_leader` as an analytical dimension. The stable key and label come from the visit-author snapshot; the store's current ASM never substitutes the author. Firm/RM/ASM/store filters use the current `stores` enrichment, while `agent` is incompatible and rejected.

## Retail invariants inherited

- `Cartele` are excluded from normal accessory KPIs.
- Distribution / `TR %` locations are excluded from ordinary Retail KPI scope.
- Quantities are net.
- `reporting_sales_day_v1` expune numai zile observate din head-ul Sales eligibil. `coverage_state=observed` nu afirmă acoperire completă; zilele fără rând rămân missing, iar `return_quantity` păstrează semnul negativ. Bonurile de retur nu se deduc din agregatele pe produs.
- Sub-view-ul Sales Transactions expune numai `receipts.total`, `receipts.average_value` și `receipt_2plus_pct` din contractul agregat. Nu reconstruiește linii de bon și nu etichetează cantitatea negativă drept număr de bonuri retur.
- Identical source rows are not deduplicated as transactions.
- Snapshot and historical fallback coverage are explicit.
- Salary totals follow the Retail salary contract.

## Risk and alerts

Initial alerts are deterministic rules, not machine-learning scores. They expose the rule outcome and entity label. Thresholds move into the versioned metric/rule catalog before production expansion.

## Domain contracts and privacy

- Campaign mechanisms remain separate and carry their own cutoff/status/eligibility authority; they are not summed without a defined metric. Focus Top/Bottom folosește numai magazine observate și `campaigns.focus_share`; nu afirmă coverage, adopție sau cauzalitate.
- Workforce movements come from official effective-dated events, never inferred only from missing sales.
- Visits read only `reporting_visit_month_v2`; draft rows, distribution/`TR %` locations and `Cartele` are excluded. `avg_completion` is recalculated from the 19 canonical FieldOps fields, not from a stale persisted percentage. Performance and Workforce expose the same Visits slice and source metadata, so their native widgets, query batch, inspect and XLSX cannot drift to the legacy ASM projection.
- Compensation reads an aggregate Retail view only. No direct `salary_records`, `agent_salary_links`, names or private IDs remain granted. Total uses all rows, average uses values at least 2,000 RON, median uses all values; cohorts of one or two are suppressed across KPI, series, inspect and export, including differencing attacks through filters.
- Finance explicitly marks `actual`/`estimated` and authority. `__FINANCE_UNALLOCATED__` belongs in company totals and never in store/RM detail. Shadow or unpromoted generations are unavailable, not actual.
- Planning forecast identifies run, horizon, method/model, input cutoff and coverage. `completed` este numai candidat: v2 publică exclusiv head-ul promovat, cu hash/row-count înghețat, approval artifact, revision CAS și ledger append-only. Target scenarios identify scenario, revision, status, rule-set hash and exact registry-backed snapshot; drafts și scenariile legacy nu devin implicit shared truth. Accuracy păstrează KPI-ul server-side și vizualizează perechile Actual × Forecast publicate pe magazin; clientul nu recalculează o formulă alternativă.

Retail migration 047 is intentionally additive for consumer N/N-1. Migrations 049–050 add Visits v2 and canonical completion without rewriting FieldOps history. Migration 051 adds `reporting_source_snapshot_v3` and `reporting_planning_scenario_v2`; the current consumer selects these while v1/v2 contracts remain rollback anchors. Migration 051 performs zero business promotions: without an approved Planning head or exact Target snapshot, results stay `partial/unavailable`. Legacy raw grants do not authorize new Insight code to query raw tables.

## Export contract

XLSX/CSV/PNG apply the same capability, scope ceiling, ACL, snapshot and suppression as the API. Tabular exports are bounded/paged, cancellable and audited, use native numeric cells, neutralize formula injection and carry metadata/warnings. PNG is non-persistent by default and its filename/options are sanitized.

## Metric catalog fields

`id`, `version`, display name, description, unit, aggregation, formula reference, allowed dimensions/grains, compatible analytical shapes/`ChartSpec`, comparison policy, `allowed_comparisons`, missing policy, suppressibility, capability, source authority and effective dates.
