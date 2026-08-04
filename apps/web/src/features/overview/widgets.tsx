import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from '@tanstack/react-table';
import type { EChartsCoreOption } from 'echarts/core';
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  CircleDollarSign,
  Gauge,
  Minus,
  ReceiptText,
  Sparkles,
  Store,
  TriangleAlert,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import { EChart } from '../../components/charts/EChart';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatCurrency, formatInteger, formatPercent } from '../../lib/format';
import { useOverviewData } from './context';
import type { KpiMetric, PerformanceRow } from './schemas';

function formatMetric(metric: KpiMetric): string {
  switch (metric.unit) {
    case 'currency':
      return formatCurrency(metric.value, true);
    case 'percent':
      return formatPercent(metric.value);
    case 'integer':
      return formatInteger(metric.value);
    case 'decimal':
      return metric.value.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
  }
}

function formatSupporting(metric: KpiMetric): string {
  const value = metric.supporting_value;
  if (value === null || value === undefined) return '—';
  if (metric.id === 'forecast.linear') return formatPercent(value);
  if (metric.id === 'receipt_2plus_pct') return formatInteger(value);
  return formatCurrency(value, true);
}

function KpiIcon({ id }: { id: string }) {
  if (id === 'sales.total') return <CircleDollarSign size={18} />;
  if (id === 'target.progress_pct') return <Gauge size={18} />;
  if (id === 'forecast.linear') return <Sparkles size={18} />;
  return <ReceiptText size={18} />;
}

function Delta({ metric }: { metric: KpiMetric }) {
  if (metric.delta_pct === null || metric.delta_pct === undefined) {
    return (
      <span className="kpi-delta kpi-delta--neutral">
        <Minus size={13} /> Fără reper
      </span>
    );
  }
  const positive = metric.delta_pct >= 0;
  return (
    <span className={`kpi-delta ${positive ? 'kpi-delta--positive' : 'kpi-delta--negative'}`}>
      {positive ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
      {formatPercent(Math.abs(metric.delta_pct))}
    </span>
  );
}

function KpiWidget({ metricId }: { metricId: string }) {
  const { kpis } = useOverviewData();
  const metric = kpis.find((item) => item.id === metricId);
  if (!metric) return <EmptyState message="Metrica nu este disponibilă în contractul curent." />;

  return (
    <div className="kpi-widget">
      <div className={`kpi-icon kpi-icon--${metric.risk}`}>
        <KpiIcon id={metric.id} />
      </div>
      <div className="kpi-main">
        <strong>{formatMetric(metric)}</strong>
        <Delta metric={metric} />
      </div>
      <div className="kpi-support">
        {metric.supporting_value !== null && metric.supporting_value !== undefined ? (
          <>
            <span>{metric.supporting_label ?? 'Detaliu'}</span>
            <b>{formatSupporting(metric)}</b>
          </>
        ) : (
          <span>{metric.delta_label ?? 'Perioada selectată'}</span>
        )}
      </div>
    </div>
  );
}

export function SalesKpiWidget() {
  return <KpiWidget metricId="sales.total" />;
}

export function TargetKpiWidget() {
  return <KpiWidget metricId="target.progress_pct" />;
}

export function ForecastKpiWidget() {
  return <KpiWidget metricId="forecast.linear" />;
}

export function ReceiptKpiWidget() {
  return <KpiWidget metricId="receipt_2plus_pct" />;
}

export function SalesTrendWidget() {
  const { daily, meta } = useOverviewData();
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 280,
      aria: {
        enabled: true,
        description: `Evoluția cumulată a vânzărilor pentru ${meta.period}.`,
      },
      grid: { top: 36, right: 18, bottom: 30, left: 56 },
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: unknown) =>
          typeof value === 'number' ? formatCurrency(value) : '—',
      },
      legend: {
        top: 0,
        right: 0,
        icon: 'roundRect',
        textStyle: { color: '#64748b', fontSize: 11 },
      },
      xAxis: {
        type: 'category',
        data: daily.map((point) => point.day),
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#dbe3ef' } },
        axisTick: { show: false },
        axisLabel: { color: '#64748b', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          color: '#64748b',
          fontSize: 10,
          formatter: (value: string | number) => formatCurrency(Number(value), true),
        },
        splitLine: { lineStyle: { color: '#e9eef5', type: 'dashed' } },
      },
      series: [
        {
          type: 'line',
          name: 'Realizat',
          data: daily.map((point) => point.sales),
          showSymbol: false,
          connectNulls: false,
          smooth: 0.18,
          lineStyle: { width: 3, color: '#4f46e5' },
          itemStyle: { color: '#4f46e5' },
          areaStyle: { color: 'rgba(79,70,229,0.10)' },
          emphasis: { focus: 'series' },
        },
        {
          type: 'line',
          name: 'Target pace',
          data: daily.map((point) => point.target_pace),
          showSymbol: false,
          lineStyle: { width: 2, color: '#0f766e', type: 'dashed' },
          itemStyle: { color: '#0f766e' },
          emphasis: { focus: 'series' },
        },
        {
          type: 'line',
          name: 'Forecast',
          data: daily.map((point) => point.forecast ?? null),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2, color: '#d97706', type: 'dotted' },
          itemStyle: { color: '#d97706' },
          emphasis: { focus: 'series' },
        },
        {
          type: 'line',
          name: meta.comparison === 'previous-year' ? 'Anul trecut' : 'Luna precedentă',
          data: daily.map((point) => point.comparison ?? null),
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: '#94a3b8' },
          itemStyle: { color: '#94a3b8' },
          emphasis: { focus: 'series' },
        },
      ],
    }),
    [daily, meta.comparison, meta.period],
  );

  return (
    <EChart
      option={option}
      className="chart--fill"
      ariaLabel={`Grafic vânzări cumulative pentru ${meta.period}`}
    />
  );
}

