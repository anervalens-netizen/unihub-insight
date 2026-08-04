import { BarChart, LineChart, PieChart } from 'echarts/charts';
import {
  AriaComponent,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import type { EChartsCoreOption, EChartsType } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

echarts.use([
  AriaComponent,
  BarChart,
  CanvasRenderer,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
]);

export function EChart({
  option,
  className = '',
  ariaLabel,
}: {
  option: EChartsCoreOption;
  className?: string;
  ariaLabel: string;
}) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<EChartsType | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const chart = echarts.init(host, undefined, {
      renderer: 'canvas',
      useDirtyRect: true,
    });
    chartRef.current = chart;

    const resizeObserver = new ResizeObserver(() => chart.resize());
    resizeObserver.observe(host);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, {
      notMerge: true,
      lazyUpdate: true,
    });
  }, [option]);

  return <div ref={hostRef} className={`chart ${className}`} role="img" aria-label={ariaLabel} />;
}
