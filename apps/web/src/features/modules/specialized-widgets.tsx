import type { EChartsCoreOption } from 'echarts/core';
import { useMemo, useState } from 'react';
import { ChartTypeSelector } from '../../components/charts/ChartTypeSelector';
import { chartRangeEventToMonthRange, resolveChartSpec } from '../../components/charts/chart-spec';
import {
  BOXPLOT_MIN_SAMPLE_SIZE,
  buildHistogramBins,
  finiteSortedValues,
  summarizeDistribution,
} from '../../components/charts/distribution';
import { EChart, type EChartEvent } from '../../components/charts/EChart';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatCurrency, formatInteger, formatPercent } from '../../lib/format';
import type { MetricDefinition, QueryDataset } from '../query/schemas';
import {
  useModuleData,
  useModuleEntityOpen,
  useModuleUrlRangeChange,
  useModuleUrlStateChange,
  useModuleUrlStateReset,
} from './context';
import { moduleEntityDimension } from './interactions';

export function ModulePaceWidget() {
  const data = useModuleData();
  const sales = data.kpis.find((metric) => metric.id === 'sales.total');
  const progressMetric = data.kpis.find((metric) => metric.id === 'target.progress_pct');
  if (!sales || !progressMetric) {
    return (
      <EmptyState message="Pace-ul nu poate fi calculat fără vânzări și target autoritativ." />
    );
  }
  const target = progressMetric.supporting_value;
  const gap = target === null || target === undefined ? null : target - sales.value;
  const boundedProgress = Math.max(0, Math.min(progressMetric.value, 100));
  return (
    <div className="module-pace-widget">
      <div className="module-pace-value">
        <span>Realizare în luna selectată</span>
        <strong>{formatPercent(progressMetric.value)}</strong>
      </div>
      <progress
        aria-label={`Realizare target ${formatPercent(progressMetric.value)}`}
        max={100}
        value={boundedProgress}
      />
      <div className="module-pace-contract">
        <div>
          <span>Realizat</span>
          <strong>{formatCurrency(sales.value, true)}</strong>
        </div>
        <div>
          <span>Target</span>
          <strong>
            {target === null || target === undefined ? '—' : formatCurrency(target, true)}
          </strong>
        </div>
        <div>
          <span>{gap !== null && gap < 0 ? 'Peste target' : 'Gap'}</span>
          <strong>{gap === null ? '—' : formatCurrency(Math.abs(gap), true)}</strong>
        </div>
      </div>
    </div>
  );
}

export function ModuleRankingWidget() {
  const data = useModuleData();
  const onEntityOpen = useModuleEntityOpen();
  const onUrlStateChange = useModuleUrlStateChange();
  const onUrlStateReset = useModuleUrlStateReset();
  const rows = useMemo(() => {
    const sorted = [...data.breakdown].sort(
      (left, right) => (right.progress_pct ?? right.primary) - (left.progress_pct ?? left.primary),
    );
    const top = sorted.slice(0, 5).map((row) => ({ ...row, group: 'Top' as const }));
    const topIds = new Set(top.map((row) => row.id));
    const bottom = sorted
      .slice(-5)
      .filter((row) => !topIds.has(row.id))
      .map((row) => ({ ...row, group: 'Bottom' as const }));
    return [...top, ...bottom];
  }, [data.breakdown]);
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      aria: { enabled: true, description: `Clasament ${data.title}.` },
      grid: { top: 8, right: 24, bottom: 30, left: 118 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'value',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatPercent(value),
        },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map((row) => `${row.group} · ${row.label}`),
        axisLabel: { color: '#64748b', fontSize: 9, width: 108, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: rows.map((row) => ({
            value: row.progress_pct ?? row.primary,
            itemStyle: {
              color: row.risk === 'risk' ? '#e11d48' : row.risk === 'watch' ? '#d97706' : '#0f766e',
              borderRadius: [0, 5, 5, 0],
            },
          })),
        },
      ],
    }),
    [data.title, rows],
  );
  if (rows.length === 0) return <EmptyState message="Clasamentul nu are entități eligibile." />;
  const handleRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) {
      onUrlStateChange?.({
        dimensionId: moduleEntityDimension[data.module],
        value: row.id,
        label: row.label,
      });
    }
  };
  const openRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) {
      onEntityOpen?.({
        dimensionId: moduleEntityDimension[data.module],
        value: row.id,
        label: row.label,
      });
    }
  };
  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel={`Clasament ${data.title}`}
      pngExport={{ filename: `${data.module}-${data.meta.period}-ranking`, pixelRatio: 2 }}
      onEvent={handleRow}
      onDoubleEvent={openRow}
      {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
    />
  );
}

