# UniHub Insight User Guide

## Global scope

The filter bar controls period, comparison, company, RM, ASM, stores and agent. Scope is stored in the URL, so a copied link reproduces the same analysis. Selected stores dominate historical parent-company filters where the Retail identity contract requires it.

Finance and Planning do not accept agent scope. Compensation is visible only with the HR capability; Finance only with the P&L capability.

## Modules

- **Overview** — business health, target pace, forecast, contribution and priority alerts.
- **Sales** — pace, history, receipts, product/category mix and temporal patterns.
- **Performance** — rankings, consistency, volatility and entity heatmaps.
- **Campaigns** — Focus and commercial mechanism adoption/contribution.
- **Workforce** — headcount, staffing coverage, lifecycle and Grile status.
- **Compensation** — payroll, average/median, distribution and sales ratio.
- **Finance** — revenue, cost structure, EBIT, margin and monthly profitability.
- **Planning** — actual, forecast, target gap and forecast accuracy.
- **Custom** — personal and shared dashboards assembled from governed metrics.

Current reality: Overview and Monthly Review are the differentiated mature views. Sales through Planning currently render mostly the same generic KPI/trend/distribution/matrix/table canvas; the specialized sub-tabs and deeper drill/cross-filter behavior above are target behavior from the [integrated plan](PLAN_DEZVOLTARE_INTEGRAT.md), not completed functionality.

## Dashboard interaction

- Use **Edit layout** to drag a card by its header and resize it from its edges.
- Use **Layout implicit** to restore the versioned default.
- Expand any card to fullscreen.
- In current generic modules, use the table icon to inspect the response rows and export CSV. The target inspector will rerun the exact widget query server-side in the same snapshot.
- Chart toggles offer only visualizations compatible with the analytical contract.

## Custom dashboards

Start blank or clone Director, Regional Manager, Finance or Risk templates. A card selects a module, registered metric, visualization and filter policy:

- **Inherit** — uses all global filters.
- **Augment** — starts from global filters and adds/replaces specified local values.
- **Override** — ignores global business filters and uses only specified local values; period/comparison remain global.
- **Ignore** — analyzes network scope for the selected period/comparison.

Every non-inherited state is shown on the card. Current `shared` visibility is global inside the authorized Insight audience; targeted per-user ACL, revocation and scope ceilings are planned and must replace it before sharing is considered complete.

## Data-state interpretation

- `Demo` means deterministic development data, never production evidence.
- `PostgreSQL live` means the read-only Retail adapter supplied the result.
- Cutoff is the last covered business date, not page-load time.
- Forecast run-rate is labeled separately from persisted AI forecast.
- Missing data is not silently converted to zero.
- Salary views with fewer than three people are suppressed. The current direct salary/person read path is transitional; the target contract removes it and permits only an aggregate Retail read-model protected against identification and filter differencing.

## Operational actions

Insight is analytical and read-only. Use **Open Retail** for imports, configurations, month-closing operations or any business mutation. Authorization is evaluated independently by Retail.
