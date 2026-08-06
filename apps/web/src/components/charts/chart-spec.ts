import type { EChartsCoreOption } from 'echarts/core';
import type { ChartKind } from '../../features/modules/schemas';
import type {
  DatasetDimension,
  DatasetValue,
  MetricDefinition,
  QueryDataset,
} from '../../features/query/schemas';

export type ChartRenderer = 'canvas';

export interface ChartSpec {
  readonly shape: Exclude<ChartKind, 'kpi' | 'table'>;
  readonly renderer: ChartRenderer;
  readonly requiredDimensionKinds: readonly DatasetDimension['kind'][];
}

export interface BuiltChartSpec {
  readonly kind: 'chart';
  readonly shape: ChartSpec['shape'];
  readonly renderer: ChartRenderer;
  readonly option: EChartsCoreOption;
}

export interface TableFallbackSpec {
  readonly kind: 'table';
  readonly requestedShape: ChartKind;
  readonly reason: string;
}

export type ResolvedChartSpec = BuiltChartSpec | TableFallbackSpec;

export interface WidgetChartOptions {
  show_legend?: boolean | undefined;
  show_labels?: boolean | undefined;
  top_n?: number | undefined;
  renderer?: 'canvas' | undefined;
  smooth?: boolean | undefined;
  stacked?: boolean | undefined;
  pixel_ratio?: 1 | 2 | undefined;
}

export interface ChartUrlStateEvent {
  readonly dimensionId: string;
  readonly value: string;
  readonly label: string | null;
}

const chartSpecRegistry: Partial<Record<ChartKind, ChartSpec>> = {
  line: { shape: 'line', renderer: 'canvas', requiredDimensionKinds: ['string', 'time'] },
  area: { shape: 'area', renderer: 'canvas', requiredDimensionKinds: ['string', 'time'] },
  bar: { shape: 'bar', renderer: 'canvas', requiredDimensionKinds: ['string', 'time'] },
  'stacked-bar': {
    shape: 'stacked-bar',
    renderer: 'canvas',
    requiredDimensionKinds: ['string', 'time'],
  },
  donut: { shape: 'donut', renderer: 'canvas', requiredDimensionKinds: ['string'] },
  heatmap: { shape: 'heatmap', renderer: 'canvas', requiredDimensionKinds: ['string', 'time'] },
  scatter: { shape: 'scatter', renderer: 'canvas', requiredDimensionKinds: ['number', 'integer'] },
  waterfall: {
    shape: 'waterfall',
    renderer: 'canvas',
    requiredDimensionKinds: ['string', 'number'],
  },
  histogram: { shape: 'histogram', renderer: 'canvas', requiredDimensionKinds: ['number'] },
  boxplot: { shape: 'boxplot', renderer: 'canvas', requiredDimensionKinds: ['number'] },
  treemap: { shape: 'treemap', renderer: 'canvas', requiredDimensionKinds: ['string', 'number'] },
  calendar: { shape: 'calendar', renderer: 'canvas', requiredDimensionKinds: ['time', 'number'] },
  'forecast-band': {
    shape: 'forecast-band',
    renderer: 'canvas',
    requiredDimensionKinds: ['time', 'number'],
  },
};

export { chartSpecRegistry };

export function applyWidgetChartOptions(
  option: EChartsCoreOption,
  shape: ChartKind,
  options: WidgetChartOptions,
): EChartsCoreOption {
  const record = isRecord(option) ? option : {};
  const legend = isRecord(record['legend']) ? record['legend'] : {};
  const series = Array.isArray(record['series'])
    ? record['series'].map((entry) => {
        if (!isRecord(entry)) return entry;
        const next = { ...entry };
        if (typeof options.show_labels === 'boolean') {
          next['label'] = {
            ...(isRecord(entry['label']) ? entry['label'] : {}),
            show: options.show_labels,
          };
        }
        if (
          typeof options.smooth === 'boolean' &&
          (shape === 'line' || shape === 'area') &&
          entry['type'] === 'line'
        ) {
          next['smooth'] = options.smooth;
        }
        if (typeof options.stacked === 'boolean' && shape === 'bar' && entry['type'] === 'bar') {
          next['stack'] = options.stacked ? 'value' : undefined;
        }
        return next;
      })
    : record['series'];
  return {
    ...record,
    ...(typeof options.show_legend === 'boolean'
      ? { legend: { ...legend, show: options.show_legend } }
      : {}),
    ...(series ? { series } : {}),
  } as EChartsCoreOption;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function valueDimension(dataset: QueryDataset): DatasetDimension | undefined {
  return (
    dataset.dimensions.find((dimension) => dimension.role === 'value') ??
    dataset.dimensions.find(
      (dimension) => dimension.kind === 'number' || dimension.kind === 'integer',
    )
  );
}

function categoryDimension(dataset: QueryDataset): DatasetDimension | undefined {
  return (
    dataset.dimensions.find((dimension) => dimension.role === 'label') ??
    dataset.dimensions.find((dimension) => dimension.role === 'key') ??
    dataset.dimensions.find((dimension) => dimension.kind === 'string' || dimension.kind === 'time')
  );
}

function dimensionByRole(dataset: QueryDataset, role: DatasetDimension['role']) {
  return dataset.dimensions.find((dimension) => dimension.role === role);
}

function sourceFor(dataset: QueryDataset) {
  return {
    dimensions: dataset.dimensions.map((dimension) => dimension.id),
    source: dataset.rows,
  };
}

function baseOption(dataset: QueryDataset, tooltipTrigger: 'axis' | 'item' = 'axis') {
  return {
    dataset: sourceFor(dataset),
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: tooltipTrigger, confine: true },
    animation: false,
    grid: { top: 22, right: 18, bottom: 42, left: 58, containLabel: true },
  };
}