export function ModuleProductivityScatterWidget() {
  const data = useModuleData();
  const onEntityOpen = useModuleEntityOpen();
  const onUrlStateChange = useModuleUrlStateChange();
  const onUrlStateReset = useModuleUrlStateReset();
  const rows = useMemo(
    () =>
      data.breakdown.filter(
        (row) =>
          row.tertiary !== null &&
          row.tertiary !== undefined &&
          row.progress_pct !== null &&
          row.progress_pct !== undefined,
      ),
    [data.breakdown],
  );
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      aria: {
        enabled: true,
        description: 'Relația dintre productivitatea zilnică și realizarea targetului.',
      },
      grid: { top: 18, right: 22, bottom: 48, left: 70 },
      tooltip: {
        trigger: 'item',
        formatter: (input: unknown) => {
          const item = input as { dataIndex?: number };
          const row = item.dataIndex === undefined ? undefined : rows[item.dataIndex];
          return row
            ? `${row.label}<br/>${formatCurrency(row.tertiary ?? 0, true)} / zi-agent<br/>${formatPercent(row.progress_pct)}`
            : '';
        },
      },
      xAxis: {
        type: 'value',
        name: 'Productivitate / zi-agent',
        nameLocation: 'middle',
        nameGap: 31,
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatCurrency(value, true),
        },
      },
      yAxis: {
        type: 'value',
        name: 'Realizare target',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatPercent(value),
        },
        splitLine: { lineStyle: { color: '#e7edf5', type: 'dashed' } },
      },
      series: [
        {
          type: 'scatter',
          symbolSize: 12,
          data: rows.map((row) => [row.tertiary, row.progress_pct]),
          itemStyle: { color: '#4f46e5', opacity: 0.78 },
        },
      ],
    }),
    [rows],
  );
  if (rows.length === 0) {
    return <EmptyState message="Relația productivitate × target nu are perechi complete." />;
  }
  const handleRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) {
      onUrlStateChange?.({
        dimensionId: moduleEntityDimension[data.module],
        value: row.id,
        label: row.label,
      });
    }
  };
  const openRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) {
      onEntityOpen?.({
        dimensionId: moduleEntityDimension[data.module],
        value: row.id,
        label: row.label,
      });
    }
  };
  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel="Productivitate versus realizare target"
      pngExport={{ filename: `${data.module}-${data.meta.period}-productivity`, pixelRatio: 2 }}
      onEvent={handleRow}
      onDoubleEvent={openRow}
      {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
    />
  );
}

