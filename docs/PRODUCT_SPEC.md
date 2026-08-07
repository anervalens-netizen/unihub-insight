# Product Specification

## Product statement

UniHub Insight is the desktop decision cockpit for the UniHub Retail business. It lets a manager understand what changed, where it changed, why it matters and which entity deserves attention, without mixing analysis with operational data entry.

## Primary users

- Owner — complete network, person, salary, P&L, forecast and operational analysis.
- General director — the same complete analytical visibility as the owner.

No module-specific HR, Finance, management or geographical permission narrows data for either authorized user.

## Core jobs

1. Assess business health in under ten seconds.
2. Compare a selected period with a meaningful benchmark.
3. Drill from network to entity without losing context.
4. Explain a chart through its underlying table and metric definition.
5. Build a reusable dashboard for a recurring managerial workflow.
6. Move to UniHub Retail with the same context when an operational action is needed.
7. Read an automatically generated explanation whose claims link to the exact metric, scope, cutoff and backing rows.

## Information architecture

| Module | Core question | Target surfaces |
| --- | --- | --- |
| Overview | How is the business doing and where should I look? | health, target/forecast, comparisons, profit/cost, risk, data alerts |
| Monthly Review | What happened in the selected month versus history? | YoY, MoM, 3/6/12-month context, hierarchy, products, returns, numeric XLSX |
| Sales | What drives sales, pace, mix and transaction quality? | Pace, Trend, Mix, Drivers, Transactions, Calendar |
| Performance | Which organizational entities are strong, weak or unstable? | hierarchy, Rankings, Distribution, Target matrix, Consistency, Productivity, Visits |
| Campaigns | How are commercial mechanisms adopted and performing? | Overview, Promo, Incentive, Concurs, Focus, Folii |
| Workforce | Do staffing, stability and productivity support performance? | People, Movements, Stability, Coverage, Productivity, Visits, Grile |
| Compensation | How do individual and aggregate remuneration relate to performance? | complete person detail, salary components, structure, distribution, payroll/sales, payroll/profit and person/team comparison |
| Finance | Where is revenue converted into profit or lost to cost? | Overview, Trend, Cost structure, Profitability, Reconciliation, Break-even |
| Planning | What is likely to happen and what changes the outcome? | Current, 12 months, Accuracy, Scenarios, Sensitivity |
| Custom | Which recurring view does this user need? | blank/template/clone, complete widget editor, targeted sharing, inspect/export |

## Current product boundary

Overview and Monthly Review are live differentiated experiences. Sales through Planning are currently partial: routes, data and exports exist, but most reuse one generic four-KPI/trend/distribution/matrix/table layout. Custom Dashboards has persistent CRUD and a partial editor, not yet the final query/ACL/interaction model. A page is not complete merely because it renders live data.

## Global analytical scope

Period/range, comparison, company, RM, ASM, one or more stores and one or more agents where the contract supports it. Local widget overrides are allowed only when displayed visibly.

## Widget behavior

A widget defines metric(s) with versions, dimension, time grain, comparison(s), analytical snapshot, a compatible `ChartSpec`, local filter policy, sort, result limit, display options, size and position. Native modules and Custom use the same bounded batch query, inspect and export contracts. The product does not expose arbitrary SQL or an unrestricted formula editor.

## UX requirements

- Desktop-only analytical surface, minimum 1180 px.
- No centered max-width container.
- View mode prevents accidental movement; Edit mode exposes drag/resize.
- Fullscreen exists on analytical widgets; current generic modules expose inspect, iar targetul este inspect server-side pe același snapshot pentru fiecare widget.
- Cutoff, scope and source remain visible.
- Missing, partial, stale and error states are distinct.
- Charts never rely only on color for meaning.
- Chart selection follows the business-question matrix in the [integrated plan](PLAN_DEZVOLTARE_INTEGRAT.md); users see only semantically compatible choices.
- Click/cross-filter, drill path and time selection are serializable in URL and reproducible after reload.
- Every chart has an accessible description and a complete backing table available to both authorized users; person-level drill, inspect and export preserve the canonical Retail rows.
- Global Chart Studio keeps governed Executive/Ocean/Vibrant/Accessible/Monochrome presets, density, legend, labels and animation controls without changing metric semantics.
- Generated explanations and deviation alerts are evidence-backed and versioned; they never state unsupported causality.

## Non-goals

Replacing Retail imports/writes, generic arbitrary BI, causal attribution without validated methodology, real-time streaming over snapshot sources, and a mobile application.