export function ContributionWidget() {
  const { contribution } = useOverviewData();
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 260,
      tooltip: {
        trigger: 'item',
        formatter: '{b}<br/>{c} RON · {d}%',
      },
      legend: {
        bottom: 0,
        left: 'center',
        textStyle: { color: '#64748b', fontSize: 11 },
      },
      series: [
        {
          type: 'pie',
          radius: ['54%', '76%'],
          center: ['50%', '43%'],
          avoidLabelOverlap: true,
          itemStyle: { borderColor: '#ffffff', borderWidth: 3, borderRadius: 6 },
          label: { show: false },
          emphasis: {
            label: { show: true, fontSize: 13, fontWeight: 700 },
          },
          data: contribution.map((item) => ({ name: item.label, value: item.value })),
        },
      ],
    }),
    [contribution],
  );

  if (contribution.length === 0) {
    return <EmptyState message="Nu există contribuții pentru filtrarea curentă." />;
  }
  return <EChart option={option} className="chart--fill" ariaLabel="Contribuția firmelor" />;
}

function RiskBadge({ risk }: { risk: PerformanceRow['risk'] }) {
  const labels = { healthy: 'Sănătos', watch: 'Atenție', risk: 'Risc' } as const;
  return <span className={`risk-badge risk-badge--${risk}`}>{labels[risk]}</span>;
}

export function PerformanceWidget() {
  const { performance } = useOverviewData();
  const [sorting, setSorting] = useState<SortingState>([{ id: 'progress', desc: false }]);
  const columns = useMemo<ColumnDef<PerformanceRow>[]>(
    () => [
      {
        accessorKey: 'label',
        header: 'Magazin',
        cell: ({ row }) => (
          <div className="entity-cell">
            <Store size={14} />
            <div>
              <strong>{row.original.label}</strong>
              <span>{row.original.context}</span>
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'sales',
        header: 'Vânzări',
        cell: ({ getValue }) => formatCurrency(Number(getValue()), true),
      },
      {
        accessorKey: 'target',
        header: 'Target',
        cell: ({ getValue }) => formatCurrency(Number(getValue()), true),
      },
      {
        id: 'progress',
        accessorKey: 'progress_pct',
        header: 'Realizare',
        cell: ({ getValue }) => formatPercent(getValue<number | null>()),
      },
      {
        accessorKey: 'delta_pct',
        header: 'Δ reper',
        cell: ({ getValue }) => {
          const value = getValue<number | null>();
          return value === null || value === undefined ? '—' : formatPercent(value);
        },
      },
      {
        accessorKey: 'risk',
        header: 'Status',
        cell: ({ getValue }) => <RiskBadge risk={getValue<PerformanceRow['risk']>()} />,
      },
    ],
    [],
  );
  const table = useReactTable({
    data: performance,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (performance.length === 0) {
    return <EmptyState message="Nu există magazine în scope-ul selectat." />;
  }

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  {header.isPlaceholder ? null : (
                    <button
                      type="button"
                      className="table-sort"
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {header.column.getIsSorted() === 'asc'
                        ? ' ↑'
                        : header.column.getIsSorted() === 'desc'
                          ? ' ↓'
                          : ''}
                    </button>
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AlertsWidget() {
  const { alerts } = useOverviewData();
  const icons = {
    info: CheckCircle2,
    warning: TriangleAlert,
    critical: AlertCircle,
  } as const;

  if (alerts.length === 0) {
    return <EmptyState message="Nu există alerte pentru scope-ul curent." />;
  }

  return (
    <div className="alert-list">
      {alerts.map((alert) => {
        const Icon = icons[alert.severity];
        return (
          <article key={alert.id} className={`insight-alert insight-alert--${alert.severity}`}>
            <Icon size={17} />
            <div>
              <strong>{alert.title}</strong>
              <p>{alert.description}</p>
              {alert.entity_label ? <span>{alert.entity_label}</span> : null}
            </div>
          </article>
        );
      })}
    </div>
  );
}