export function ModuleFocusRankingWidget() {
  const data = useModuleData();
  const onEntityOpen = useModuleEntityOpen();
  const onUrlStateChange = useModuleUrlStateChange();
  const onUrlStateReset = useModuleUrlStateReset();
  const rows = useMemo(() => {
    const sorted = [...data.breakdown].sort(
      (left, right) => (right.progress_pct ?? 0) - (left.progress_pct ?? 0),
    );
    const top = sorted.slice(0, 5).map((row) => ({ ...row, group: 'Top' as const }));
    const topIds = new Set(top.map((row) => row.id));
    const bottom = sorted
      .slice(-5)
      .filter((row) => !topIds.has(row.id))
      .map((row) => ({ ...row, group: 'Bottom' as const }));
    return [...top, ...bottom];
  }, [data.breakdown]);
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      aria: {
        enabled: true,
        description: 'Top și Bottom magazine observate după ponderea vânzărilor Focus.',
      },
      grid: { top: 8, right: 24, bottom: 30, left: 128 },
      tooltip: {
        trigger: 'item',
        formatter: (input: unknown) => {
          const item = input as { dataIndex?: number };
          const row = item.dataIndex === undefined ? undefined : rows[item.dataIndex];
          return row
            ? [
                row.label,
                `Pondere Focus: ${formatPercent(row.progress_pct ?? 0)}`,
                `Vânzări Focus: ${formatCurrency(row.primary, true)}`,
                `Cantitate netă: ${(row.secondary ?? 0).toLocaleString('ro-RO')}`,
                `Produse active: ${(row.tertiary ?? 0).toLocaleString('ro-RO')}`,
              ].join('<br/>')
            : '';
        },
      },
      xAxis: {
        type: 'value',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatPercent(value),
        },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map((row) => `${row.group} · ${row.label}`),
        axisLabel: { color: '#64748b', fontSize: 9, width: 118, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: rows.map((row) => ({
            value: row.progress_pct ?? 0,
            itemStyle: {
              color: row.group === 'Top' ? '#0f766e' : '#d97706',
              borderRadius: [0, 5, 5, 0],
            },
          })),
        },
      ],
    }),
    [rows],
  );
  if (rows.length === 0) {
    return <EmptyState message="Nu există magazine observate eligibile pentru Focus." />;
  }
  const handleRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) {
      onUrlStateChange?.({ dimensionId: 'store', value: row.id, label: row.label });
    }
  };
  const openRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) onEntityOpen?.({ dimensionId: 'store', value: row.id, label: row.label });
  };
  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel="Top și Bottom magazine observate Focus"
      pngExport={{ filename: `campaigns-${data.meta.period}-focus-ranking`, pixelRatio: 2 }}
      onEvent={handleRow}
      onDoubleEvent={openRow}
      {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
    />
  );
}

function formatCampaignValue(value: number, unit: string): string {
  if (unit === 'currency') return formatCurrency(value, true);
  if (unit === 'percent') return formatPercent(value);
  if (unit === 'integer') return formatInteger(value);
  return value.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
}

/** A mechanism-neutral ranking used by Promo, Incentive, Folii and Concurs. */
export function ModuleCampaignRankingWidget() {
  const data = useModuleData();
  const onEntityOpen = useModuleEntityOpen();
  const onUrlStateChange = useModuleUrlStateChange();
  const onUrlStateReset = useModuleUrlStateReset();
  const rows = useMemo(
    () => [...data.breakdown].sort((left, right) => right.primary - left.primary).slice(0, 10),
    [data.breakdown],
  );
  const axis = data.axes[0];
  const dimension = data.entity_dimension ?? moduleEntityDimension[data.module];
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      aria: {
        enabled: true,
        description: `Clasament ${data.title} după ${axis?.label ?? 'valoare'}.`,
      },
      grid: { top: 8, right: 24, bottom: 30, left: 128 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (input: unknown) => {
          const item = input as { dataIndex?: number };
          const row = item.dataIndex === undefined ? undefined : rows[item.dataIndex];
          return row
            ? [
                row.label,
                `${axis?.label ?? 'Valoare'}: ${formatCampaignValue(row.primary, axis?.unit ?? 'decimal')}`,
                row.context,
              ].join('<br/>')
            : '';
        },
      },
      xAxis: {
        type: 'value',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatCampaignValue(value, axis?.unit ?? 'decimal'),
        },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: rows.map((row) => row.label),
        axisLabel: { color: '#64748b', fontSize: 9, width: 118, overflow: 'truncate' },
      },
      series: [
        {
          type: 'bar',
          data: rows.map((row) => ({
            value: row.primary,
            itemStyle: {
              color: row.risk === 'risk' ? '#e11d48' : row.risk === 'watch' ? '#d97706' : '#4f46e5',
              borderRadius: [0, 5, 5, 0],
            },
          })),
        },
      ],
    }),
    [axis, data.title, rows],
  );
  if (rows.length === 0)
    return <EmptyState message="Nu există entități eligibile pentru mecanism." />;
  const interaction = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (!row) return undefined;
    const value = dimension === 'agent' ? row.label : (row.id.split(':').at(-1) ?? row.id);
    return { dimensionId: dimension, value, label: row.label };
  };
  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel={`Clasament ${data.title}`}
      pngExport={{ filename: `${data.module}-${data.meta.period}-campaign-ranking`, pixelRatio: 2 }}
      onEvent={(event) => {
        const item = interaction(event);
        if (item) onUrlStateChange?.(item);
      }}
      onDoubleEvent={(event) => {
        const item = interaction(event);
        if (item) onEntityOpen?.(item);
      }}
      {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
    />
  );
}

