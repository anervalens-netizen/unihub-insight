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
  Hash,
  Minus,
  Sparkles,
  TriangleAlert,
} from 'lucide-react';
import { useMemo, useState } from 'react';

import { EChart } from '../../components/charts/EChart';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatCurrency, formatInteger, formatPercent } from '../../lib/format';
import { useModuleData } from './context';
import type { BreakdownRow, ChartKind, ModuleKpi } from './schemas';

function formatValue(value: number | null | undefined, unit: string, compact = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  if (unit === 'currency') return formatCurrency(value, compact);
  if (unit === 'percent') return formatPercent(value);
  if (unit === 'integer') return formatInteger(value);
  return value.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
}

function KpiIcon({ unit }: { unit: ModuleKpi['unit'] }) {
  if (unit === 'currency') return <CircleDollarSign size={18} />;
  if (unit === 'percent') return <Gauge size={18} />;
  if (unit === 'integer') return <Hash size={18} />;
  return <Sparkles size={18} />;
}

function ModuleKpiWidget({ index }: { index: number }) {
  const { kpis } = useModuleData();
  const metric = kpis[index];
  if (!metric) return <EmptyState message="Metrica nu este disponibilă pentru scope-ul curent." />;
  const delta = metric.delta_pct;
  return (
    <div className="kpi-widget">
      <div className={`kpi-icon kpi-icon--${metric.risk}`}>
        <KpiIcon unit={metric.unit} />
      </div>
      <div className="kpi-main">
        <strong>{formatValue(metric.value, metric.unit, true)}</strong>
        {delta === null || delta === undefined ? (
          <span className="kpi-delta kpi-delta--neutral">
            <Minus size={13} /> Fără reper
          </span>
        ) : (
          <span
            className={`kpi-delta ${delta >= 0 ? 'kpi-delta--positive' : 'kpi-delta--negative'}`}
          >
            {delta >= 0 ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {formatPercent(Math.abs(delta))}
          </span>
        )}
      </div>
      <div className="kpi-support">
        <span>{metric.supporting_label ?? metric.delta_label ?? 'Perioada selectată'}</span>
        {metric.supporting_value !== null && metric.supporting_value !== undefined ? (
          <b>
            {formatValue(
              metric.supporting_value,
              metric.id.includes('pct') ||
                metric.id.includes('ratio') ||
                metric.id.includes('accuracy')
                ? 'percent'
                : metric.unit,
              true,
            )}
          </b>
        ) : null}
      </div>
    </div>
  );
}

export function ModuleKpiOne() {
  return <ModuleKpiWidget index={0} />;
}
export function ModuleKpiTwo() {
  return <ModuleKpiWidget index={1} />;
}
export function ModuleKpiThree() {
  return <ModuleKpiWidget index={2} />;
}
export function ModuleKpiFour() {
  return <ModuleKpiWidget index={3} />;
}

function ChartToggle({
  options,
  value,
  onChange,
}: {
  options: readonly ChartKind[];
  value: ChartKind;
  onChange: (value: ChartKind) => void;
}) {
  const labels: Partial<Record<ChartKind, string>> = {
    line: 'Linie',
    area: 'Arie',
    bar: 'Coloane',
    donut: 'Donut',
  };
  return (
    <div className="chart-toggle">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className={value === option ? 'is-active' : ''}
          onClick={() => onChange(option)}
        >
          {labels[option] ?? option}
        </button>
      ))}
    </div>
  );
}

