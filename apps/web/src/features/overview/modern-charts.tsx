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
import { useOverviewData } from './context';

const trendTypes = ['line', 'area', 'bar'] as const satisfies readonly ProfessionalChartType[];
const contributionTypes = ['donut', 'bar'] as const satisfies readonly ProfessionalChartType[];

export function ModernSalesTrendWidget() {
  const { daily, meta } = useOverviewData();
  const design = useChartDesign();
  const [type, setType] = useState<(typeof trendTypes)[number]>('area');
  const option = useMemo<EChartsCoreOption>(() => {
    const primarySeries =
      type === 'bar'
        ? {
            id: 'sales',
            type: 'bar' as const,
            name: 'Realizat',
            data: daily.map((point) => point.sales),
            itemStyle: { color: design.primary },
          }
        : {
            id: 'sales',
            type: 'line' as const,
            name: 'Realizat',
            data: daily.map((point) => point.sales),
            showSymbol: false,
            connectNulls: false,
            smooth: design.preferences.smoothLines ? 0.16 : false,
            lineStyle: { width: 3, color: design.primary },
            itemStyle: { color: design.primary },
            ...(type === 'area' ? { areaStyle: { color: design.areaPrimary } } : {}),
          };
    return {
      animationDuration: 280,
      aria: {
        enabled: true,
        description: `Evoluția cumulată a vânzărilor pentru ${meta.period}.`,
      },
      grid: { top: 44, right: 18, bottom: 34, left: 58 },
      tooltip: {
        trigger: 'axis',
        valueFormatter: (value: unknown) =>
          typeof value === 'number' ? formatCurrency(value) : '—',
      },
      legend: { top: 0, right: 0, icon: 'roundRect' },
      xAxis: {
        type: 'category',
        data: daily.map((point) => point.day),
        boundaryGap: type === 'bar',
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLabel: {
          formatter: (value: string | number) => formatCurrency(Number(value), true),
        },
      },
      series: [
        primarySeries,
        {
          id: 'target',
          type: 'line',
          name: 'Target pace',
          data: daily.map((point) => point.target_pace),
          showSymbol: false,
          lineStyle: { width: 2, color: design.positive, type: 'dashed' },
          itemStyle: { color: design.positive },
        },
        {
          id: 'forecast',
          type: 'line',
          name: 'Forecast',
          data: daily.map((point) => point.forecast ?? null),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2, color: design.warning, type: 'dotted' },
          itemStyle: { color: design.warning },
        },
        {
          id: 'comparison',
          type: 'line',
          name: meta.comparison === 'previous-year' ? 'Anul trecut' : 'Luna precedentă',
          data: daily.map((point) => point.comparison ?? null),
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 1.5, color: design.subtle },
          itemStyle: { color: design.subtle },
        },
      ],
    };
  }, [daily, design, meta.comparison, meta.period, type]);

  if (daily.length === 0) return <EmptyState message="Nu există date zilnice pentru scope." />;
  return (
    <div className="chart-widget">
      <ChartTypeSelector
        value={type}
        options={trendTypes}
        onChange={setType}
        label="Tip grafic pace comercială"
      />
      <EChart
        option={option}
        className="chart--fill"
        ariaLabel={`Pace comercială pentru ${meta.period}`}
      />
    </div>
  );
}

export function ModernContributionWidget() {
  const { contribution } = useOverviewData();
  const design = useChartDesign();
  const [type, setType] = useState<(typeof contributionTypes)[number]>('donut');
  const option = useMemo<EChartsCoreOption>(() => {
    if (type === 'bar') {
      return {
        grid: { top: 42, right: 18, bottom: 28, left: 94 },
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: {
          type: 'value',
          axisLabel: {
            formatter: (value: string | number) => formatCurrency(Number(value), true),
          },
        },
        yAxis: {
          type: 'category',
          inverse: true,
          data: contribution.map((item) => item.label),
        },
        series: [
          {
            id: 'contribution',
            type: 'bar',
            data: contribution.map((item) => item.value),
            itemStyle: { color: design.primary },
            label: {
              show: design.preferences.showLabels,
              position: 'right',
              formatter: (params: { value?: unknown }) =>
                typeof params.value === 'number' ? formatCurrency(params.value, true) : '',
            },
          },
        ],
      };
    }
    return {
      tooltip: {
        trigger: 'item',
        formatter: '{b}<br/>{c} RON · {d}%',
      },
      legend: { bottom: 0, left: 'center' },
      series: [
        {
          id: 'contribution',
          type: 'pie',
          radius: ['54%', '78%'],
          center: ['50%', '43%'],
          avoidLabelOverlap: true,
          label: {
            show: design.preferences.showLabels,
            formatter: '{b}\n{d}%',
          },
          emphasis: {
            scale: true,
            scaleSize: 8,
            label: { show: true, fontSize: 13, fontWeight: 750 },
          },
          data: contribution.map((item) => ({ name: item.label, value: item.value })),
        },
      ],
    };
  }, [contribution, design, type]);

  if (contribution.length === 0)
    return <EmptyState message="Nu există contribuții pentru filtrarea curentă." />;
  return (
    <div className="chart-widget">
      <ChartTypeSelector
        value={type}
        options={contributionTypes}
        onChange={setType}
        label="Tip grafic contribuție"
      />
      <EChart option={option} className="chart--fill" ariaLabel="Contribuția firmelor" />
    </div>
  );
}
