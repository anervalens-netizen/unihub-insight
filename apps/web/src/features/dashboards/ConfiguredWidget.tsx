import type { EChartsCoreOption } from 'echarts/core';
import { useMemo } from 'react';

import { EChart } from '../../components/charts/EChart';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatCurrency, formatInteger, formatPercent } from '../../lib/format';
import type { ModuleAnalytics } from '../modules/schemas';
import type { DashboardWidget } from './schemas';

function format(value: number, unit: string): string {
  if (unit === 'currency') return formatCurrency(value, true);
  if (unit === 'percent') return formatPercent(value);
  if (unit === 'integer') return formatInteger(value);
  return value.toLocaleString('ro-RO', { maximumFractionDigits: 2 });
}

function ConfiguredChart({ widget, data }: { widget: DashboardWidget; data: ModuleAnalytics }) {
  const option = useMemo<EChartsCoreOption>(() => {
    if (widget.visualization === 'donut') return { tooltip: { trigger: 'item' }, legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 10 } }, series: [{ type: 'pie', radius: ['48%', '72%'], center: ['50%', '43%'], label: { show: false }, data: data.distribution.map((row) => ({ name: row.label, value: row.value })) }] };
    if (widget.visualization === 'waterfall') return { grid: { top: 12, right: 12, bottom: 40, left: 55 }, tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: data.distribution.map((row) => row.label), axisLabel: { rotate: 25, fontSize: 9 } }, yAxis: { type: 'value' }, series: [{ type: 'bar', data: data.distribution.map((row) => row.value), itemStyle: { color: '#4f46e5' } }] };
    if (widget.visualization === 'heatmap') {
      const x = [...new Set(data.matrix.map((cell) => cell.x))];
      const y = [...new Set(data.matrix.map((cell) => cell.y))];
      const values = data.matrix.map((cell) => cell.value);
      return { tooltip: { position: 'top' }, grid: { top: 12, right: 12, bottom: 44, left: 95 }, xAxis: { type: 'category', data: x }, yAxis: { type: 'category', data: y, axisLabel: { width: 86, overflow: 'truncate' } }, visualMap: { min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 100, orient: 'horizontal', left: 'center', bottom: 0, inRange: { color: ['#fff1f2', '#fef3c7', '#ccfbf1', '#c7d2fe'] } }, series: [{ type: 'heatmap', data: data.matrix.map((cell) => [x.indexOf(cell.x), y.indexOf(cell.y), cell.value]) }] };
    }
    if (widget.visualization === 'scatter') return { grid: { top: 16, right: 18, bottom: 36, left: 58 }, tooltip: { trigger: 'item' }, xAxis: { type: 'value', name: data.axes[0]?.label }, yAxis: { type: 'value', name: data.axes[1]?.label }, series: [{ type: 'scatter', symbolSize: 10, data: data.breakdown.filter((row) => row.secondary !== null && row.secondary !== undefined).map((row) => [row.primary, row.secondary, row.label]) }] };
    const chartType = widget.visualization === 'bar' ? 'bar' : 'line';
    return { grid: { top: 18, right: 16, bottom: 36, left: 58 }, tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: data.trend.map((row) => row.label) }, yAxis: { type: 'value' }, series: [{ type: chartType, data: data.trend.map((row) => row.primary), showSymbol: false, smooth: 0.15, itemStyle: { color: '#4f46e5' }, lineStyle: { color: '#4f46e5', width: 2 }, ...(widget.visualization === 'area' ? { areaStyle: { color: 'rgba(79,70,229,.12)' } } : {}) }, { type: 'line', data: data.trend.map((row) => row.target), showSymbol: false, lineStyle: { color: '#0f766e', type: 'dashed' } }] };
  }, [data, widget.visualization]);
  return <div className="configured-chart"><span className="widget-filter-mode">{widget.filter_mode}</span><EChart option={option} className="chart--fill" ariaLabel={widget.title} /></div>;
}

export function ConfiguredWidget({ widget, data }: { widget: DashboardWidget; data: ModuleAnalytics | undefined }) {
  if (!data) return <EmptyState message="Modulul nu este disponibil pentru permisiunile sau scope-ul curent." />;
  const metric = data.kpis.find((item) => item.id === widget.metric_id) ?? data.kpis[0];
  if (widget.visualization === 'kpi') {
    if (!metric) return <EmptyState message="Metrica configurată nu este disponibilă." />;
    return <div className="configured-kpi"><strong>{format(metric.value, metric.unit)}</strong><span>{metric.label}</span><small className={`risk-badge risk-badge--${metric.risk}`}>{metric.supporting_label ?? data.meta.scope_label}</small><em>Filtru local: {widget.filter_mode}</em></div>;
  }
  if (widget.visualization === 'table') return <div className="table-scroll"><table className="data-table"><thead><tr><th>Entitate</th><th>{data.axes[0]?.label ?? 'Principal'}</th><th>Progres</th><th>Status</th></tr></thead><tbody>{data.breakdown.map((row) => <tr key={row.id}><td>{row.label}<small className="table-context">{row.context}</small></td><td>{format(row.primary, data.axes[0]?.unit ?? 'decimal')}</td><td>{formatPercent(row.progress_pct)}</td><td><span className={`risk-badge risk-badge--${row.risk}`}>{row.risk}</span></td></tr>)}</tbody></table></div>;
  return <ConfiguredChart widget={widget} data={data} />;
}
