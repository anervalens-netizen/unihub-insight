# Live Reconciliation

## Objective

Prove that UniHub Insight presents the same business truth as UniHub Retail for identical period and scope. Visual similarity is not acceptance; control totals must match.

## Latest production evidence — 2026-08-06

The bounded matrix has zero numeric differences for every available case:
19/19 in the closed month 2026-07 and 18/18 in the current month 2026-08.
This is **not** authoritative acceptance: 0/19 and 0/18 cases pass the source
authority gate. July is missing the historically transferred-store sample;
August is missing that sample and a partial-month target agent. Campaigns,
Workforce and Planning are `partial`, Finance and Compensation are
`unavailable`, and July Sales is also `partial`. Visits v2 differences are zero
where eligible. Missing/partial sources and missing samples are never converted
to success.

The next integrated candidate is `1.0.0-rc.2`; it carries the Sales Portfolio
contract below and is not a relabeling of `1.0.0-rc.1`.

### Sales Portfolio control — entire network, 2026-06

All four Portfolio API roll-ups have exact zero difference from their approved
Retail reporting controls: **3,223,513.13 RON** and **33,279 net units**. The
checks include both aggregate conservation and the displayed entity count.

| Dimension | Accounting control | Entity control | Exact result |
| --- | --- | ---: | --- |
| Category | `reporting_category_month` | 6 categories | 3,223,513.13 RON; 33,279 net units |
| Subcategory | `reporting_category_month` | 20 category/subcategory pairs | 3,223,513.13 RON; 33,279 net units |
| Brand | `reporting_item_month`, with real-brand attributes from `insight.monthly_review_item_month` | 19 actual brands | 3,223,513.13 RON; 33,279 net units |
| Product | `reporting_item_month` | 1,099 SKU (`item_code`) | 3,223,513.13 RON; 33,279 net units |

Brand enrichment does not change the item accounting authority. Returns remain
signed in the brand/product controls. Product receipt incidence is reconciled
only as SKU–receipt incidence; it is deliberately not compared with, or named
as, a distinct-receipt total.

Campaign publication v2 also reconciles June 2026 exactly. The source remains
`partial`, rather than `unavailable`, because the legacy completed-sales head
does not prove final sales authority. That status does not alter the canonical
mechanism totals.

| Mechanism / scope | Sales RON | Net quantity | Products | Stores | Canonical value |
| --- | ---: | ---: | ---: | ---: | ---: |
| Promo `promotie-actuala-mihai` / network | 190,544.58 | 1,090 | 42 | 76 | discount 21,991.08 |
| Promo / Mobiup | 98,880.60 | 526 | 40 | 36 | discount 11,664.26 |
| Promo / MobiCell | 91,663.98 | 564 | 37 | 40 | discount 10,326.82 |
| Incentive campaign `5` / network | 2,803,358.98 | 29,107 | 877 | 40 | reward 76,367.50 |
| Incentive / Mobiup | 1,371,590.36 | 14,006 | 838 | 18 | reward 33,105.00 |
| Incentive / MobiCell | 1,431,768.62 | 15,101 | 809 | 22 | reward 43,262.50 |

Promo discounted units are 646 network / 302 Mobiup / 344 MobiCell.
Incentive eligible quantity is 27,549 and qualified quantity is 17,792;
qualified-store count is 40 and potential reward is 161,025. Negative return
rows remain signed in the publication. Every control total above has difference
`0.00` or `0`, including the two company slices; active product counts are the
distinct union of published product codes, never a sum of slice counts.

`ops/scripts/reconcile.py --matrix` is fail-closed by default. `--numeric-only`
still fails when a required sample is absent. The combination
`--numeric-only --allow-missing-cases` is diagnostic evidence only and cannot
approve `1.0`. The exact deployed SHA remains independently bound by public
`build-info.json`, release evidence, preflight and the SLI evaluator.

## Required samples

Use one finalized month and the current open month. For each, test:

- entire network;
- each company;
- at least two Regional Managers;
- at least two ASMs;
- at least five stores, including a historically transferred store;
- at least five agents, including an agent with partial-month target allocation;
- one store with returns;
- one month containing estimated P&L;
- one HR scope with fewer than three people.

## Control totals

### Sales

Compare net sales, net quantity, receipts, 2+ accessory receipts, cutoff date and distinct stores/agents. `Cartele` and `TR %` locations must remain outside normal KPIs.

For Sales Portfolio, compare category, subcategory, brand and product
independently. All four must conserve net sales and net quantity; brand/product
must also conserve signed returns, and product alone conserves SKU–receipt
incidence. Reconcile entity cardinality at the same time. Product is keyed only
by `item_code`; a label or Monthly Review attribute conflict is evidence, not a
new SKU. Never use the SKU incidence as a distinct receipt control.

### Targets

- Network/store scope: sum canonical `store_targets` for represented stores.
- Agent scope: use `agent_targets`; never assign the entire store target to one agent.
- Missing target remains distinguishable from zero.

### Campaigns

Compare Focus sales/quantity and the count of active products/stores. Promo and
Incentive additionally compare mechanism existence, sales, signed net quantity,
distinct published product codes, participating stores and canonical
discount/reward from `reporting_campaign_month_v2`. Promo, Incentive and Concurs
remain separate metrics and are not merged into Focus.

Concurs has two Retail mechanisms in 2026-06 but no eligible official
head/read-model for Insight, so it is unavailable rather than zero or partial
reconciliation evidence. The current Retail `promo_bonuri` aggregate sums
excluded units and is not a distinct-receipt control.

### Workforce

Compare active headcount, days worked, entries/exits and eligible-store coverage. Coverage denominator includes eligible stores with no staffed sales row.

### Compensation

- Compare only approved aggregate cohorts from `reporting_compensation_month_v1`; Insight never reads salary/person rows.
- Total payroll includes all canonical salary rows in the Retail-owned aggregation.
- Average includes only salaries of at least 2,000 RON; median does not apply pragul.
- Any cohort with one or two people exposes no values, rows, charts or exports.
- Public contracts contain no `person_id`, name, CNP or filter that can differentiate a person.

### Finance

Compare revenue, COGS, operating costs, depreciation, EBIT and margin to the cent. Actual rows dominate estimates for the same company/month. Store breakdown represents only the selected month; temporal matrix may represent several months and must be labeled accordingly.

### Planning

Compare completed forecast run IDs, actuals, forecast values, target gap and accuracy. Missing forecast coverage is an explicit warning, not zero.

## Procedure

1. Freeze the Retail snapshot/cutoff used for the comparison.
2. Save the exact URL scope and Insight response metadata.
3. Export the backing table from each Insight widget.
4. Export or query the corresponding Retail source.
5. Compare totals before reviewing entity rows.
6. Record source SHA, period, cutoff, filters and difference.
7. Classify every difference as contract mismatch, stale source, scope identity issue or expected rounding.
8. Fix and rerun; never approve unexplained differences.

## Tolerances

- Currency: exact to 0.01 RON after canonical rounding.
- Integer counts/quantities: exact.
- Percentages: derived from exact control totals; display tolerance 0.01 percentage points.
- Dates, entity counts, capability decisions and suppression: exact.

## No-go conditions

Promotion remains blocked by any missing required sample, non-official required source, write privilege on the analytics role, unexplained total difference, a Portfolio dimension that does not conserve its required values/cardinality, an SKU incidence presented as distinct receipts, an agent receiving a store target, sensitive values visible below the suppression threshold, P&L actual/estimate overlap, stale migration checksum or non-finite query scope.