function lineOption(
  dataset: QueryDataset,
  metric: MetricDefinition,
  shape: 'line' | 'area' | 'bar' | 'stacked-bar',
): EChartsCoreOption | null {
  const category = categoryDimension(dataset);
  const value = valueDimension(dataset);
  if (!category || !value) return null;
  const comparisons = dataset.dimensions.filter((dimension) => dimension.role === 'comparison');
  const target = dimensionByRole(dataset, 'target');
  const type = shape === 'bar' || shape === 'stacked-bar' ? 'bar' : 'line';
  const series: Array<Record<string, unknown>> = [
    {
      type,
      name: metric.display_name,
      encode: { x: category.id, y: value.id, tooltip: [category.id, value.id] },
      connectNulls: false,
      ...(shape === 'area' ? { areaStyle: {} } : {}),
      ...(shape === 'stacked-bar' ? { stack: 'value' } : {}),
    },
  ];
  for (const comparison of comparisons) {
    series.push({
      type: 'line',
      name: comparison.label,
      encode: { x: category.id, y: comparison.id, tooltip: [category.id, comparison.id] },
      connectNulls: false,
      showSymbol: false,
    });
  }
  if (target) {
    series.push({
      type: 'line',
      name: 'Target',
      encode: { x: category.id, y: target.id, tooltip: [category.id, target.id] },
      connectNulls: false,
      showSymbol: false,
    });
  }
  return {
    ...baseOption(dataset),
    xAxis: { type: 'category' },
    yAxis: { type: 'value' },
    ...(dataset.rows.length > 18
      ? {
          dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            { type: 'slider', height: 16 },
          ],
        }
      : {}),
    series,
  } as EChartsCoreOption;
}

function donutOption(dataset: QueryDataset, metric: MetricDefinition): EChartsCoreOption | null {
  const category = categoryDimension(dataset);
  const value = valueDimension(dataset);
  if (!category || !value) return null;
  return {
    ...baseOption(dataset, 'item'),
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        name: metric.display_name,
        radius: ['48%', '72%'],
        center: ['50%', '43%'],
        encode: { itemName: category.id, value: value.id, tooltip: [category.id, value.id] },
        label: { show: false },
      },
    ],
  } as EChartsCoreOption;
}

