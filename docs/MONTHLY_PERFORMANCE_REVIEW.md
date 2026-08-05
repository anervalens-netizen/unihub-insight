# Monthly Performance Review

## Purpose

The **Raport lunar** module converts the recurring month-close analysis into a reusable UniHub Insight product surface. It is designed for management distribution and for identifying where performance is improving, slowing or diverging from the network.

## Comparisons

Every selected period is evaluated against three independent references:

1. the same month of the previous year;
2. the immediately previous month;
3. the average of the previous 3, 6 or 12 months.

The report also compares the month-over-month seasonal lift with the same transition in the two previous years. This prevents a normal seasonal increase or decline from being interpreted as exceptional performance.

## Sections

- executive KPIs and exact sales-driver bridge;
- multi-month trend and target;
- seasonality on a current organizational cohort;
- company, RM, store and agent performance;
- product/category impact and distribution;
- returns by store, product and agent;
- explicit alerts and methodology.

## Performance score

The score is a prioritization aid, not a compensation formula:

- target attainment: 40%;
- year-over-year development: 25%;
- development versus recent average: 25%;
- recent consistency: 10%.

Statuses are deterministic: outperforming, healthy, watch, risk, recovering, slowing, volatile, new or exited. The current status always remains explainable through the displayed components.

## Driver decomposition

The sales difference is reconciled exactly into:

- receipt-count effect;
- units-per-receipt effect;
- value-per-unit and mix effect.

A rounding correction is assigned to the last component so the three drivers always equal the exact sales difference.

## Cohort and identity

The live adapter uses the currently eligible stores in the selected scope and reads historical transactions for that cohort. Explicit store selection dominates parent organizational filters. Agent targets come from `agent_targets`; an agent never inherits the full store target.

## Exports

The complete report and every material section can be exported to `.xlsx`. Values are written as native numeric cells with Excel number formats. Text-formatted numbers are forbidden. The complete workbook separates metadata, summary, drivers, trend, seasonality, companies, managers, stores, categories, products, returns, agents, methodology and alerts.
