# Data Contracts

## Response metadata

Every analytical response includes period/range, comparisons, scope, `analytical_snapshot_id`, data mode, currency and generated time. Source metadata is domain-specific and includes cutoff, final/open state, coverage numerator/denominator, source generation, authority/head, rule/metric version, status and warnings. Queries that combine domains expose every required source, not only the primary module source. `as_of` is the last covered business date, not response time; Sales cutoff is never reused implicitly for Finance, HR or Forecast. Every catalog metric carries a stable versioned `formula_reference`; the generic legacy reference is not accepted for active metrics.

One dashboard render resolves one eligible snapshot from `completed/promoted` generations. All widget queries, inspect and export reuse it. Consumer compatibility is additive N/N-1 across Retail publisher and Insight consumer.

## Bounded query contract

The request is finite: metric IDs + versions, dimensions, time range/grain, filters by stable entity IDs, simultaneous comparisons, sort and limit. A server-side batch contains at most 12 widgets, resolves and rechecks one eligible snapshot under one deadline/cancellation context, and returns data/error independently per widget. SQL, arbitrary formulas and client-provided functions are invalid.

Saved widgets persist `metric_id`, `metric_version` and `query_contract_version`. Inspector and exports execute the same query and snapshot server-side; they do not reconstruct analytical rows from UI payloads.

Native module widgets and custom widgets are both fed by catalog-derived batch queries. Native specialized cards are projections of their exact batch datasets; they do not execute a parallel legacy visual payload. A duplicated custom widget is persisted as a new dashboard version before its new ID is eligible for batch/inspect/export authorization.

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
| `campaigns.promo_sales` / `campaigns.promo_quantity` | Net Retail sales and quantity for products participating in the published Promo generation | RON / integer | null without a promoted campaign head |
| `campaigns.promo_discount` | Canonical Retail Promo discount value | RON | null without a promoted campaign head |
| `campaigns.incentive_sales` / `campaigns.incentive_quantity` | Net Retail sales and quantity for products participating in the published Incentive generation | RON / integer | null without a promoted campaign head |
| `campaigns.incentive_reward` | Canonical Retail Incentive reward | RON | null without a promoted campaign head |
| `campaigns.folii_*` | Promo Folii only where `reporting_campaign_month_v3.mechanism_variant = same_model_screen_camera` | RON / integer | unavailable without the published canonical variant; never inferred from key/title |
| `campaigns.contest_*` | Published Concurs points, Focus/Promo/Price units and prize by contest/site/agent identity | decimal / integer / RON | null without `reporting_contest_month_v1` |
| `sales.portfolio_sales` / `sales.portfolio_net_quantity` | Net sales / quantity on exactly one Sales Portfolio dimension: category, subcategory, brand or product | RON / integer | source-row-missing remains missing |
| `sales.portfolio_return_quantity` | Signed return quantity for the brand or product portfolio roll-up | integer | source-row-missing remains missing |
| `sales.portfolio_receipt_incidence` | Sum of SKU–receipt incidences; it is not a distinct receipt count | integer | source-row-missing remains missing |

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

- Master hierarchy: company → RM → store → agent. ASM remains an internal drill/reconciliation dimension and is not serialized by the primary filter bar.
- RM, store and agent selections are ordered, deduplicated CSV sets; each supports multiple values through the same URL/query/export contract.
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

## Sales Portfolio contract

Sales Portfolio is a monthly, one-dimension-at-a-time roll-up. The permitted
dimensions are exactly `category`, `subcategory`, `brand` and `product`; they
cannot be combined as a free taxonomy query.

- `category` and `subcategory` use `reporting_category_month`. Their controls
  are the sum of `total_sales` and signed net `total_quantity` at the selected
  scope.
- `brand` and `product` use `reporting_item_month`. `brand` is a grouping
  attribute, enriched from `insight.monthly_review_item_month` by
  `(import_month, site_code, agent, item_code)`; that Monthly Review table
  never replaces the Retail item read-model for sales, quantities, returns or
  receipt incidence.
- Product identity is strictly `item_code` (SKU). Name, real-brand and
  category differences remain visible as attribute/label warnings; they never
  split or merge product totals by a display label.
- `return_quantity` remains signed and is available for brand and product.
  Zero- or return-only rows remain in the total and table even where a mix
  chart calculates visual shares only from positive net sales.
- Product `receipt_count` means SKU–receipt incidences: one receipt containing
  multiple SKUs contributes once to every represented SKU. It must never be
  called, summed or compared as a count of distinct receipts. The canonical
  Sales Transactions receipt metrics remain separate.