export function ModulePlanningAccuracyWidget() {
  const data = useModuleData();
  const onEntityOpen = useModuleEntityOpen();
  const onUrlStateChange = useModuleUrlStateChange();
  const onUrlStateReset = useModuleUrlStateReset();
  const rows = useMemo(
    () =>
      data.breakdown.filter(
        (row) =>
          row.secondary !== null &&
          row.secondary !== undefined &&
          Number.isFinite(row.secondary) &&
          Number.isFinite(row.primary),
      ),
    [data.breakdown],
  );
  const extent = useMemo(() => {
    const values = rows.flatMap((row) => [row.secondary ?? 0, row.primary]);
    return values.length > 0 ? [Math.min(...values), Math.max(...values)] : [0, 1];
  }, [rows]);
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      aria: {
        enabled: true,
        description: 'Actual observat versus forecast publicat, pentru fiecare magazin eligibil.',
      },
      grid: { top: 18, right: 22, bottom: 48, left: 70 },
      tooltip: {
        trigger: 'item',
        formatter: (input: unknown) => {
          const item = input as { dataIndex?: number };
          const row = item.dataIndex === undefined ? undefined : rows[item.dataIndex];
          const actual = row?.secondary;
          if (!row || actual === null || actual === undefined) return '';
          return [
            row.label,
            `Actual: ${formatCurrency(actual, true)}`,
            `Forecast: ${formatCurrency(row.primary, true)}`,
            `Diferență: ${formatCurrency(row.primary - actual, true)}`,
          ].join('<br/>');
        },
      },
      xAxis: {
        type: 'value',
        name: 'Actual observat',
        nameLocation: 'middle',
        nameGap: 31,
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatCurrency(value, true),
        },
      },
      yAxis: {
        type: 'value',
        name: 'Forecast',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatCurrency(value, true),
        },
        splitLine: { lineStyle: { color: '#e7edf5', type: 'dashed' } },
      },
      series: [
        {
          type: 'scatter',
          symbolSize: 12,
          data: rows.map((row) => [row.secondary, row.primary]),
          itemStyle: { color: '#4f46e5', opacity: 0.78 },
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            label: { formatter: 'Forecast = actual', color: '#64748b', fontSize: 9 },
            lineStyle: { color: '#94a3b8', type: 'dashed' },
            data: [[{ coord: [extent[0], extent[0]] }, { coord: [extent[1], extent[1]] }]],
          },
        },
      ],
    }),
    [extent, rows],
  );
  if (rows.length === 0) {
    return <EmptyState message="Nu există perechi complete Actual × Forecast pe magazin." />;
  }
  const handleRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) onUrlStateChange?.({ dimensionId: 'store', value: row.id, label: row.label });
  };
  const openRow = (event: EChartEvent) => {
    const row = event.dataIndex === undefined ? undefined : rows[event.dataIndex];
    if (row) onEntityOpen?.({ dimensionId: 'store', value: row.id, label: row.label });
  };
  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel="Actual observat versus forecast pe magazin"
      pngExport={{ filename: `planning-${data.meta.period}-accuracy`, pixelRatio: 2 }}
      onEvent={handleRow}
      onDoubleEvent={openRow}
      {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
    />
  );
}