function heatmapOption(dataset: QueryDataset): EChartsCoreOption | null {
  const x = dataset.dimensions.find((dimension) => dimension.id === 'x');
  const y = dataset.dimensions.find((dimension) => dimension.id === 'y');
  const value = valueDimension(dataset);
  if (!x || !y || !value) return null;
  const values = finiteValues(dataset);
  if (values.length === 0) return null;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  return {
    ...baseOption(dataset, 'item'),
    xAxis: { type: 'category' },
    yAxis: { type: 'category' },
    visualMap: {
      min: minimum,
      max: maximum === minimum ? minimum + 1 : maximum,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    series: [
      {
        type: 'heatmap',
        encode: { x: x.id, y: y.id, value: value.id, tooltip: [x.id, y.id, value.id] },
        progressive: 1000,
        progressiveThreshold: 2000,
      },
    ],
  } as EChartsCoreOption;
}

function scatterOption(dataset: QueryDataset, metric: MetricDefinition): EChartsCoreOption | null {
  const x = dataset.dimensions.find(
    (dimension) =>
      dimension.id === 'x' && (dimension.kind === 'number' || dimension.kind === 'integer'),
  );
  const y = dataset.dimensions.find(
    (dimension) =>
      dimension.id === 'y' && (dimension.kind === 'number' || dimension.kind === 'integer'),
  );
  if (!x || !y || dataset.rows.length === 0) return null;
  const label = categoryDimension(dataset);
  return {
    ...baseOption(dataset, 'item'),
    xAxis: { type: 'value', name: x.label },
    yAxis: { type: 'value', name: y.label },
    series: [
      {
        type: 'scatter',
        name: metric.display_name,
        symbolSize: 10,
        large: dataset.rows.length > 2000,
        largeThreshold: 2000,
        progressive: 1000,
        progressiveThreshold: 2000,
        encode: {
          x: x.id,
          y: y.id,
          ...(label ? { itemName: label.id, tooltip: [label.id, x.id, y.id] } : {}),
        },
      },
    ],
  } as EChartsCoreOption;
}

function finiteValues(dataset: QueryDataset): number[] {
  const value = valueDimension(dataset);
  if (!value) return [];
  return dataset.rows
    .map((row) => row[value.id])
    .filter((item): item is number => typeof item === 'number' && Number.isFinite(item));
}

function numericCell(row: QueryDataset['rows'][number], dimensionId: string): number | null {
  const value = row[dimensionId];
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function waterfallOption(
  dataset: QueryDataset,
  metric: MetricDefinition,
): EChartsCoreOption | null {
  const category = categoryDimension(dataset);
  const value = valueDimension(dataset);
  const stepKind = dataset.dimensions.find((dimension) => dimension.id === 'step_kind');
  if (!category || !value || !stepKind) return null;
  const rows = dataset.rows
    .map((row) => ({
      label: String(row[category.id] ?? ''),
      value: Number(row[value.id]),
      kind: String(row[stepKind.id] ?? ''),
    }))
    .filter((row) => row.label && Number.isFinite(row.value));
  if (rows.length < 3 || rows[0]?.kind !== 'start' || rows.at(-1)?.kind !== 'total') return null;
  const start = rows[0]?.value ?? 0;
  const total = rows.at(-1)?.value ?? 0;
  const deltas = rows.slice(1, -1);
  if (deltas.some((row) => row.kind !== 'delta')) return null;
  const reconciled = start + deltas.reduce((sum, row) => sum + row.value, 0);
  const tolerance = Math.max(0.01, Math.abs(total) * 0.000001);
  if (Math.abs(reconciled - total) > tolerance) return null;
  let running = start;
  const helper: number[] = [];
  const positive: Array<number | '-'> = [];
  const negative: Array<number | '-'> = [];
  for (const [index, row] of rows.entries()) {
    if (index === 0 || index === rows.length - 1) {
      helper.push(0);
      positive.push(row.value >= 0 ? row.value : '-');
      negative.push(row.value < 0 ? Math.abs(row.value) : '-');
      continue;
    }
    const next = running + row.value;
    helper.push(Math.min(running, next));
    positive.push(row.value >= 0 ? row.value : '-');
    negative.push(row.value < 0 ? Math.abs(row.value) : '-');
    running = next;
  }
  return {
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, confine: true },
    legend: { data: ['Creștere', 'Scădere'], bottom: 0 },
    grid: { top: 20, right: 18, bottom: 50, left: 58, containLabel: true },
    xAxis: { type: 'category', data: rows.map((row) => row.label) },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'bar',
        stack: 'waterfall',
        data: helper,
        itemStyle: { borderColor: 'transparent', color: 'transparent' },
        emphasis: { itemStyle: { borderColor: 'transparent', color: 'transparent' } },
        tooltip: { show: false },
      },
      { type: 'bar', name: 'Creștere', stack: 'waterfall', data: positive },
      { type: 'bar', name: 'Scădere', stack: 'waterfall', data: negative },
    ],
    title: { text: metric.display_name, left: 0, textStyle: { fontSize: 12 } },
  } as EChartsCoreOption;
}

function histogramOption(
  dataset: QueryDataset,
  metric: MetricDefinition,
): EChartsCoreOption | null {
  const values = finiteValues(dataset);
  if (values.length < 3) return null;
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  if (minimum === maximum) return null;
  const binCount = Math.min(20, Math.max(4, Math.ceil(Math.sqrt(values.length))));
  const width = (maximum - minimum) / binCount;
  const counts = Array.from({ length: binCount }, () => 0);
  for (const value of values) {
    const index = Math.min(binCount - 1, Math.floor((value - minimum) / width));
    counts[index] = (counts[index] ?? 0) + 1;
  }
  const labels = counts.map((_count, index) => {
    const start = minimum + index * width;
    const end = start + width;
    return `${start.toLocaleString('ro-RO', { maximumFractionDigits: 1 })}–${end.toLocaleString('ro-RO', { maximumFractionDigits: 1 })}`;
  });
  return {
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, confine: true },
    grid: { top: 22, right: 18, bottom: 58, left: 52, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLabel: { rotate: 30 } },
    yAxis: { type: 'value', name: 'Frecvență', minInterval: 1 },
    series: [{ type: 'bar', name: metric.display_name, data: counts, barCategoryGap: '4%' }],
  } as EChartsCoreOption;
}

