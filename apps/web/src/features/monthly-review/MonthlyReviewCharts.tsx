import type { EChartsCoreOption } from 'echarts/core';
import { useMemo, useState } from 'react';

import { EChart } from '../../components/charts/EChart';
import {
  ChartTypeSelector,
  type ProfessionalChartType,
} from '../../components/charts/ChartTypeSelector';
import { useChartDesign } from '../../components/charts/chart-design';
import { EmptyState } from '../../components/ui/EmptyState';
import { formatCurrency } from '../../lib/format';
import type { MonthlyReview } from './schemas';

const trendTypes = ['line', 'area', 'bar'] as const satisfies readonly ProfessionalChartType[];
const driverTypes = ['bar', 'waterfall'] as const satisfies readonly ProfessionalChartType[];

export function MonthlyTrendChart({ data }: { data: MonthlyReview }) {
  const design = useChartDesign();
  const [type, setType] = useState<(typeof trendTypes)[number]>('area');
  const option = useMemo<EChartsCoreOption>(() => {
    const salesSeries =
      type === 'bar'
        ? {
            id: 'monthly-sales',
            type: 'bar' as const,
            name: 'Vânzări',
            data: data.trend.map((point) => point.sales),
            itemStyle: { color: design.primary },
          }
        : {
            id: 'monthly-sales',
            type: 'line' as const,
            name: 'Vânzări',
            data: data.trend.map((point) => point.sales),
            showSymbol: false,
            smooth: design.preferences.smoothLines ? 0.16 : false,
            lineStyle: { width: 3, color: design.primary },
            itemStyle: { color: design.primary },
            ...(type === 'area' ? { areaStyle: { color: design.areaPrimary } } : {}),
          };
    return {
      grid: { top: 44, right: 22, bottom: 36, left: 66 },
      tooltip: { trigger: 'axis' },
      legend: { top: 0, right: 0 },
      xAxis: {
        type: 'category',
        boundaryGap: type === 'bar',
        data: data.trend.map((point) => point.period),
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: string | number) => formatCurrency(Number(value), true),
        },
      },
      series: [
        salesSeries,
        {
          id: 'monthly-target',
          type: 'line',
          name: 'Target',
          data: data.trend.map((point) => point.target),
          showSymbol: false,
          lineStyle: { width: 2, type: 'dashed', color: design.positive },
          itemStyle: { color: design.positive },
        },
      ],
    };
  }, [data.trend, design, type]);

  if (data.trend.length === 0) return <EmptyState message="Nu există trend lunar în scope." />;
  return (
    <div className="chart-widget">
      <ChartTypeSelector
        value={type}
        options={trendTypes}
        onChange={setType}
        label="Tip grafic evoluție lunară"
      />
      <EChart option={option} className="chart--fill" ariaLabel="Evoluție lunară" />
    </div>
  );
}

interface WaterfallPoint {
  label: string;
  value: number;
  helper: number;
  positive: number | null;
  negative: number | null;
}

function waterfallPoints(values: Array<{ label: string; value: number }>): WaterfallPoint[] {
  let cumulative = 0;
  return values.map(({ label, value }) => {
    const helper = value >= 0 ? cumulative : cumulative + value;
    cumulative += value;
    return {
      label,
      value,
      helper,
      positive: value >= 0 ? value : null,
      negative: value < 0 ? Math.abs(value) : null,
    };
  });
}

export function MonthlyDriverChart({ data }: { data: MonthlyReview }) {
  const design = useChartDesign();
  const [type, setType] = useState<(typeof driverTypes)[number]>('waterfall');
  const driver = data.drivers[0];
  const values = useMemo(
    () =>
      driver
        ? [
            { label: 'Bonuri', value: driver.receipts_effect },
            { label: 'Produse / bon', value: driver.units_per_receipt_effect },
            { label: 'Valoare / produs', value: driver.value_per_unit_effect },
          ]
        : [],
    [driver],
  );
  const option = useMemo<EChartsCoreOption>(() => {
    if (type === 'bar') {
      return {
        grid: { top: 44, right: 16, bottom: 48, left: 66 },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: { type: 'category', data: values.map((item) => item.label) },
        yAxis: {
          type: 'value',
          axisLabel: {
            formatter: (value: string | number) => formatCurrency(Number(value), true),
          },
        },
        series: [
          {
            id: 'driver-bars',
            type: 'bar',
            data: values.map((item) => ({
              value: item.value,
              itemStyle: { color: item.value < 0 ? design.negative : design.positive },
            })),
            label: {
              show: design.preferences.showLabels,
              formatter: (params: { value?: unknown }) =>
                typeof params.value === 'number' ? formatCurrency(params.value, true) : '',
            },
          },
        ],
      };
    }
    const points = waterfallPoints(values);
    return {
      grid: { top: 44, right: 16, bottom: 48, left: 66 },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        valueFormatter: (value: unknown) =>
          typeof value === 'number' ? formatCurrency(value, true) : '—',
      },
      legend: { show: false },
      xAxis: { type: 'category', data: points.map((item) => item.label) },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: string | number) => formatCurrency(Number(value), true),
        },
      },
      series: [
        {
          id: 'waterfall-helper',
          type: 'bar',
          stack: 'driver',
          silent: true,
          data: points.map((item) => item.helper),
          itemStyle: { color: 'rgba(0,0,0,0)' },
          emphasis: { disabled: true },
        },
        {
          id: 'waterfall-positive',
          type: 'bar',
          stack: 'driver',
          name: 'Impact pozitiv',
          data: points.map((item) => item.positive),
          itemStyle: { color: design.positive },
          label: {
            show: true,
            position: 'top',
            formatter: (params: { dataIndex?: number }) => {
              const point = points[params.dataIndex ?? -1];
              return point ? formatCurrency(point.value, true) : '';
            },
          },
        },
        {
          id: 'waterfall-negative',
          type: 'bar',
          stack: 'driver',
          name: 'Impact negativ',
          data: points.map((item) => item.negative),
          itemStyle: { color: design.negative },
          label: {
            show: true,
            position: 'bottom',
            formatter: (params: { dataIndex?: number }) => {
              const point = points[params.dataIndex ?? -1];
              return point ? formatCurrency(point.value, true) : '';
            },
          },
        },
      ],
    };
  }, [design, type, values]);

  if (!driver) return <EmptyState message="Driverii diferenței nu sunt disponibili." />;
  return (
    <div className="chart-widget">
      <ChartTypeSelector
        value={type}
        options={driverTypes}
        onChange={setType}
        label="Tip grafic driveri"
      />
      <EChart option={option} className="chart--fill" ariaLabel="Driverii diferenței" />
    </div>
  );
}