export function ModuleHistogramWidget() {
  const data = useModuleData();
  const [requestedType, setRequestedType] = useState<'histogram' | 'boxplot'>('histogram');
  const profile =
    data.module === 'performance'
      ? {
          label: 'Realizare target',
          unit: 'percent' as const,
          values: data.breakdown.map((row) => row.progress_pct),
        }
      : {
          label: 'Salariu mediu agregat',
          unit: 'currency' as const,
          values: data.breakdown.map((row) => row.secondary),
        };
  const values = useMemo(() => finiteSortedValues(profile.values), [profile.values]);
  const statistics = useMemo(() => summarizeDistribution(values), [values]);
  const bins = useMemo(() => buildHistogramBins(values), [values]);
  const canRenderBoxplot = values.length >= BOXPLOT_MIN_SAMPLE_SIZE;
  const activeType = requestedType === 'boxplot' && canRenderBoxplot ? 'boxplot' : 'histogram';
  const option = useMemo<EChartsCoreOption>(() => {
    const formatValue = (value: number): string =>
      profile.unit === 'percent' ? formatPercent(value) : formatCurrency(value, true);
    if (activeType === 'boxplot' && statistics) {
      return {
        animationDuration: 220,
        aria: {
          enabled: true,
          description: `Box plot ${profile.label}, calculat pe același set de agregate ca histograma.`,
        },
        grid: { top: 18, right: 18, bottom: 40, left: 64, containLabel: true },
        tooltip: { trigger: 'item', confine: true },
        xAxis: { type: 'category', data: [profile.label] },
        yAxis: {
          type: 'value',
          axisLabel: { color: '#64748b', fontSize: 9, formatter: formatValue },
          splitLine: { lineStyle: { color: '#e7edf5', type: 'dashed' } },
        },
        series: [
          {
            type: 'boxplot',
            name: profile.label,
            data: [
              [
                statistics.whiskerLow,
                statistics.q1,
                statistics.median,
                statistics.q3,
                statistics.whiskerHigh,
              ],
            ],
            itemStyle: { color: '#c7d2fe', borderColor: '#4f46e5', borderWidth: 2 },
          },
          {
            type: 'scatter',
            name: 'Outlieri IQR',
            data: statistics.outliers.map((value) => [0, value]),
            itemStyle: { color: '#e11d48' },
          },
        ],
      };
    }
    return {
      animationDuration: 220,
      aria: {
        enabled: true,
        description: `Histogramă ${profile.label}, calculată numai din agregatele livrate de API.`,
      },
      grid: { top: 18, right: 18, bottom: 46, left: 54 },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      xAxis: {
        type: 'category',
        name: profile.label,
        nameLocation: 'middle',
        nameGap: 31,
        data: bins.map((bin) =>
          bin.start === bin.end
            ? formatValue(bin.start)
            : `${formatValue(bin.start)}–${formatValue(bin.end)}`,
        ),
        axisLabel: { color: '#64748b', fontSize: 8, rotate: bins.length > 5 ? 24 : 0 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        name: 'Entități',
        axisLabel: { color: '#64748b', fontSize: 9 },
        splitLine: { lineStyle: { color: '#e7edf5', type: 'dashed' } },
      },
      series: [
        {
          type: 'bar',
          data: bins.map((bin) => bin.count),
          itemStyle: { color: '#4f46e5', borderRadius: [5, 5, 0, 0] },
        },
      ],
    };
  }, [activeType, bins, profile.label, profile.unit, statistics]);
  if (bins.length === 0) {
    return <EmptyState message="Nu există suficiente agregate eligibile pentru distribuție." />;
  }
  if (!statistics) return null;
  const formatStatistic = (value: number): string =>
    profile.unit === 'percent' ? formatPercent(value) : formatCurrency(value, true);
  return (
    <div className="module-distribution-widget">
      <div className="module-distribution-controls">
        <ChartTypeSelector
          value={activeType}
          options={canRenderBoxplot ? ['histogram', 'boxplot'] : ['histogram']}
          onChange={setRequestedType}
          label="Vizualizare distribuție"
        />
        {!canRenderBoxplot ? (
          <span className="module-distribution-note" role="status">
            Box plot disponibil de la {BOXPLOT_MIN_SAMPLE_SIZE} agregate eligibile.
          </span>
        ) : null}
      </div>
      <dl className="module-distribution-stats" aria-label="Statistici distribuție">
        <div>
          <dt>n</dt>
          <dd>{values.length}</dd>
        </div>
        <div>
          <dt>Mediană</dt>
          <dd>{formatStatistic(statistics.median)}</dd>
        </div>
        <div>
          <dt>Q1–Q3</dt>
          <dd>
            {formatStatistic(statistics.q1)}–{formatStatistic(statistics.q3)}
          </dd>
        </div>
        <div>
          <dt>Outlieri IQR</dt>
          <dd>{statistics.outliers.length}</dd>
        </div>
      </dl>
      <EChart
        option={option}
        className="chart--fill"
        ariaLabel={`${activeType === 'boxplot' ? 'Box plot' : 'Histogramă'} ${profile.label}`}
        pngExport={{ filename: `${data.module}-${data.meta.period}-${activeType}`, pixelRatio: 2 }}
      />
    </div>
  );
}

export function ModuleWaterfallWidget() {
  const data = useModuleData();
  const revenue = data.kpis.find((metric) => metric.id === 'finance.revenue');
  const ebit = data.kpis.find((metric) => metric.id === 'finance.ebit');
  const resolved = useMemo(() => {
    if (!revenue || !ebit) return null;
    const dataset: QueryDataset = {
      dimensions: [
        { id: 'label', label: 'Pas reconciliere', kind: 'string', role: 'label' },
        { id: 'value', label: 'EBIT', kind: 'number', role: 'value' },
        { id: 'step_kind', label: 'Tip pas', kind: 'string', role: 'metadata' },
      ],
      rows: [
        { label: revenue.label, value: revenue.value, step_kind: 'start' },
        ...data.distribution.map((item) => ({
          label: item.label,
          value: -item.value,
          step_kind: 'delta',
        })),
        { label: ebit.label, value: ebit.value, step_kind: 'total' },
      ],
    };
    const metric: MetricDefinition = {
      id: 'finance.ebit',
      version: 1,
      display_name: 'EBIT',
      description: 'EBIT reconciliat din contractul Finance.',
      unit: 'currency',
      aggregation: 'derived',
      allowed_dimensions: ['category'],
      allowed_grains: ['month'],
      comparison_policy: 'none',
      allowed_comparisons: [],
      missing_policy: 'null',
      required_capability: 'insight:pnl',
      formula_reference: 'unihub-insight:metric:finance.ebit:v1',
      allowed_shapes: ['waterfall'],
      suppressible: false,
      source_authority: 'reporting_finance_month_v1',
      query_contract_version: 1,
      effective_from: null,
      effective_to: null,
    };
    return resolveChartSpec(metric, 'waterfall', dataset);
  }, [data.distribution, ebit, revenue]);
  if (!resolved) {
    return <EmptyState message="Waterfall-ul cere venit și EBIT din aceeași generație Finance." />;
  }
  if (resolved.kind === 'table') {
    return (
      <EmptyState message="Categoriile publicate nu reconciliază exact EBIT; waterfall-ul este refuzat." />
    );
  }
  return (
    <EChart
      option={resolved.option}
      className="chart--fill"
      ariaLabel="Waterfall venit, costuri și EBIT"
      pngExport={{ filename: `${data.module}-${data.meta.period}-waterfall`, pixelRatio: 2 }}
    />
  );
}

export function ModuleForecastWidget() {
  const data = useModuleData();
  const onEntityOpen = useModuleEntityOpen();
  const onUrlStateChange = useModuleUrlStateChange();
  const onUrlRangeChange = useModuleUrlRangeChange();
  const onUrlStateReset = useModuleUrlStateReset();
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 260,
      aria: {
        enabled: true,
        description: 'Forecast, actual observat și target din același snapshot Planning.',
      },
      grid: { top: 42, right: 18, bottom: data.trend.length > 1 ? 52 : 34, left: 68 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, right: 0, textStyle: { color: '#64748b', fontSize: 10 } },
      xAxis: {
        type: 'category',
        data: data.trend.map((point) => point.label),
        axisLabel: { color: '#64748b', fontSize: 9 },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#64748b',
          fontSize: 9,
          formatter: (value: number) => formatCurrency(value, true),
        },
        splitLine: { lineStyle: { color: '#e7edf5', type: 'dashed' } },
      },
      ...(data.trend.length > 1
        ? {
            dataZoom: [
              { type: 'inside', start: 0, end: 100, filterMode: 'none', realtime: false },
              {
                type: 'slider',
                start: 0,
                end: 100,
                height: 16,
                bottom: 2,
                filterMode: 'none',
                realtime: false,
              },
            ],
          }
        : {}),
      series: [
        {
          type: 'line',
          name: 'Forecast',
          data: data.trend.map((point) => point.primary),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 3, color: '#4f46e5' },
          itemStyle: { color: '#4f46e5' },
          areaStyle: { color: 'rgba(79,70,229,0.12)' },
        },
        {
          type: 'line',
          name: 'Actual',
          data: data.trend.map((point) => point.comparison ?? null),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2, color: '#0f766e' },
          itemStyle: { color: '#0f766e' },
        },
        {
          type: 'line',
          name: 'Target',
          data: data.trend.map((point) => point.target ?? null),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1.5, type: 'dashed', color: '#d97706' },
          itemStyle: { color: '#d97706' },
        },
      ],
    }),
    [data.trend],
  );
  if (data.trend.length === 0) {
    return <EmptyState message="Run-ul Planning nu publică încă un orizont de forecast." />;
  }
  const handlePoint = (event: EChartEvent) => {
    const point = event.dataIndex === undefined ? undefined : data.trend[event.dataIndex];
    if (point) onUrlStateChange?.({ dimensionId: 'time', value: point.key, label: point.label });
  };
  const openPoint = (event: EChartEvent) => {
    const point = event.dataIndex === undefined ? undefined : data.trend[event.dataIndex];
    if (point) onEntityOpen?.({ dimensionId: 'time', value: point.key, label: point.label });
  };
  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel="Forecast, actual și target"
      pngExport={{ filename: `${data.module}-${data.meta.period}-forecast`, pixelRatio: 2 }}
      onEvent={handlePoint}
      onDoubleEvent={openPoint}
      onRangeEvent={(event) => {
        const range = chartRangeEventToMonthRange(
          data.trend.map((point) => point.key),
          event,
        );
        if (range) onUrlRangeChange?.(range);
      }}
      {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
    />
  );
}

