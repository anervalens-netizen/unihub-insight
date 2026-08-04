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

ECharts uses modular registration and canvas rendering. Realized, target, forecast and comparison have stable visual identities. Future actual values are gaps. Donut is limited to a small number of meaningful shares; ranking uses bars/tables. Every chart later exposes Inspect data.

## Tables

Sticky headers, finite sortable columns, numeric alignment, tabular figures and contextual entity cells. Virtualization enters when row count or profiling justifies it.

## Accessibility

Keyboard-visible focus, reduced-motion support, dialog semantics/Escape, accessible chart descriptions and no meaning by color alone. The desktop minimum is communicated explicitly.