export function ModuleTrendWidget() {
  const data = useModuleData();
  const supported = data.supported_charts.filter(
    (kind): kind is 'line' | 'area' | 'bar' => kind === 'line' || kind === 'area' || kind === 'bar',
  );
  const choices: Array<'line' | 'area' | 'bar'> = supported.length > 0 ? supported : ['line'];
  const [kind, setKind] = useState<'line' | 'area' | 'bar'>(choices[0] ?? 'line');
  const primaryAxis = data.axes[0];
  const option = useMemo<EChartsCoreOption>(() => {
    const axisFormatter = (value: string | number): string =>
      formatValue(Number(value), primaryAxis?.unit ?? 'decimal', true);
    const mainSeries =
      kind === 'bar'
        ? {
            type: 'bar' as const,
            name: primaryAxis?.label ?? 'Valoare',
            data: data.trend.map((point) => point.primary),
            itemStyle: { color: '#4f46e5', borderRadius: [5, 5, 0, 0] },
          }
        : {
            type: 'line' as const,
            name: primaryAxis?.label ?? 'Valoare',
            data: data.trend.map((point) => point.primary),
            showSymbol: false,
            smooth: 0.18,
            lineStyle: { width: 3, color: '#4f46e5' },
            itemStyle: { color: '#4f46e5' },
            ...(kind === 'area' ? { areaStyle: { color: 'rgba(79,70,229,0.12)' } } : {}),
          };
    return {
      animationDuration: 260,
      aria: { enabled: true, description: `Evoluție ${data.title} pentru ${data.meta.period}.` },
      grid: { top: 42, right: 18, bottom: 34, left: 62 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, right: 0, textStyle: { color: '#64748b', fontSize: 11 } },
      xAxis: {
        type: 'category',
        data: data.trend.map((point) => point.label),
        axisTick: { show: false },
        axisLabel: { color: '#64748b', fontSize: 10 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#64748b', fontSize: 10, formatter: axisFormatter },
        splitLine: { lineStyle: { color: '#e7edf5', type: 'dashed' } },
      },
      series: [
        mainSeries,
        {
          type: 'line',
          name: 'Reper / actual',
          data: data.trend.map((point) => point.comparison ?? null),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 1.5, color: '#94a3b8' },
          itemStyle: { color: '#94a3b8' },
        },
        {
          type: 'line',
          name: 'Target',
          data: data.trend.map((point) => point.target ?? null),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2, type: 'dashed', color: '#0f766e' },
          itemStyle: { color: '#0f766e' },
        },
      ],
    };
  }, [data, kind, primaryAxis]);
  if (data.trend.length === 0)
    return <EmptyState message="Nu există serie temporală pentru scope-ul curent." />;
  return (
    <div className="chart-widget">
      <ChartToggle options={choices} value={kind} onChange={setKind} />
      <EChart option={option} className="chart--fill" ariaLabel={`Evoluție ${data.title}`} />
    </div>
  );
}

export function ModuleDistributionWidget() {
  const data = useModuleData();
  const choices: Array<'donut' | 'bar'> = data.supported_charts.includes('donut')
    ? ['donut', 'bar']
    : ['bar'];
  const [kind, setKind] = useState<'donut' | 'bar'>(choices[0] ?? 'bar');
  const option = useMemo<EChartsCoreOption>(
    () =>
      kind === 'donut'
        ? {
            tooltip: { trigger: 'item' },
            legend: { bottom: 0, left: 'center', textStyle: { color: '#64748b', fontSize: 10 } },
            series: [
              {
                type: 'pie',
                radius: ['48%', '72%'],
                center: ['50%', '43%'],
                label: { show: false },
                itemStyle: { borderColor: '#fff', borderWidth: 2, borderRadius: 5 },
                data: data.distribution.map((item) => ({ name: item.label, value: item.value })),
              },
            ],
          }
        : {
            grid: { top: 8, right: 12, bottom: 28, left: 96 },
            tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
            xAxis: { type: 'value', axisLabel: { color: '#64748b', fontSize: 9 } },
            yAxis: {
              type: 'category',
              inverse: true,
              data: data.distribution.map((item) => item.label),
              axisLabel: { color: '#64748b', fontSize: 9, width: 88, overflow: 'truncate' },
            },
            series: [
              {
                type: 'bar',
                data: data.distribution.map((item) => item.value),
                itemStyle: { color: '#4f46e5', borderRadius: [0, 5, 5, 0] },
              },
            ],
          },
    [data.distribution, kind],
  );
  if (data.distribution.length === 0)
    return <EmptyState message="Nu există distribuție pentru scope-ul curent." />;
  return (
    <div className="chart-widget">
      <ChartToggle options={choices} value={kind} onChange={setKind} />
      <EChart option={option} className="chart--fill" ariaLabel={`Distribuție ${data.title}`} />
    </div>
  );
}

