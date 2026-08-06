import type { GlobalSearch } from '../../lib/search';
import { parseComparisons, rangeBounds } from '../../lib/search';
import type { QueryBatchRequest, WidgetQuery } from '../query/schemas';
import { resolveWidgetSearch } from './filter-resolution';
import { type DashboardDocument, type DashboardWidget, dashboardWidgetDimensions } from './schemas';

export const MAX_DASHBOARD_QUERY_WIDGETS = 12;
const businessFilterKeys = ['firm', 'regional', 'asm', 'stores', 'agent'] as const;

const supportedComparisons = new Set<WidgetQuery['comparisons'][number]>([
  'target',
  'forecast',
  'previous-period',
  'previous-year',
  'recent-average',
]);
const supportedTimeGrains = ['day', 'week', 'month', 'quarter', 'year'] as const;

function widgetComparisons(
  widget: DashboardWidget,
  search: GlobalSearch & { period: string },
): WidgetQuery['comparisons'] {
  const configured = widget.comparisons.filter(
    (value): value is WidgetQuery['comparisons'][number] =>
      supportedComparisons.has(value as WidgetQuery['comparisons'][number]),
  );
  if (configured.length > 0) return configured;
  const selected = parseComparisons(search).filter((value) =>
    supportedComparisons.has(value as WidgetQuery['comparisons'][number]),
  );
  if (selected.length > 0) return selected;
  if (search.comparison === 'previous-month') return ['previous-period'];
  if (search.comparison === 'previous-year') return ['previous-year'];
  return [];
}

function widgetFilters(widget: DashboardWidget, search: GlobalSearch & { period: string }) {
  const resolved = resolveWidgetSearch(search, widget);
  const filters: Record<string, string> = {};
  for (const key of businessFilterKeys) {
    const value = resolved[key];
    if (typeof value === 'string') filters[key] = value;
  }
  return filters;
}

export function toWidgetQuery(
  widget: DashboardWidget,
  search: GlobalSearch & { period: string },
): WidgetQuery {
  const resolved = resolveWidgetSearch(search, widget);
  const bounds = rangeBounds(resolved);
  return {
    widget_id: widget.id,
    module: widget.module,
    metric_id: widget.metric_id,
    metric_version: widget.metric_version,
    query_contract_version: widget.query_contract_version,
    dimensions: dashboardWidgetDimensions(widget),
    time_range: bounds,
    time_grain: supportedTimeGrains.includes(
      widget.time_grain as (typeof supportedTimeGrains)[number],
    )
      ? (widget.time_grain as WidgetQuery['time_grain'])
      : 'month',
    filters: widgetFilters(widget, search),
    comparisons: widgetComparisons(widget, search),
    sort: widget.sort.flatMap((field) => {
      const [name, direction] = field.split(':', 2);
      if (!name) return [];
      return [{ field: name, direction: direction === 'asc' ? 'asc' : 'desc' }];
    }),
    limit: widget.limit,
    visualization: widget.visualization,
  };
}

export function dashboardBatchRequest(
  dashboard: DashboardDocument,
  search: GlobalSearch & { period: string },
): QueryBatchRequest {
  return {
    dashboard_id: dashboard.id,
    widgets: dashboard.widgets
      .slice(0, MAX_DASHBOARD_QUERY_WIDGETS)
      .map((widget) => toWidgetQuery(widget, search)),
  };
}
