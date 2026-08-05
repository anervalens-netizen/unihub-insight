import {
  BarChart,
  BoxplotChart,
  HeatmapChart,
  LineChart,
  PieChart,
  ScatterChart,
  TreemapChart,
} from 'echarts/charts';
import {
  AriaComponent,
  CalendarComponent,
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
import type { ChartPngExportConfig } from './chart-spec';

echarts.use([
  AriaComponent,
  BarChart,
  BoxplotChart,
  CalendarComponent,
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
  TreemapChart,
  UniversalTransition,
  VisualMapComponent,
]);

export type EChartEvent = {
  data?: unknown;
  dataIndex?: number;
  name?: string;
};

function safeFilename(value: string): string {
  const normalized = value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9._-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 96);
  return `${normalized || 'chart'}.png`;
}

function downloadChartPng(chart: EChartsType, exportConfig: ChartPngExportConfig): void {
  const url = chart.getDataURL({
    type: 'png',
    pixelRatio: exportConfig.pixelRatio,
    backgroundColor: 'transparent',
  });
  const link = document.createElement('a');
  link.href = url;
  link.download = safeFilename(exportConfig.filename);
  link.click();
}

export function EChart({
  option,
  className = '',
  ariaLabel,
  onEvent,
  onDoubleEvent,
  onBlankReset,
  pngExport,
}: {
  option: EChartsCoreOption;
  className?: string;
  ariaLabel: string;
  onEvent?: (event: EChartEvent) => void;
  onDoubleEvent?: (event: EChartEvent) => void;
  onBlankReset?: () => void;
  pngExport?: ChartPngExportConfig;
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
    const resizeObserver = new ResizeObserver(() => {
      if (!chart.isDisposed()) chart.resize({ animation: { duration: 120 } });
    });
    resizeObserver.observe(host);
    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onEvent) return;
    const handleClick = (event: EChartEvent) => onEvent(event);
    chart.on('click', handleClick);
    return () => {
      if (!chart.isDisposed()) chart.off('click', handleClick);
    };
  }, [onEvent]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onDoubleEvent) return;
    const handleDoubleClick = (event: EChartEvent) => onDoubleEvent(event);
    chart.on('dblclick', handleDoubleClick);
    return () => {
      if (!chart.isDisposed()) chart.off('dblclick', handleDoubleClick);
    };
  }, [onDoubleEvent]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onBlankReset) return;
    const handleBlankClick = (event: { target?: unknown }) => {
      if (!event.target) onBlankReset();
    };
    const renderer = chart.getZr();
    renderer.on('click', handleBlankClick);
    return () => {
      if (!chart.isDisposed()) renderer.off('click', handleBlankClick);
    };
  }, [onBlankReset]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || chart.isDisposed()) return;
    chart.setOption(designedOption, {
      notMerge: true,
      lazyUpdate: true,
      silent: false,
    });
  }, [designedOption]);

  return (
    <div className="chart-host">
      <div
        ref={hostRef}
        className={`chart ${className}`}
        role="img"
        aria-label={ariaLabel}
        data-chart-palette={design.paletteName}
        data-chart-theme={design.theme}
      />
      {pngExport ? (
        <button
          type="button"
          className="chart-export-button"
          aria-label={`Descarcă PNG pentru ${ariaLabel}`}
          title="Descarcă PNG"
          onClick={() => {
            if (chartRef.current) downloadChartPng(chartRef.current, pngExport);
          }}
        >
          PNG
        </button>
      ) : null}
    </div>
  );
}
