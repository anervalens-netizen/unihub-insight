import { useMemo } from 'react';
import type { ChartUrlRangeEvent, ChartUrlStateEvent } from '../../components/charts/chart-spec';
import {
  applyWidgetChartOptions,
  buildSafePngExport,
  chartEventToUrlState,
  chartRangeEventToUrlState,
  resolveChartSpec,
} from '../../components/charts/chart-spec';
import { EChart } from '../../components/charts/EChart';
import { EmptyState } from '../../components/ui/EmptyState';
import { ErrorState } from '../../components/ui/ErrorState';
import { LoadingState } from '../../components/ui/LoadingState';
import { formatCurrency, formatInteger, formatPercent } from '../../lib/format';
import type {
  DatasetDimension,
  DatasetValue,
  MetricDefinition,
  QueryDataset,
  WidgetQueryResult,
} from '../query/schemas';
import { widgetFilterLabel } from './filter-resolution';
import type { DashboardWidget } from './schemas';

function formatNumber(value: number, unit: MetricDefinition['unit']): string {
  if (unit === 'currency') return formatCurrency(value, true);
  if (unit === 'percent') return formatPercent(value);
  if (unit === 'integer') return formatInteger(value);
  return value.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
}

function formatValue(
  value: DatasetValue | undefined,
  dimension: DatasetDimension | undefined,
  metric: MetricDefinition,
): string {
  if (value === null || value === undefined) return '—';
  if (dimension?.role === 'value' || dimension?.id === 'value') {
    const numericValue = typeof value === 'number' ? value : Number(value);
    if (Number.isFinite(numericValue)) return formatNumber(numericValue, metric.unit);
  }
  if (typeof value === 'number') return value.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
  if (typeof value === 'boolean') return value ? 'Da' : 'Nu';
  return value;
}

function sourceLabel(result: WidgetQueryResult): string {
  if (!result.meta) return '';
  return `${result.meta.source.source} · ${result.meta.source.status}`;
}

function sourceRisk(result: WidgetQueryResult): 'healthy' | 'watch' | 'risk' {
  const status = result.meta?.source.status;
  if (status === 'official') return 'healthy';
  if (status === 'partial' || status === 'stale') return 'watch';
  return 'risk';
}

function QueryMetadata({
  result,
  metric,
}: {
  result: WidgetQueryResult;
  metric: MetricDefinition;
}) {
  const source = result.meta?.source;
  const sources = Object.values(result.meta?.sources ?? {});
  return (
    <details className="query-metadata">
      <summary>
        <span>{source?.status ?? 'missing'}</span>
        <span>{source?.source ?? metric.source_authority}</span>
      </summary>
      <div>
        <span>Definiție: {metric.description}</span>
        <span>Formulă: {metric.formula_reference}</span>
        <span>Missing: {metric.missing_policy}</span>
        <span>
          Metric v{metric.version} · query v{metric.query_contract_version}
        </span>
        <span>
          Cutoff: {source?.cutoff ?? '—'} · as of: {source?.as_of ?? '—'} ·{' '}
          {source?.is_final ? 'final' : 'deschis'}
        </span>
        <span>
          Coverage: {source?.coverage_numerator ?? '—'}/{source?.coverage_denominator ?? '—'} ·
          authority: {source?.authority ?? '—'} · head {source?.authority_head ?? '—'}
        </span>
        <span>
          Generație: {source?.source_generation ?? '—'} · contract v
          {source?.contract_version ?? '—'} · rule {source?.rule_version ?? '—'}
        </span>
        {sources.length > 1
          ? sources.map((item) => (
              <span key={item.domain}>
                {item.domain}: {item.status} · cutoff {item.cutoff ?? '—'} · coverage{' '}
                {item.coverage_numerator ?? '—'}/{item.coverage_denominator ?? '—'} ·{' '}
                {item.authority}
              </span>
            ))
          : null}
        {source?.warnings.length ? <span>Warnings: {source.warnings.join(' · ')}</span> : null}
      </div>
    </details>
  );
}

