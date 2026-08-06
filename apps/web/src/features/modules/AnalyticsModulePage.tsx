import { useQuery } from '@tanstack/react-query';
import { ExternalLink, Lock, RefreshCw, RotateCcw, Unlock } from 'lucide-react';
import { lazy, Suspense, useEffect, useMemo, useState } from 'react';

import { useGlobalSearch, useUpdateGlobalSearch } from '../../app/search-hooks';
import { DashboardCanvas } from '../../components/dashboard/DashboardCanvas';
import { ErrorState } from '../../components/ui/ErrorState';
import { ExcelExportButton } from '../../components/ui/ExcelExportButton';
import { LoadingState } from '../../components/ui/LoadingState';
import {
  crossFilterMultiPatch,
  crossFilterPatch,
  crossFilterRangePatch,
  resetCrossFilterPatch,
} from '../../lib/cross-filter';
import { analyticsSearchParams } from '../../lib/download';
import { environment } from '../../lib/environment';
import { formatDate, formatMonth } from '../../lib/format';
import { currentBusinessMonth, parseComparisons, rangeBounds } from '../../lib/search';
import { useIdentity } from '../identity/context';
import { analyticsCatalogQuery, queryBatchOptions } from '../query/api';
import type {
  MetricDefinition,
  QueryBatchRequest,
  WidgetQuery,
  WidgetQueryResult,
} from '../query/schemas';
import { moduleAnalyticsQuery } from './api';
import { ModuleProvider } from './context';
import { moduleDistributionDimension, moduleEntityDimension } from './interactions';
import { openRetailContext, retailContextUrl, retailEntityContextUrl } from './retail-link';
import type { ModuleAnalytics, ModuleId } from './schemas';
import {
  type ModuleSubview,
  moduleSubviewConfig,
  portfolioDimensionForSubview,
  specializedSubviewActions,
  subviewForId,
  subviewStatus,
  unavailableSubviewCopy,
} from './subviews';
import { moduleWidgetQuerySpec, moduleWidgets } from './widget-catalog';

const QueryInspector = lazy(() =>
  import('../query/QueryInspector').then((module) => ({ default: module.QueryInspector })),
);
const SourceMetadataStrip = lazy(() =>
  import('./SourceMetadataStrip').then((module) => ({ default: module.SourceMetadataStrip })),
);

const businessFilterKeys = ['firm', 'regional', 'asm', 'stores', 'agent'] as const;
type NativeBatchProjector = (
  data: ModuleAnalytics,
  results: readonly WidgetQueryResult[],
) => ModuleAnalytics;