export function ModuleCalendarWidget() {
  const data = useModuleData();
  const onUrlStateReset = useModuleUrlStateReset();
  const rows = data.calendar;
  const values = useMemo(() => rows.map((row) => row.sales).filter(Number.isFinite), [rows]);
  const option = useMemo<EChartsCoreOption>(() => {
    const minimum = values.length > 0 ? Math.min(...values) : 0;
    const maximum = values.length > 0 ? Math.max(...values) : 1;
    return {
      animationDuration: 220,
      aria: {
        enabled: true,
        description:
          'Calendarul conține numai zile observate; lipsa unei celule nu este interpretată ca zero.',
      },
      tooltip: {
        position: 'top',
        confine: true,
        formatter: (input: unknown) => {
          const item = input as { dataIndex?: number };
          const row = item.dataIndex === undefined ? undefined : rows[item.dataIndex];
          if (!row) return '';
          return [
            row.date,
            formatCurrency(row.sales, true),
            `Cantitate netă: ${row.net_quantity.toLocaleString('ro-RO')}`,
            `Retur: ${row.return_quantity.toLocaleString('ro-RO')}`,
            `Bonuri: ${row.receipt_count.toLocaleString('ro-RO')}`,
            `Magazine observate: ${row.observed_store_count}`,
          ].join('<br/>');
        },
      },
      visualMap: {
        min: minimum,
        max: maximum === minimum ? minimum + 1 : maximum,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
      },
      calendar: {
        range: data.meta.period,
        top: 34,
        left: 38,
        right: 18,
        bottom: 54,
        cellSize: ['auto', 20],
        dayLabel: { firstDay: 1, nameMap: ['D', 'L', 'Ma', 'Mi', 'J', 'V', 'S'] },
        monthLabel: { show: false },
        yearLabel: { show: false },
      },
      series: [
        {
          type: 'heatmap',
          coordinateSystem: 'calendar',
          data: rows.map((row) => [row.date, row.sales]),
        },
      ],
    };
  }, [data.meta.period, rows, values]);
  if (rows.length === 0) {
    return <EmptyState message="Nu există zile observate pentru perioada și scope-ul selectat." />;
  }
  return (
    <div className="module-calendar-widget">
      <div className="module-calendar-contract" role="note">
        <strong>{rows.length} zile observate</strong>
        <span>
          până la {data.meta.as_of ?? 'cutoff necunoscut'} · zilele fără rând nu sunt transformate
          în zero
        </span>
      </div>
      <EChart
        option={option}
        className="chart--fill"
        ariaLabel={`Calendar zilnic observat ${data.meta.period}`}
        pngExport={{ filename: `sales-${data.meta.period}-calendar`, pixelRatio: 2 }}
        {...(onUrlStateReset ? { onBlankReset: onUrlStateReset } : {})}
      />
    </div>
  );
}
