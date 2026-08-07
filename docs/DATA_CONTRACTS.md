# Data Contracts

## Response metadata

Every analytical response includes period/range, comparisons, scope, `analytical_snapshot_id`, data mode, currency and generated time. Source metadata is domain-specific and includes cutoff, final/open state, coverage numerator/denominator, source generation, authority/head, rule/metric version, status and warnings. Queries that combine domains expose every required source, not only the primary module source. `as_of` is the last covered business date, not response time; Sales cutoff is never reused implicitly for Finance, HR or Forecast. Every catalog metric carries a stable versioned `formula_reference`; the generic legacy reference is not accepted for active metrics.

One dashboard render resolves one coherent Retail snapshot. All widget queries, inspect and export reuse it. A promoted generation is preferred when available, but its absence does not hide canonical rows already accepted and displayed by Retail; those rows carry explicit `legacy`, `actual`, `estimated` or other truthful provenance. Consumer compatibility is additive N/N-1 across Retail publisher and Insight consumer.

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
| `campaigns.contest_*` | Published Concurs integer points, Focus/Promo/Price units and textual prize by contest/site/agent identity | integer / text | null without `reporting_contest_month_v1` |
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

The five tokens may be requested simultaneously only when the metric's versioned `allowed_comparisons` permits them and the query has the `time` dimension. Each becomes a separate typed dataset dimension/series; one token never overwrites another. Unsupported combinations fail per widget instead of returning a silently null or semantically different series. Temporal references execute with the same scope and coherent snapshot as the primary query. Availability classification must consult the canonical Retail source: metadata/head absence cannot preempt the fetch when accepted Retail rows exist.

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

- `Cartele` are excluded from normal accessory KPIs but remain visible in dedicated detail/inspect/export.
- Distribution / `TR %` locations are excluded from ordinary Retail KPI totals but remain visible in dedicated detail/inspect/export.
- Quantities are net.
- `reporting_sales_day_v1` expune numai zile observate din head-ul Sales eligibil. `coverage_state=observed` nu afirmă acoperire completă; zilele fără rând rămân missing, iar `return_quantity` păstrează semnul negativ. Bonurile de retur nu se deduc din agregatele pe produs.
- Sales Transactions păstrează KPI-urile `receipts.total`, `receipts.average_value` și `receipt_2plus_pct`, dar ținta include și antetul/linia canonică de bon disponibilă în Retail pentru drill, inspect și export. Cantitatea negativă nu este etichetată drept număr de bonuri retur.
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

## Domain contracts and authorized visibility

- Campaign mechanisms remain separate and carry their own cutoff/status/eligibility authority; they are not summed without a defined metric. Retail migration 057 publishes immutable v3 campaign rows and snapshot v5. Promo/Incentive reuse the canonical Retail evaluators; `promo_qualifying_bons=NULL` remains absent, never zero. Folii is only `mechanism_variant=same_model_screen_camera`, derived by Retail from the validated definition; that variant is excluded from Promo and Insight never matches a key or title. Focus provenance remains distinct. Concurs reads only `reporting_contest_month_v1`: `focus_units`, `promo_units`, `price_units`, integer point totals/breakdown, textual prize, rank/status/warnings and governed agent/site hierarchy; it never consumes person names, CNP or invented sales/score fields.
- Workforce People, Stability, Coverage and Movements are `partial` commercial activity observed in reporting rows, not an official roster. Movements contains only new/reactivated observation; exits and transfers are explicitly unavailable.
- Grile reads only `reporting_grile_month_v2`. Snapshot v6 selects one source for the whole month: the non-empty fenced current projection, otherwise the latest immutable completed full run ordered by terminal instant and id. It never fills individual stores from a different generation; raw Grile tables are not direct Insight sources.
- Visits official KPI reads `reporting_visit_month_v2`; draft rows, distribution/`TR %` locations and `Cartele` do not alter acel KPI, dar rămân vizibile într-un detail separat cu statusul lor. `avg_completion` is recalculated from the 19 canonical FieldOps fields, not from a stale persisted percentage. Performance and Workforce expose the same Visits slice and source metadata.
- Compensation exposes every canonical Retail salary row to the allowlisted users through a complete versioned read-model: stable person/agent identity, display name, company, store and organizational dimensions, total and available salary components/provenance. KPI, person detail, filters, inspect and export use the same rows. There is no cohort suppression, minimum-person threshold, identity masking or exclusion merely because a legacy row lacks a newer import-batch approval field. CNP or another source field, when present and required for authorized reconciliation, is available only through authenticated detail/export and is never written to application logs.
- Finance explicitly marks `actual`/`estimated` and source provenance. The read-model follows the same preference as Retail: actual dominates estimated only for the same company/month/site where both exist; otherwise the estimate remains visible and labeled. `__FINANCE_UNALLOCATED__` belongs in company totals and also appears in a dedicated unallocated detail. Shadow data is labeled as shadow/draft and never presented as actual, but canonical `store_pnl_monthly` rows are not hidden solely because a promoted generation head is absent.
- Planning forecast identifies run, horizon, method/model, input cutoff and coverage. `completed` este numai candidat: v2 publică exclusiv head-ul promovat, cu hash/row-count înghețat, approval artifact, revision CAS și ledger append-only. Target scenarios identify scenario, revision, status, rule-set hash and exact registry-backed snapshot; drafts și scenariile legacy nu devin implicit shared truth. Accuracy păstrează KPI-ul server-side și vizualizează perechile Actual × Forecast publicate pe magazin; clientul nu recalculează o formulă alternativă.

`UNAVAILABLE` means no canonical Retail rows exist for the requested period/scope or the source is technically unreachable. `PARTIAL` reports incomplete coverage or provenance without hiding available rows. Missing head/publication metadata alone must not turn salary, P&L, forecast or workforce rows already accepted by Retail into an empty module.

Retail migration 047 is the historical aggregate-only baseline and must be superseded additively by complete Compensation and Finance contracts; applied migration files remain immutable. Migrations 049–050 add Visits v2 and canonical completion without rewriting FieldOps history. Migrations 051–052 add governed Planning v2. Migration 057 adds Campaigns v3, Concurs v1, Grile v1 and snapshot v5; migration 058 adds Grile v2 and snapshot v6 while v5/v1 remain rollout anchors. Legacy raw grants do not authorize arbitrary SQL, but complete versioned read-models must expose all available business data to the allowlisted users.

## Export contract

XLSX/CSV/PNG apply the same full-data allowlist and snapshot as the API. Dashboard ACL controls saved-layout permissions only; no module capability, scope ceiling or cohort suppression may remove business rows from an authorized user's export. Tabular exports are bounded/paged, cancellable and audited, use native numeric cells, neutralize formula injection and carry metadata/warnings. PNG is non-persistent by default and its filename/options are sanitized.

## Metric catalog fields

`id`, `version`, display name, description, unit, aggregation, formula reference, allowed dimensions/grains, compatible analytical shapes/`ChartSpec`, comparison policy, `allowed_comparisons`, missing policy, source authority and effective dates. Catalog compatibility constrains valid analysis, never which business data an allowlisted user may see.