export function nativeWidgetQuery(
  module: ModuleId,
  widgetId: string,
  search: ReturnType<typeof useGlobalSearch> & { period: string },
  metric: MetricDefinition | undefined,
  selectedSubviewId?: ModuleSubview['id'],
): WidgetQuery | null {
  const spec = moduleWidgetQuerySpec(module, widgetId);
  if (!spec || !metric || metric.id !== spec.metricId) return null;
  const portfolioDimension = selectedSubviewId
    ? portfolioDimensionForSubview(selectedSubviewId)
    : undefined;
  const isPortfolioMetric = metric.id.startsWith('sales.portfolio_');
  if (isPortfolioMetric && !portfolioDimension) return null;
  const entityDimension = spec.metricId.startsWith('visits.')
    ? 'team_leader'
    : (portfolioDimension ?? moduleEntityDimension[module]);
  let visualization: WidgetQuery['visualization'];
  let dimensions: string[];
  if (spec.kind === 'kpi') {
    visualization = 'kpi';
    dimensions = portfolioDimension ? [portfolioDimension] : [];
  } else if (spec.kind === 'trend') {
    visualization = 'line';
    dimensions = ['time'];
  } else if (spec.kind === 'distribution') {
    visualization = 'donut';
    const dimension = portfolioDimension ?? moduleDistributionDimension[module];
    if (!dimension) return null;
    dimensions = [dimension];
  } else if (spec.kind === 'matrix') {
    visualization = 'heatmap';
    dimensions = [entityDimension, 'time'];
  } else if (spec.kind === 'scatter') {
    visualization = 'scatter';
    dimensions = [entityDimension];
  } else if (spec.kind === 'histogram') {
    visualization = 'histogram';
    dimensions = [entityDimension];
  } else if (spec.kind === 'waterfall') {
    visualization = 'waterfall';
    dimensions = ['category'];
  } else if (spec.kind === 'calendar') {
    visualization = 'calendar';
    dimensions = ['time'];
  } else {
    visualization = 'table';
    dimensions = [entityDimension];
  }
  if (
    !metric.allowed_shapes.includes(visualization) ||
    dimensions.some((dimension) => !metric.allowed_dimensions.includes(dimension))
  ) {
    return null;
  }
  const filters: WidgetQuery['filters'] = {};
  for (const key of businessFilterKeys) {
    const value = search[key];
    if (value) filters[key] = value;
  }
  return {
    widget_id: widgetId,
    module,
    metric_id: metric.id,
    metric_version: metric.version,
    query_contract_version: metric.query_contract_version,
    dimensions,
    time_range: rangeBounds(search),
    time_grain: spec.kind === 'calendar' ? 'day' : 'month',
    filters,
    comparisons:
      widgetId === 'forecast'
        ? [...new Set<WidgetQuery['comparisons'][number]>(['target', ...parseComparisons(search)])]
        : spec.kind === 'trend'
          ? parseComparisons(search)
          : [],
    sort: [],
    limit:
      spec.kind === 'matrix' || spec.kind === 'table' || isPortfolioMetric
        ? 5000
        : spec.kind === 'breakdown'
          ? 500
          : 100,
    visualization,
  };
}

function moduleExportParams(
  input: Parameters<typeof analyticsSearchParams>[0],
  snapshotId: string | null | undefined,
): URLSearchParams {
  const params = analyticsSearchParams(input);
  if (snapshotId) params.set('snapshot_id', snapshotId);
  return params;
}

export function moduleSubviewData(data: ModuleAnalytics, subview: ModuleSubview): ModuleAnalytics {
  if (subview.id === 'visits' && data.visits) return { ...data, ...data.visits };
  const campaignSlice = data.campaigns?.[subview.id];
  if (campaignSlice) return { ...data, ...campaignSlice };
  const portfolioDimension = portfolioDimensionForSubview(subview.id);
  const portfolioSlice = portfolioDimension ? data.portfolio?.[portfolioDimension] : undefined;
  return portfolioSlice ? { ...data, ...portfolioSlice } : data;
}

function SubviewNavigation({
  views,
  selected,
  statuses,
  onSelect,
}: {
  views: readonly ModuleSubview[];
  selected: ModuleSubview;
  statuses: ReadonlyMap<string, ReturnType<typeof subviewStatus>>;
  onSelect: (id: ModuleSubview['id']) => void;
}) {
  return (
    <nav className="module-subview-nav" aria-label="Sub-view analiză">
      {views.map((view) => {
        const status = statuses.get(view.id);
        return (
          <button
            type="button"
            key={view.id}
            className={view.id === selected.id ? 'module-subview is-active' : 'module-subview'}
            onClick={() => onSelect(view.id)}
          >
            <span>{view.label}</span>
            <small
              className={`availability-dot availability-dot--${status?.availability ?? 'unavailable'}`}
            >
              {status?.availability === 'available'
                ? 'LIVE'
                : status?.availability === 'partial'
                  ? 'PARTIAL'
                  : 'UNAVAILABLE'}
            </small>
          </button>
        );
      })}
    </nav>
  );
}