function quantile(sorted: readonly number[], fraction: number): number {
  const index = (sorted.length - 1) * fraction;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const lowerValue = sorted[lower] ?? 0;
  const upperValue = sorted[upper] ?? lowerValue;
  return lowerValue + (upperValue - lowerValue) * (index - lower);
}

function boxplotOption(dataset: QueryDataset, metric: MetricDefinition): EChartsCoreOption | null {
  const values = finiteValues(dataset).sort((left, right) => left - right);
  if (values.length < 5) return null;
  const q1 = quantile(values, 0.25);
  const median = quantile(values, 0.5);
  const q3 = quantile(values, 0.75);
  const iqr = q3 - q1;
  const lowFence = q1 - 1.5 * iqr;
  const highFence = q3 + 1.5 * iqr;
  const whiskerLow = values.find((value) => value >= lowFence) ?? values[0] ?? 0;
  const whiskerHigh =
    [...values].reverse().find((value) => value <= highFence) ?? values.at(-1) ?? 0;
  const outliers = values.filter((value) => value < whiskerLow || value > whiskerHigh);
  return {
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: 'item', confine: true },
    grid: { top: 22, right: 18, bottom: 42, left: 58, containLabel: true },
    xAxis: { type: 'category', data: [metric.display_name] },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'boxplot',
        name: metric.display_name,
        data: [[whiskerLow, q1, median, q3, whiskerHigh]],
      },
      { type: 'scatter', name: 'Outliers', data: outliers.map((value) => [0, value]) },
    ],
  } as EChartsCoreOption;
}

function treemapOption(dataset: QueryDataset, metric: MetricDefinition): EChartsCoreOption | null {
  const category = categoryDimension(dataset);
  const value = valueDimension(dataset);
  if (!category || !value) return null;
  const data = dataset.rows
    .map((row) => ({ name: String(row[category.id] ?? ''), value: Number(row[value.id]) }))
    .filter((row) => row.name && Number.isFinite(row.value) && row.value >= 0);
  if (data.length < 2) return null;
  return {
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: 'item', confine: true },
    series: [
      {
        type: 'treemap',
        name: metric.display_name,
        data,
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: { show: true, formatter: '{b}' },
      },
    ],
  } as EChartsCoreOption;
}

