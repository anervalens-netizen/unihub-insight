# Design System

## Character

Dense, calm, professional and evidence-first. The interface resembles a modern analytical workstation rather than a marketing site or enlarged mobile application.

## Layout

- Sidebar: 238 px expanded, 76 px collapsed.
- Compact top bar and permanently visible global filters.
- Full remaining viewport width; no max-width container.
- Dashboard: 24 columns, 28 px base row, 10 px gaps.
- Widget radius 16 px; restrained shadows and borders.

## Semantic tokens

CSS custom properties are the initial source of truth: canvas/surface levels, primary/soft/muted text, indigo/teal/amber/rose semantics, borders, shadows and shared dimensions. Light/dark themes keep the same token names.

## Color semantics

- Indigo: active/navigation/primary analytical series.
- Teal: healthy/positive/target pace.
- Amber: watch/forecast/attention.
- Rose: risk/negative/critical.
- Gray: comparison/neutral context.

Color is always paired with label, icon, line style or shape.

## Widgets

Every widget has title, optional concise subtitle, fullscreen action, bounded body, consistent loading/empty/error states and a drag handle only in Edit mode. Content must survive its documented minimum size; incompatible dimensions are prevented by catalog constraints.

## Charts

Apache ECharts 6.1 uses modular registration. The canonical research and complete matrix are in the [integrated plan](PLAN_DEZVOLTARE_INTEGRAT.md); an ADR freezes accepted chart types and thresholds before the selector expands.

| Analytical shape | Default | Limit / fallback |
| --- | --- | --- |
| Trend | line; column for discrete periods | `dataZoom` at long ranges; no misleading smoothing |
| Target/status | KPI + progress/bullet bar | no decorative gauge |
| Ranking | horizontal bar + table | 30 visible categories, then Top N/table |
| Part-to-whole | stacked/100% stacked bar | donut only for 5–6 meaningful categories |
| Change bridge | waterfall | signed components must reconcile start/end |
| Relationship | scatter | bubble only for one meaningful third metric; no causal claim |
| Distribution | histogram + boxplot | sample size visible; full person-level backing table available to authorized users |
| Entity × time | Canvas heatmap | initial 100×36, then aggregation/paging |
| Forecast uncertainty | range/fan band + scenario lines | actual, estimate and scenario remain visually distinct |

`ChartSpec` maps question and data shape to allowed charts, cardinality, renderer, interaction, formatter, accessible table and export. Shared `dataset`/`dimensions`/`encode` is the chart data boundary; client transforms are presentation-safe only. Realized, target, forecast and comparison keep stable identities. Future actual values are gaps.

Chart Studio exposes governed Executive, Ocean, Vibrant, Accessible and Monochrome presets plus density, legend, labels and motion controls. User preferences may change presentation, never formulas, missing-data behavior, source provenance or required non-color encoding.

Canvas is the default for dense/large charts. SVG is allowed only after measured POC for many small charts or vector/zoom needs. Acceptance profiles bundle/chunk size, first render, resize, frame time and memory for 8–12 widgets; interaction p95 remains under 200 ms. Cross-filter uses ECharts events/actions through URL state. ARIA, decals/non-color encoding, backing table and sanitized non-persistent PNG export are mandatory.

## Tables

Sticky headers, finite sortable columns, numeric alignment, tabular figures and contextual entity cells. Virtualization enters when row count or profiling justifies it.

## Accessibility

Keyboard-visible focus, reduced-motion support, dialog semantics/Escape, accessible chart descriptions and no meaning by color alone. The desktop minimum is communicated explicitly.