export function AnalyticsModulePage({ module }: { module: ModuleId }) {
  const search = useGlobalSearch();
  const updateSearch = useUpdateGlobalSearch();
  const identity = useIdentity();
  const period = search.period ?? currentBusinessMonth();
  const input = useMemo(() => ({ ...search, period }), [period, search]);
  const views = moduleSubviewConfig[module];
  const selectedSubview = subviewForId(module, search.subview);
  useEffect(() => {
    if (search.subview !== selectedSubview.id) updateSearch({ subview: selectedSubview.id }, true);
  }, [search.subview, selectedSubview.id, updateSearch]);
  const incompatibleAgent = Boolean(
    search.agent &&
      (module === 'finance' || module === 'planning' || selectedSubview.id === 'visits'),
  );
  const moduleQuery = useQuery({
    ...moduleAnalyticsQuery(module, input),
    enabled: !incompatibleAgent,
  });
  const catalogQuery = useQuery(analyticsCatalogQuery());
  const [editMode, setEditMode] = useState(false);
  const [resetToken, setResetToken] = useState(0);
  const [inspectWidget, setInspectWidget] = useState<string | null>(null);
  const rawData = moduleQuery.data;
  const rawStatuses = rawData
    ? new Map(views.map((view) => [view.id, subviewStatus(rawData, view)]))
    : new Map<string, ReturnType<typeof subviewStatus>>();
  const rawStatus = rawStatuses.get(selectedSubview.id);
  const rawDisplayData = rawData ? moduleSubviewData(rawData, selectedSubview) : undefined;
  const catalogMetrics = useMemo(
    () => new Map((catalogQuery.data?.metrics ?? []).map((metric) => [metric.id, metric])),
    [catalogQuery.data?.metrics],
  );
  const candidateWidgets = useMemo(
    () =>
      rawDisplayData && rawStatus?.availability !== 'unavailable'
        ? moduleWidgets(rawDisplayData, selectedSubview.id)
        : [],
    [rawDisplayData, rawStatus?.availability, selectedSubview.id],
  );
  const widgetQueryList = useMemo(
    () =>
      candidateWidgets.flatMap((widget) => {
        const spec = moduleWidgetQuerySpec(module, widget.id);
        const widgetQuery = nativeWidgetQuery(
          module,
          widget.id,
          input,
          spec ? catalogMetrics.get(spec.metricId) : undefined,
          selectedSubview.id,
        );
        return widgetQuery ? [widgetQuery] : [];
      }),
    [candidateWidgets, catalogMetrics, input, module, selectedSubview.id],
  );
  const batchRequest = useMemo<QueryBatchRequest>(
    () => ({
      ...(rawData?.meta.analytical_snapshot_id
        ? { snapshot_id: rawData.meta.analytical_snapshot_id }
        : {}),
      dashboard_id: null,
      widgets: widgetQueryList,
    }),
    [rawData?.meta.analytical_snapshot_id, widgetQueryList],
  );
  const batchRequired = widgetQueryList.length > 0;
  const batchQuery = useQuery({
    ...queryBatchOptions(batchRequest, input),
    enabled: !incompatibleAgent && batchRequired && moduleQuery.isSuccess && catalogQuery.isSuccess,
  });
  const [nativeBatchProjector, setNativeBatchProjector] = useState<NativeBatchProjector | null>(
    null,
  );
  useEffect(() => {
    let active = true;
    void import('./native-batch').then(({ applyNativeBatchResults }) => {
      if (active) setNativeBatchProjector(() => applyNativeBatchResults);
    });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (rawStatus?.availability === 'unavailable') setEditMode(false);
  }, [rawStatus?.availability]);

  if (incompatibleAgent) {
    return (
      <ErrorState
        title="Filtru incompatibil"
        message={
          selectedSubview.id === 'visits'
            ? 'Visits păstrează autorul Team Leader și scope-ul magazinului; filtrul agent nu este compatibil.'
            : 'Finance și Planning funcționează la nivel de rețea, structură și magazin, nu la nivel de agent.'
        }
        onRetry={() => updateSearch({ agent: undefined }, true)}
      />
    );
  }
  if (
    moduleQuery.isPending ||
    catalogQuery.isPending ||
    (batchRequired && (batchQuery.isPending || !nativeBatchProjector))
  ) {
    return <LoadingState label="Se construiește analiza din catalog…" />;
  }
  if (moduleQuery.isError || catalogQuery.isError || (batchRequired && batchQuery.isError)) {
    const error = moduleQuery.error ?? catalogQuery.error ?? batchQuery.error;
    return (
      <ErrorState
        message={error instanceof Error ? error.message : 'Eroare necunoscută.'}
        onRetry={() => {
          void moduleQuery.refetch();
          void catalogQuery.refetch();
          if (batchRequired) void batchQuery.refetch();
        }}
      />
    );
  }

  const data = moduleQuery.data;
  if (!identity.capabilities.includes(data.required_capability)) {
    return (
      <ErrorState
        title="Acces indisponibil"
        message={`Modulul necesită capabilitatea ${data.required_capability}.`}
      />
    );
  }
  const statuses = new Map(views.map((view) => [view.id, subviewStatus(data, view)]));
  const status = statuses.get(selectedSubview.id);
  const batchResults = batchQuery.data?.results ?? [];
  const batchResultByWidget = new Map(batchResults.map((result) => [result.widget_id, result]));
  const displayData = nativeBatchProjector
    ? nativeBatchProjector(moduleSubviewData(data, selectedSubview), batchResults)
    : moduleSubviewData(data, selectedSubview);
  const widgetQueries = new Map(widgetQueryList.map((item) => [item.widget_id, item]));
  const snapshotId = batchQuery.data?.snapshot.id ?? data.meta.analytical_snapshot_id;
  const widgets = (
    status?.availability === 'unavailable' ? [] : moduleWidgets(displayData, selectedSubview.id)
  ).map((widget) => {
    const widgetQuery = widgetQueries.get(widget.id);
    const batchResult = batchResultByWidget.get(widget.id);
    const metric = widgetQuery ? catalogMetrics.get(widgetQuery.metric_id) : undefined;
    const explanation = metric
      ? `${metric.description} Formulă: ${metric.formula_reference}. Missing: ${metric.missing_policy}.`
      : widget.subtitle;
    if (widgetQuery && batchResult?.error) {
      const message = batchResult.error.message;
      return {
        ...widget,
        ...(explanation ? { explanation } : {}),
        inspectable: false,
        component: () => <ErrorState message={message} onRetry={() => void batchQuery.refetch()} />,
      };
    }
    return {
      ...widget,
      ...(explanation ? { explanation } : {}),
      inspectable: Boolean(snapshotId && widgetQuery && batchResult?.dataset),
    };
  });
  const inspectedQuery = inspectWidget ? widgetQueries.get(inspectWidget) : undefined;
  const inspectedMetric = inspectedQuery ? catalogMetrics.get(inspectedQuery.metric_id) : undefined;
  const inspectedResult = inspectWidget ? batchResultByWidget.get(inspectWidget) : undefined;
  const retailUrl = retailContextUrl(environment.retailBaseUrl, module, selectedSubview.id, input);
  const actions = specializedSubviewActions(status?.availability ?? 'unavailable');
  const handleUrlState = (event: { dimensionId: string; value: string; label: string | null }) => {
    updateSearch(crossFilterPatch(search.drill, event));
  };
  const handleEntityOpen = (event: {
    dimensionId: string;
    value: string;
    label: string | null;
  }) => {
    openRetailContext(
      retailEntityContextUrl(environment.retailBaseUrl, module, selectedSubview.id, input, event),
    );
  };
  return (
    <ModuleProvider
      data={displayData}
      onUrlStateChange={handleUrlState}
      onEntityOpen={handleEntityOpen}
      onUrlStateChanges={(events) => updateSearch(crossFilterMultiPatch(search.drill, events))}
      onUrlRangeChange={(event) => updateSearch(crossFilterRangePatch(search.drill, event))}
      onUrlStateReset={() => updateSearch(resetCrossFilterPatch(search.drill))}
    >
      <SubviewNavigation
        views={views}
        selected={selectedSubview}
        statuses={statuses}
        onSelect={(id) => updateSearch({ subview: id })}
      />
      <section className="module-view-heading">
        <div>
          <span>
            {portfolioDimensionForSubview(selectedSubview.id)
              ? 'Sales Portfolio'
              : 'Sub-view specializat'}
          </span>
          <h2>{selectedSubview.label}</h2>
          <p>{selectedSubview.description}</p>
        </div>
        {status ? (
          <div className={`module-contract-state module-contract-state--${status.availability}`}>
            <strong>
              {status.availability === 'available'
                ? 'Contract disponibil'
                : status.availability === 'partial'
                  ? 'Contract parțial'
                  : 'Contract lipsă'}
            </strong>
            <span>{status.reason}</span>
          </div>
        ) : null}
      </section>
      <section className="overview-toolbar" aria-label="Starea analizei">
        <div className="overview-meta">
          <span className="meta-chip meta-chip--strong">{formatMonth(data.meta.period)}</span>
          <span className="meta-chip">Scope: {data.meta.scope_label}</span>
          <span className="meta-chip">Cutoff: {formatDate(data.meta.as_of)}</span>
          <span className={`meta-chip data-mode data-mode--${data.meta.data_mode}`}>
            {data.meta.data_mode === 'demo' ? 'Date demo deterministe' : 'PostgreSQL live'}
          </span>
          <span className="meta-chip">Sursă: {data.meta.source}</span>
        </div>
        <div className="overview-actions">
          <a
            className="button button--secondary"
            href={retailUrl}
            target="_blank"
            rel="noreferrer"
            aria-label={`Deschide ${selectedSubview.label} în UniHub Retail cu contextul curent`}
          >
            <ExternalLink size={15} />
            Deschide în Retail
          </a>
          {actions.showExport ? (
            <ExcelExportButton
              path={`/exports/modules/${module}.xlsx`}
              params={moduleExportParams(input, data.meta.analytical_snapshot_id)}
              filename={`${module}-${period}.xlsx`}
              label="Raport complet XLSX"
            />
          ) : null}
          <button
            type="button"
            className="button button--secondary"
            onClick={() => {
              void moduleQuery.refetch();
              if (batchRequired) void batchQuery.refetch();
            }}
          >
            <RefreshCw size={15} />
            Actualizează
          </button>
          {actions.showLayout && editMode ? (
            <button
              type="button"
              className="button button--ghost"
              onClick={() => setResetToken((value) => value + 1)}
            >
              <RotateCcw size={15} />
              Layout implicit
            </button>
          ) : null}
          {actions.showLayout ? (
            <button
              type="button"
              className={`button ${editMode ? 'button--primary' : 'button--secondary'}`}
              onClick={() => setEditMode((value) => !value)}
            >
              {editMode ? <Lock size={15} /> : <Unlock size={15} />}
              {editMode ? 'Salvează layout' : 'Editează layout'}
            </button>
          ) : null}
        </div>
      </section>
      <Suspense fallback={null}>
        <SourceMetadataStrip data={data} />
      </Suspense>
      {actions.showLayout && editMode ? (
        <div className="edit-notice">
          Trage cardurile din antet și redimensionează-le. Layoutul local este versionat separat
          pentru fiecare modul.
        </div>
      ) : null}
      {status?.availability === 'unavailable' ? (
        <div className="module-unavailable" role="status">
          <strong>{selectedSubview.label} nu este disponibil</strong>
          <span>{status.reason}</span>
          <small>{unavailableSubviewCopy(selectedSubview)}</small>
        </div>
      ) : (
        <DashboardCanvas
          widgets={widgets}
          editMode={editMode}
          resetToken={resetToken}
          storageKey={`unihub-insight:${module}-${selectedSubview.id}-layout:v2`}
          onInspect={setInspectWidget}
          onExport={setInspectWidget}
        />
      )}
      {inspectWidget && inspectedQuery && inspectedMetric && inspectedResult && snapshotId ? (
        <Suspense fallback={null}>
          <QueryInspector
            dashboardId={null}
            snapshotId={snapshotId}
            search={input}
            result={inspectedResult}
            metric={inspectedMetric}
            onClose={() => setInspectWidget(null)}
          />
        </Suspense>
      ) : null}
    </ModuleProvider>
  );
}