For the entire network in 2026-06, each of the four roll-ups conserves the
published monthly total of **3,223,513.13 RON** and **33,279 net units**. The
cardinality controls are 6 categories, 20 category/subcategory pairs, 19 real
brands and 1,099 SKU. This is a reconciliation fact for the read-models, not a
claim that SKU receipt incidence equals the network receipt count.

## Risk and alerts

Initial alerts are deterministic rules, not machine-learning scores. They expose the rule outcome and entity label. Thresholds move into the versioned metric/rule catalog before production expansion.

## Domain contracts and privacy

- Campaign mechanisms remain separate and carry their own cutoff/status/eligibility authority; they are not summed without a defined metric. Retail migration 057 publishes immutable v3 campaign rows and snapshot v5. Promo/Incentive reuse the canonical Retail evaluators; `promo_qualifying_bons=NULL` remains absent, never zero. Folii is only `mechanism_variant=same_model_screen_camera`, derived by Retail from the validated definition; Insight never matches a key or title. Focus provenance remains distinct. Concurs reads only `reporting_contest_month_v1`: `focus_units`, `promo_units`, `price_units`, point totals/breakdown, prize, rank/status/warnings and governed agent/site hierarchy; it never consumes person names, CNP or invented sales/score fields.
- Workforce People, Stability, Coverage and Movements are `partial` commercial activity observed in reporting rows, not an official roster. Movements contains only new/reactivated observation; exits and transfers are explicitly unavailable.
- Grile reads only `reporting_grile_month_v2`. Snapshot v6 selects one source for the whole month: the non-empty fenced current projection, otherwise the latest immutable completed full run ordered by terminal instant and id. It never fills individual stores from a different generation; raw Grile tables are not direct Insight sources.
- Visits read only `reporting_visit_month_v2`; draft rows, distribution/`TR %` locations and `Cartele` are excluded. `avg_completion` is recalculated from the 19 canonical FieldOps fields, not from a stale persisted percentage. Performance and Workforce expose the same Visits slice and source metadata, so their native widgets, query batch, inspect and XLSX cannot drift to the legacy ASM projection.
- Compensation reads an aggregate Retail view only. No direct `salary_records`, `agent_salary_links`, names or private IDs remain granted. Total uses all rows, average uses values at least 2,000 RON, median uses all values; cohorts of one or two are suppressed across KPI, series, inspect and export, including differencing attacks through filters.
- Finance explicitly marks `actual`/`estimated` and authority. `__FINANCE_UNALLOCATED__` belongs in company totals and never in store/RM detail. Shadow or unpromoted generations are unavailable, not actual.
- Planning forecast identifies run, horizon, method/model, input cutoff and coverage. `completed` este numai candidat: v2 publică exclusiv head-ul promovat, cu hash/row-count înghețat, approval artifact, revision CAS și ledger append-only. Target scenarios identify scenario, revision, status, rule-set hash and exact registry-backed snapshot; drafts și scenariile legacy nu devin implicit shared truth. Accuracy păstrează KPI-ul server-side și vizualizează perechile Actual × Forecast publicate pe magazin; clientul nu recalculează o formulă alternativă.

Unavailable or partial Compensation, Finance, Planning and Workforce surfaces
mean that the required approved aggregate contract, read-model publication or
eligible head is absent. They do not assert that Retail has no underlying
operational, salary, P&L, forecast or workforce data.

Retail migration 047 is intentionally additive for consumer N/N-1. Migrations 049–050 add Visits v2 and canonical completion without rewriting FieldOps history. Migrations 051–052 add governed Planning v2. Migration 057 adds Campaigns v3, Concurs v1, Grile v1 and snapshot v5; migration 058 adds Grile v2 and snapshot v6 while v5/v1 remain rollout anchors. The current consumer selects snapshot v6, Campaigns v3 and Planning v2. Without the matching approved head, results stay `partial/unavailable`; legacy raw grants never authorize Insight to query raw business tables.

## Export contract

XLSX/CSV/PNG apply the same capability, scope ceiling, ACL, snapshot and suppression as the API. Tabular exports are bounded/paged, cancellable and audited, use native numeric cells, neutralize formula injection and carry metadata/warnings. PNG is non-persistent by default and its filename/options are sanitized.

## Metric catalog fields

`id`, `version`, display name, description, unit, aggregation, formula reference, allowed dimensions/grains, compatible analytical shapes/`ChartSpec`, comparison policy, `allowed_comparisons`, missing policy, suppressibility, capability, source authority and effective dates.