export function ModuleMatrixWidget() {
  const data = useModuleData();
  const xValues = useMemo(() => [...new Set(data.matrix.map((cell) => cell.x))], [data.matrix]);
  const yValues = useMemo(() => [...new Set(data.matrix.map((cell) => cell.y))], [data.matrix]);
  const values = data.matrix.map((cell) => cell.value);
  const minimum = values.length > 0 ? Math.min(...values) : 0;
  const maximum = values.length > 0 ? Math.max(...values) : 100;
  const option = useMemo<EChartsCoreOption>(
    () => ({
      animationDuration: 220,
      tooltip: { position: 'top' },
      grid: { top: 16, right: 16, bottom: 48, left: 104 },
      xAxis: {
        type: 'category',
        data: xValues,
        splitArea: { show: true },
        axisLabel: { color: '#64748b', fontSize: 9 },
      },
      yAxis: {
        type: 'category',
        data: yValues,
        splitArea: { show: true },
        axisLabel: { color: '#64748b', fontSize: 9, width: 94, overflow: 'truncate' },
      },
      visualMap: {
        min: minimum,
        max: maximum || 1,
        calculable: false,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        inRange: { color: ['#fff1f2', '#fef3c7', '#ccfbf1', '#c7d2fe'] },
        textStyle: { color: '#64748b', fontSize: 9 },
      },
      series: [
        {
          type: 'heatmap',
          data: data.matrix.map((cell) => [
            xValues.indexOf(cell.x),
            yValues.indexOf(cell.y),
            cell.value,
          ]),
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(15,23,42,.22)' } },
        },
      ],
    }),
    [data.matrix, maximum, minimum, xValues, yValues],
  );
  if (data.matrix.length === 0)
    return <EmptyState message="Matricea nu este disponibilă pentru scope-ul curent." />;
  return (
    <EChart option={option} className="chart--fill" ariaLabel={`Matrice temporală ${data.title}`} />
  );
}

function RiskBadge({ risk }: { risk: BreakdownRow['risk'] }) {
  const labels = { healthy: 'Sănătos', watch: 'Atenție', risk: 'Risc' } as const;
  return <span className={`risk-badge risk-badge--${risk}`}>{labels[risk]}</span>;
}

export function ModuleBreakdownWidget() {
  const data = useModuleData();
  const [sorting, setSorting] = useState<SortingState>([{ id: 'primary', desc: true }]);
  const axes = data.axes;
  const columns = useMemo<ColumnDef<BreakdownRow>[]>(
    () => [
      {
        accessorKey: 'label',
        header: 'Entitate',
        cell: ({ row }) => (
          <div className="entity-cell">
            <div>
              <strong>{row.original.label}</strong>
              <span>{row.original.context}</span>
            </div>
          </div>
        ),
      },
      {
        accessorKey: 'primary',
        header: axes[0]?.label ?? 'Principal',
        cell: ({ getValue }) => formatValue(Number(getValue()), axes[0]?.unit ?? 'decimal', true),
      },
      {
        accessorKey: 'secondary',
        header: axes[1]?.label ?? 'Secundar',
        cell: ({ getValue }) =>
          formatValue(getValue<number | null>(), axes[1]?.unit ?? 'decimal', true),
      },
      {
        accessorKey: 'tertiary',
        header: axes[2]?.label ?? 'Tertiar',
        cell: ({ getValue }) =>
          formatValue(getValue<number | null>(), axes[2]?.unit ?? 'decimal', true),
      },
      {
        accessorKey: 'progress_pct',
        header: 'Progres',
        cell: ({ getValue }) => formatPercent(getValue<number | null>()),
      },
      {
        accessorKey: 'risk',
        header: 'Status',
        cell: ({ getValue }) => <RiskBadge risk={getValue<BreakdownRow['risk']>()} />,
      },
    ],
    [axes],
  );
  const table = useReactTable({
    data: data.breakdown,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  if (data.breakdown.length === 0)
    return <EmptyState message="Nu există entități pentru scope-ul curent." />;
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id}>
              {group.headers.map((header) => (
                <th key={header.id}>
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

export function ModuleAlertsWidget() {
  const { alerts } = useModuleData();
  const icons = { info: CheckCircle2, warning: TriangleAlert, critical: AlertCircle } as const;
  if (alerts.length === 0) return <EmptyState message="Nu există alerte pentru scope-ul curent." />;
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
