import { useQuery } from '@tanstack/react-query';
import { lazy, Suspense, useMemo, useState } from 'react';
import type { ChartUrlRangeEvent, ChartUrlStateEvent } from '../../components/charts/chart-spec';
import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import type {
  DashboardLayoutItem,
  DashboardWidgetDefinition,
} from '../../components/dashboard/types';
import type { GlobalSearch } from '../../lib/search';
import type { ModuleId } from '../modules/schemas';
import { analyticsCatalogQuery, queryBatchOptions } from '../query/api';
import { ConfiguredWidget } from './ConfiguredWidget';
import { dashboardBatchRequest, MAX_DASHBOARD_QUERY_WIDGETS } from './query-mapping';
import type { DashboardDocument } from './schemas';

const QueryInspector = lazy(() =>
  import('../query/QueryInspector').then((module) => ({ default: module.QueryInspector })),
);

export function CustomDashboardPreview({
  dashboard,
  search,
  editMode,
  resetToken,
  onLayoutChange,
  onDuplicateWidget,
  onUrlStateChange,
  onEntityOpen,
  onUrlRangeChange,
  onUrlStateReset,
}: {
  dashboard: DashboardDocument;
  search: GlobalSearch & { period: string };
  editMode: boolean;
  resetToken: number;
  onLayoutChange: (items: DashboardLayoutItem[]) => void;
  onDuplicateWidget?: (widgetId: string) => void;
  onUrlStateChange?: (event: ChartUrlStateEvent) => void;
  onEntityOpen?: (module: ModuleId, event: ChartUrlStateEvent) => void;
  onUrlRangeChange?: (event: ChartUrlRangeEvent) => void;
  onUrlStateReset?: () => void;
}) {
  const catalogQuery = useQuery(analyticsCatalogQuery());
  const batchRequest = useMemo(
    () => dashboardBatchRequest(dashboard, search, catalogQuery.data?.metrics ?? []),
    [catalogQuery.data?.metrics, dashboard, search],
  );
  const hasWidgets = dashboard.widgets.length > 0;
  const batchQuery = useQuery({
    ...queryBatchOptions(batchRequest, search),
    enabled: hasWidgets && catalogQuery.isSuccess,
  });
  const [inspectWidgetId, setInspectWidgetId] = useState<string | null>(null);
  const results = useMemo(
    () => new Map((batchQuery.data?.results ?? []).map((result) => [result.widget_id, result])),
    [batchQuery.data?.results],
  );
  const metrics = useMemo(
    () => new Map((catalogQuery.data?.metrics ?? []).map((metric) => [metric.id, metric])),
    [catalogQuery.data?.metrics],
  );
  const loading = hasWidgets && (catalogQuery.isPending || batchQuery.isPending);
  const requestError = catalogQuery.isError ? catalogQuery.error : batchQuery.error;
  const retry = () => {
    if (catalogQuery.isError) void catalogQuery.refetch();
    if (batchQuery.isError) void batchQuery.refetch();
  };
  const inspectWidget = dashboard.widgets.find((widget) => widget.id === inspectWidgetId);
  const inspectResult = inspectWidget ? results.get(inspectWidget.id) : undefined;
  const inspectMetric = inspectWidget ? metrics.get(inspectWidget.metric_id) : undefined;

  const definitions: DashboardWidgetDefinition[] = dashboard.widgets.map((widget, index) => {
    const result = results.get(widget.id);
    const metric = metrics.get(widget.metric_id);
    const overBatchLimit = index >= MAX_DASHBOARD_QUERY_WIDGETS;
    const Component = () => (
      <ConfiguredWidget
        widget={widget}
        result={overBatchLimit ? undefined : result}
        metric={metric}
        loading={loading}
        requestError={
          overBatchLimit ? new Error('Batch-ul este limitat la 12 widgeturi.') : requestError
        }
        onRetry={retry}
        {...(onUrlStateChange ? { onUrlStateChange } : {})}
        {...(onEntityOpen ? { onEntityOpen: (event) => onEntityOpen(widget.module, event) } : {})}
        {...(onUrlRangeChange ? { onUrlRangeChange } : {})}
        {...(onUrlStateReset ? { onUrlStateReset } : {})}
      />
    );
    return {
      id: widget.id,
      title: widget.title,
      subtitle: `${widget.module} · ${widget.metric_id}`,
      explanation: metric
        ? `${metric.description} Formulă: ${metric.formula_reference}. Missing: ${metric.missing_policy}.`
        : `Metrica ${widget.metric_id} nu mai există în catalogul activ.`,
      component: Component,
      x: widget.layout.x,
      y: widget.layout.y,
      w: widget.layout.w,
      h: widget.layout.h,
      minW: widget.layout.min_w,
      minH: widget.layout.min_h,
    };
  });
  const widgetKey = dashboard.widgets.map((widget) => widget.id).join('|');
  return (
    <>
      <DashboardCanvas
        key={widgetKey}
        widgets={definitions}
        editMode={editMode}
        resetToken={resetToken}
        storageKey={`unihub-insight:custom:${dashboard.id}:v${dashboard.version}`}
        onLayoutChange={onLayoutChange}
        onInspect={setInspectWidgetId}
        onExport={setInspectWidgetId}
        {...(onDuplicateWidget ? { onDuplicate: onDuplicateWidget } : {})}
      />
      {inspectWidget && inspectResult && inspectMetric && batchQuery.data ? (
        <Suspense fallback={null}>
          <QueryInspector
            dashboardId={dashboard.id}
            snapshotId={batchQuery.data.snapshot.id}
            search={search}
            result={inspectResult}
            metric={inspectMetric}
            onClose={() => setInspectWidgetId(null)}
          />
        </Suspense>
      ) : null}
    </>
  );
}
