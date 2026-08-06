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
import { type KeyboardEvent, useEffect, useMemo, useRef } from 'react';
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

function chartDataCount(option: EChartsCoreOption): number {
  const record = typeof option === 'object' && option !== null ? option : {};
  const datasetValue = (record as Record<string, unknown>)['dataset'];
  const dataset = Array.isArray(datasetValue) ? datasetValue[0] : datasetValue;
  if (typeof dataset === 'object' && dataset !== null) {
    const source = (dataset as Record<string, unknown>)['source'];
    if (Array.isArray(source)) return source.length;
  }
  const series = (record as Record<string, unknown>)['series'];
  const firstSeries = Array.isArray(series) ? series[0] : series;
  if (typeof firstSeries === 'object' && firstSeries !== null) {
    const data = (firstSeries as Record<string, unknown>)['data'];
    if (Array.isArray(data)) return data.length;
  }
  return 0;
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
  const keyboardIndexRef = useRef(-1);
  const design = useChartDesign();
  const rawDataCount = useMemo(() => chartDataCount(option), [option]);
  const designedOption = useMemo(() => {
    const designed = applyChartDesign(option, design);
    return rawDataCount > 2000
      ? ({
          ...designed,
          animation: false,
          animationDuration: 0,
          animationDurationUpdate: 0,
        } as EChartsCoreOption)
      : designed;
  }, [design, option, rawDataCount]);
  const dataCount = useMemo(() => chartDataCount(designedOption), [designedOption]);
  const interactive = Boolean(onEvent || onBlankReset);

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
    let resizeFrame = 0;
    let resizeTimer = 0;
    const resizeObserver = new ResizeObserver(() => {
      window.clearTimeout(resizeTimer);
      cancelAnimationFrame(resizeFrame);
      resizeTimer = window.setTimeout(() => {
        resizeFrame = requestAnimationFrame(() => {
          if (!chart.isDisposed()) chart.resize({ animation: { duration: 0 } });
        });
      }, 120);
    });
    resizeObserver.observe(host);
    return () => {
      resizeObserver.disconnect();
      window.clearTimeout(resizeTimer);
      cancelAnimationFrame(resizeFrame);
      chartRef.current = null;
      if (!chart.isDisposed()) {
        chart.clear();
        chart.dispose();
      }
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
      lazyUpdate: false,
      silent: false,
    });
    keyboardIndexRef.current = -1;
  }, [designedOption]);

  const handleKeyboard = (event: KeyboardEvent<HTMLDivElement>): void => {
    const chart = chartRef.current;
    if (!chart || chart.isDisposed()) return;
    if (event.key === 'Escape' && onBlankReset) {
      event.preventDefault();
      onBlankReset();
      return;
    }
    const count = dataCount;
    if (count === 0) return;
    if (['ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const direction = event.key === 'ArrowLeft' || event.key === 'ArrowUp' ? -1 : 1;
      const previous = keyboardIndexRef.current;
      const current = previous < 0 ? 0 : (previous + direction + count) % count;
      if (previous >= 0)
        chart.dispatchAction({ type: 'downplay', seriesIndex: 0, dataIndex: previous });
      keyboardIndexRef.current = current;
      chart.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex: current });
      chart.dispatchAction({ type: 'showTip', seriesIndex: 0, dataIndex: current });
      return;
    }
    if ((event.key === 'Enter' || event.key === ' ') && onEvent) {
      event.preventDefault();
      const current = keyboardIndexRef.current < 0 ? 0 : keyboardIndexRef.current;
      keyboardIndexRef.current = current;
      onEvent({ dataIndex: current });
    }
  };

  const interactionProps = interactive
    ? {
        role: 'application' as const,
        tabIndex: 0,
        onKeyDown: handleKeyboard,
        'aria-label': ariaLabel,
        'aria-roledescription': 'grafic interactiv',
      }
    : {};

  return (
    <div className="chart-host" {...interactionProps}>
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
