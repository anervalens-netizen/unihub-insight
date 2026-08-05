import { BarChart, HeatmapChart, LineChart, PieChart, ScatterChart } from 'echarts/charts';
import {
  AriaComponent,
  DatasetComponent,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import type { EChartsCoreOption, EChartsType } from 'echarts/core';
import * as echarts from 'echarts/core';
import { UniversalTransition } from 'echarts/features';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useMemo, useRef } from 'react';

import { applyChartDesign, useChartDesign } from './chart-design';

echarts.use([
  AriaComponent,
  BarChart,
  CanvasRenderer,
  DataZoomComponent,
  DatasetComponent,
  GridComponent,
  HeatmapChart,
  LegendComponent,
  LineChart,
  PieChart,
  ScatterChart,
  TitleComponent,
  ToolboxComponent,
  TooltipComponent,
  UniversalTransition,
  VisualMapComponent,
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
  const design = useChartDesign();
  const designedOption = useMemo(() => applyChartDesign(option, design), [design, option]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = echarts.init(host, undefined, {
      renderer: 'canvas',
      useDirtyRect: true,
      useCoarsePointer: true,
      pointerSize: 28,
      devicePixelRatio: Math.min(window.devicePixelRatio, 2),
      locale: 'EN',
    });
    chartRef.current = chart;
    const resizeObserver = new ResizeObserver(() => chart.resize({ animation: { duration: 120 } }));
    resizeObserver.observe(host);
    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(designedOption, {
      notMerge: true,
      lazyUpdate: true,
      silent: false,
    });
  }, [designedOption]);

  return (
    <div
      ref={hostRef}
      className={`chart ${className}`}
      role="img"
      aria-label={ariaLabel}
      data-chart-palette={design.paletteName}
      data-chart-theme={design.theme}
    />
  );
}
