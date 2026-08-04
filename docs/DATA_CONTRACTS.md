# Data Contracts

## Response metadata

Every analytical response includes period, comparison, `as_of` cutoff, final/open state, data mode, currency, scope label, generation time and source. `as_of` is the last covered business date, not response time.

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

The linear forecast is explicitly labeled run-rate; it is not the persisted AI forecast used elsewhere in UniHub.

## Comparison semantics

- `previous-month`: same scope against the immediately preceding calendar month.
- `previous-year`: same calendar month one year earlier.
- `none`: comparison fields are null.

For an open current period, future actual points are null, never repeated last values.

## Scope rules

- Hierarchy: company → RM → ASM → store → agent.
- Store selection is ordered, deduplicated and supports multiple `site_code` values.
- `site_code` is the stable operational store key.
- Agent identity in the first slice uses reporting label plus site scope; stable person identity is required before cross-store longitudinal analysis.
- Selected store can dominate historical parent filters where the Retail contract requires it.

## Retail invariants inherited

- `Cartele` are excluded from normal accessory KPIs.
- Distribution / `TR %` locations are excluded from ordinary Retail KPI scope.
- Quantities are net.
- Identical source rows are not deduplicated as transactions.
- Snapshot and historical fallback coverage are explicit.
- Salary totals follow the Retail salary contract.

## Risk and alerts

Initial alerts are deterministic rules, not machine-learning scores. They expose the rule outcome and entity label. Thresholds move into the versioned metric/rule catalog before production expansion.

## Future metric catalog fields

`id`, `version`, display name, description, unit, aggregation, formula reference, allowed dimensions/grains, comparison policy, missing policy, capability and effective dates.
