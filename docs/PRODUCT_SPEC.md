# Product Specification

## Product statement

UniHub Insight is the desktop decision cockpit for the UniHub Retail business. It lets a manager understand what changed, where it changed, why it matters and which entity deserves attention, without mixing analysis with operational data entry.

## Primary users

- Commercial director / owner — network health, profit, forecast and priorities.
- Regional Manager — comparison and drill-down across ASM/store/agent scope.
- ASM / team leadership — store and people performance where authorized.
- Finance — P&L, cost structure, reconciliation and scenarios.
- HR / management — workforce and compensation under dedicated permissions.

## Core jobs

1. Assess business health in under ten seconds.
2. Compare a selected period with a meaningful benchmark.
3. Drill from network to entity without losing context.
4. Explain a chart through its underlying table and metric definition.
5. Build a reusable dashboard for a recurring managerial workflow.
6. Move to UniHub Retail with the same context when an operational action is needed.

## Information architecture

| Module | Core question |
| --- | --- |
| Overview | How is the business doing and where should I look? |
| Sales | What drives sales, pace, mix and transaction quality? |
| Performance | Which organizational entities are strong, weak or unstable? |
| Campaigns | How are commercial mechanisms adopted and performing? |
| Workforce | Do staffing, stability and productivity support performance? |
| Finance | Where is revenue converted into profit or lost to cost? |
| Planning | What is likely to happen and what changes the outcome? |
| Custom | Which recurring view does this user need? |

## Global analytical scope

Period/range, comparison, company, RM, ASM, one or more stores and one or more agents where the contract supports it. Local widget overrides are allowed only when displayed visibly.

## Widget behavior

A widget defines metric(s), dimension, time grain, comparison, a compatible visualization, local filter policy, sort, result limit, display options, size and position. The product does not expose arbitrary SQL or an unrestricted formula editor.

## UX requirements

- Desktop-only analytical surface, minimum 1180 px.
- No centered max-width container.
- View mode prevents accidental movement; Edit mode exposes drag/resize.
- Fullscreen and eventually Inspect data on every analytical widget.
- Cutoff, scope and source remain visible.
- Missing, partial, stale and error states are distinct.
- Charts never rely only on color for meaning.

## Non-goals for the initial product

Replacing Retail imports/writes, generic arbitrary BI, causal attribution without validated methodology, real-time streaming over snapshot sources, and a mobile application.