function DatasetTable({
  dataset,
  metric,
  fallbackReason,
}: {
  dataset: QueryDataset;
  metric: MetricDefinition;
  fallbackReason?: string;
}) {
  return (
    <div className="table-scroll">
      {fallbackReason ? <span className="widget-filter-mode">Tabelă: {fallbackReason}</span> : null}
      <table className="data-table">
        <thead>
          <tr>
            {dataset.dimensions.map((dimension) => (
              <th key={dimension.id}>{dimension.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {dataset.rows.map((row) => (
            <tr
              key={dataset.dimensions.map((dimension) => String(row[dimension.id] ?? '')).join('|')}
            >
              {dataset.dimensions.map((dimension) => (
                <td key={dimension.id}>{formatValue(row[dimension.id], dimension, metric)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConfiguredChart({
  widget,
  dataset,
  metric,
  result,
  onUrlStateChange,
  onUrlRangeChange,
  onUrlStateReset,
}: {
  widget: DashboardWidget;
  dataset: QueryDataset;
  metric: MetricDefinition;
  result: WidgetQueryResult;
  onUrlStateChange?: (event: ChartUrlStateEvent) => void;
  onUrlRangeChange?: (event: ChartUrlRangeEvent) => void;
  onUrlStateReset?: () => void;
}) {
  const presentedDataset = useMemo(
    () =>
      widget.options.top_n
        ? { ...dataset, rows: dataset.rows.slice(0, widget.options.top_n) }
        : dataset,
    [dataset, widget.options.top_n],
  );
  const resolved = useMemo(
    () => resolveChartSpec(metric, widget.visualization, presentedDataset),
    [metric, presentedDataset, widget.visualization],
  );
  if (resolved.kind === 'table') {
    return (
      <div className="configured-table">
        <DatasetTable dataset={dataset} metric={metric} fallbackReason={resolved.reason} />
        <QueryMetadata result={result} metric={metric} />
      </div>
    );
  }
  const option = applyWidgetChartOptions(resolved.option, widget.visualization, widget.options);
  const pngExport = buildSafePngExport(resolved, widget.title);
  const pixelRatio = widget.options.pixel_ratio;
  return (
    <div className="configured-chart">
      <span className="widget-filter-mode">{widgetFilterLabel(widget)}</span>
      <EChart
        option={option}
        className="chart--fill"
        ariaLabel={widget.title}
        pngExport={{
          ...pngExport,
          pixelRatio: pixelRatio === 1 ? 1 : 2,
        }}
        onEvent={(event) => {
          const interaction = chartEventToUrlState(presentedDataset, event);
          if (interaction) onUrlStateChange?.(interaction);
        }}
        onDoubleEvent={(event) => {
          const interaction = chartEventToUrlState(presentedDataset, event);
          if (interaction) onUrlStateChange?.(interaction);
        }}
        onRangeEvent={(event) => {
          const range = chartRangeEventToUrlState(presentedDataset, event);
          if (range) onUrlRangeChange?.(range);
        }}
        {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
      />
      <details className="chart-backing-table">
        <summary>Date sursă accesibile</summary>
        <DatasetTable dataset={dataset} metric={metric} />
      </details>
      <QueryMetadata result={result} metric={metric} />
    </div>
  );
}

export function ConfiguredWidget({
  widget,
  result,
  metric,
  loading = false,
  requestError,
  onRetry,
  onUrlStateChange,
  onUrlRangeChange,
  onUrlStateReset,
}: {
  widget: DashboardWidget;
  result: WidgetQueryResult | undefined;
  metric: MetricDefinition | undefined;
  loading?: boolean;
  requestError?: unknown;
  onRetry?: () => void;
  onUrlStateChange?: (event: ChartUrlStateEvent) => void;
  onUrlRangeChange?: (event: ChartUrlRangeEvent) => void;
  onUrlStateReset?: () => void;
}) {
  if (loading) return <LoadingState label={`Se încarcă ${widget.title}…`} />;
  if (requestError) {
    return (
      <ErrorState
        message={
          requestError instanceof Error ? requestError.message : 'Batch-ul nu a putut fi încărcat.'
        }
        {...(onRetry ? { onRetry } : {})}
      />
    );
  }
  if (!result) return <EmptyState message="Widgetul nu este disponibil în batch-ul curent." />;
  if (result.error) {
    return (
      <ErrorState
        message={result.error.message}
        {...(result.error.retryable && onRetry ? { onRetry } : {})}
      />
    );
  }
  if (!result.dataset) return <EmptyState message="Datasetul metricii nu este disponibil." />;
  if (!metric) return <EmptyState message="Metrica nu mai există în catalogul activ." />;

  const { dataset } = result;
  if (result.meta?.source.status === 'unavailable') {
    return (
      <div className="configured-empty">
        <EmptyState
          message={`Sursa este unavailable: ${result.meta.source.source}. Contractul nu a livrat date.`}
        />
        <QueryMetadata result={result} metric={metric} />
      </div>
    );
  }
  if (dataset.rows.length === 0) {
    return (
      <div className="configured-empty">
        <EmptyState
          message={
            metric.suppressible
              ? 'Date lipsă sau suprimate conform contractului; nu se afișează zero inventat.'
              : 'Dataset fără rânduri pentru snapshotul și scope-ul curent.'
          }
        />
        <QueryMetadata result={result} metric={metric} />
      </div>
    );
  }
  if (widget.visualization === 'kpi') {
    const valueDimension =
      dataset.dimensions.find((dimension) => dimension.role === 'value') ??
      dataset.dimensions.find((dimension) => dimension.id === 'value');
    const value = dataset.rows[0]?.[valueDimension?.id ?? 'value'];
    if (value === null || value === undefined) {
      return (
        <div className="configured-empty">
          <EmptyState message="Valoarea este missing în snapshot; nu se înlocuiește cu zero." />
          <QueryMetadata result={result} metric={metric} />
        </div>
      );
    }
    return (
      <div className="configured-kpi">
        <strong>{formatValue(value, valueDimension, metric)}</strong>
        <small
          className={`risk-badge risk-badge--${sourceRisk(result)}`}
          title={`Snapshot ${result.meta?.snapshot_id ?? 'indisponibil'}`}
        >
          {sourceLabel(result)}
        </small>
        <em>{widgetFilterLabel(widget)}</em>
        <QueryMetadata result={result} metric={metric} />
      </div>
    );
  }
  if (widget.visualization === 'table') {
    return (
      <div className="configured-table">
        <DatasetTable dataset={dataset} metric={metric} />
        <QueryMetadata result={result} metric={metric} />
      </div>
    );
  }
  return (
    <ConfiguredChart
      widget={widget}
      dataset={dataset}
      metric={metric}
      result={result}
      {...(onUrlStateChange ? { onUrlStateChange } : {})}
      {...(onUrlRangeChange ? { onUrlRangeChange } : {})}
      {...(onUrlStateReset ? { onUrlStateReset } : {})}
    />
  );
}
