# Live Reconciliation

## Objective

Prove that UniHub Insight presents the same business truth as UniHub Retail for identical period and scope. Visual similarity is not acceptance; control totals must match.

## Latest production evidence — 2026-08-06

The bounded representative matrix passes 30/30 scopes: 15 for the closed
month 2026-07 and 15 for the current month 2026-08. Every Sales, Target,
Campaigns, Workforce and eligible Visits control difference is zero, including
the official weighted Visits completion/checklist grain. Compensation, Finance
and Planning remain explicitly unavailable where Retail has no eligible
approved generation or head; reconciliation does not convert that absence to
zero. The exact deployed SHA remains independently bound by public
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

### Targets

- Network/store scope: sum canonical `store_targets` for represented stores.
- Agent scope: use `agent_targets`; never assign the entire store target to one agent.
- Missing target remains distinguishable from zero.

### Campaigns

Compare Focus sales/quantity and the count of active products/stores. Promo, Incentive and Concurs remain separate metrics and are not merged into Focus.

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

Deployment remains blocked by any write privilege on the analytics role, an unexplained total difference, an agent receiving a store target, sensitive values visible below the suppression threshold, P&L actual/estimate overlap, stale migration checksum or non-finite query scope.