function calendarOption(dataset: QueryDataset, metric: MetricDefinition): EChartsCoreOption | null {
  const dateDimension = dataset.dimensions.find(
    (dimension) => dimension.kind === 'time' || dimension.id === 'date' || dimension.id === 'x',
  );
  const value = valueDimension(dataset);
  if (!dateDimension || !value) return null;
  const data: Array<[string, number]> = dataset.rows
    .map((row): [string, number] => [String(row[dateDimension.id] ?? ''), Number(row[value.id])])
    .filter(([date, amount]) => /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(amount));
  if (data.length === 0) return null;
  const amounts = data.map((item) => Number(item[1]));
  return {
    aria: { enabled: true, decal: { show: true } },
    tooltip: { position: 'top', confine: true },
    visualMap: {
      min: Math.min(...amounts),
      max: Math.max(...amounts),
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    calendar: { range: [String(data[0]?.[0]), String(data.at(-1)?.[0])], cellSize: ['auto', 16] },
    series: [{ type: 'heatmap', coordinateSystem: 'calendar', name: metric.display_name, data }],
  } as EChartsCoreOption;
}

function forecastBandOption(
  dataset: QueryDataset,
  metric: MetricDefinition,
): EChartsCoreOption | null {
  const category = categoryDimension(dataset);
  const value = valueDimension(dataset);
  const lower = dataset.dimensions.find((dimension) => dimension.id === 'lower');
  const upper = dataset.dimensions.find((dimension) => dimension.id === 'upper');
  if (!category || !value || !lower || !upper) return null;
  const points = dataset.rows.map((row) => ({
    label: String(row[category.id] ?? ''),
    value: numericCell(row, value.id),
    lower: numericCell(row, lower.id),
    upper: numericCell(row, upper.id),
  }));
  if (
    !points.some(
      (point) => point.lower !== null && point.upper !== null && point.upper >= point.lower,
    )
  ) {
    return null;
  }
  return {
    aria: { enabled: true, decal: { show: true } },
    tooltip: { trigger: 'axis', confine: true },
    grid: { top: 22, right: 18, bottom: 42, left: 58, containLabel: true },
    xAxis: { type: 'category', data: points.map((point) => point.label) },
    yAxis: { type: 'value' },
    series: [
      {
        type: 'line',
        name: 'Limită inferioară',
        stack: 'forecast-range',
        data: points.map((point) => point.lower),
        lineStyle: { opacity: 0 },
        symbol: 'none',
      },
      {
        type: 'line',
        name: 'Interval forecast',
        stack: 'forecast-range',
        data: points.map((point) =>
          point.lower !== null && point.upper !== null ? point.upper - point.lower : null,
        ),
        lineStyle: { opacity: 0 },
        areaStyle: { opacity: 0.22 },
        symbol: 'none',
      },
      {
        type: 'line',
        name: metric.display_name,
        data: points.map((point) => point.value),
        connectNulls: false,
      },
    ],
  } as EChartsCoreOption;
}

function buildOption(
  shape: ChartSpec['shape'],
  dataset: QueryDataset,
  metric: MetricDefinition,
): EChartsCoreOption | null {
  if (shape === 'donut') return donutOption(dataset, metric);
  if (shape === 'heatmap') return heatmapOption(dataset);
  if (shape === 'scatter') return scatterOption(dataset, metric);
  if (shape === 'waterfall') return waterfallOption(dataset, metric);
  if (shape === 'histogram') return histogramOption(dataset, metric);
  if (shape === 'boxplot') return boxplotOption(dataset, metric);
  if (shape === 'treemap') return treemapOption(dataset, metric);
  if (shape === 'calendar') return calendarOption(dataset, metric);
  if (shape === 'forecast-band') return forecastBandOption(dataset, metric);
  return lineOption(dataset, metric, shape);
}

export function resolveChartSpec(
  metric: MetricDefinition,
  requestedShape: ChartKind,
  dataset: QueryDataset,
): ResolvedChartSpec {
  if (!metric.allowed_shapes.includes(requestedShape)) {
    return {
      kind: 'table',
      requestedShape,
      reason: 'Forma nu este permisă pentru metrica din catalog.',
    };
  }
  if (requestedShape === 'donut' && dataset.rows.length > 6) {
    return {
      kind: 'table',
      requestedShape,
      reason: 'Donut este limitat la maximum șase categorii; folosește tabelul sau ranking bar.',
    };
  }
  const spec = chartSpecRegistry[requestedShape];
  if (!spec) {
    return {
      kind: 'table',
      requestedShape,
      reason: 'Forma nu este implementată.',
    };
  }
  const option = buildOption(spec.shape, dataset, metric);
  if (!option) {
    return {
      kind: 'table',
      requestedShape,
      reason: 'Datasetul nu are dimensiunile necesare pentru forma selectată.',
    };
  }
  return { kind: 'chart', shape: spec.shape, renderer: spec.renderer, option };
}

export function chartEventToUrlState(
  dataset: QueryDataset,
  event: unknown,
): ChartUrlStateEvent | null {
  const category =
    dataset.dimensions.find((dimension) => dimension.role === 'key') ?? categoryDimension(dataset);
  if (!category || !isRecord(event)) return null;
  const eventRecord = event as { data?: unknown; dataIndex?: unknown; name?: unknown };
  const data = isRecord(eventRecord.data) ? eventRecord.data : undefined;
  const row =
    data ??
    (typeof eventRecord.dataIndex === 'number' ? dataset.rows[eventRecord.dataIndex] : undefined);
  const rawValue = row?.[category.id] ?? eventRecord.name;
  if (rawValue === null || rawValue === undefined || typeof rawValue === 'object') return null;
  const labelDimension = dataset.dimensions.find((dimension) => dimension.role === 'label');
  const rawLabel = labelDimension && row ? row[labelDimension.id] : null;
  return {
    dimensionId: category.source_dimension ?? category.id,
    value: String(rawValue),
    label: rawLabel === null || rawLabel === undefined ? null : String(rawLabel),
  };
}

export interface ChartPngExportConfig {
  readonly filename: string;
  readonly pixelRatio: 1 | 2;
}

export function buildSafePngExport(spec: BuiltChartSpec, title: string): ChartPngExportConfig {
  return {
    filename: `${title}-${spec.shape}`,
    pixelRatio: spec.renderer === 'canvas' ? 2 : 1,
  };
}

export function isDatasetValue(value: unknown): value is DatasetValue {
  return (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  );
}
