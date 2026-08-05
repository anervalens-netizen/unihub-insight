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
  readonly shape: Exclude<ChartKind, 'kpi' | 'table' | 'waterfall'>;
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
};

export { chartSpecRegistry };

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
  const comparison = dimensionByRole(dataset, 'comparison');
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
  if (comparison) {
    series.push({
      type: 'line',
      name: 'Comparație',
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
  return {
    ...baseOption(dataset, 'item'),
    xAxis: { type: 'category' },
    yAxis: { type: 'category' },
    visualMap: {
      min: 0,
      max: 100,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
    },
    series: [
      {
        type: 'heatmap',
        encode: { x: x.id, y: y.id, value: value.id, tooltip: [x.id, y.id, value.id] },
      },
    ],
  } as EChartsCoreOption;
}

function scatterOption(dataset: QueryDataset, metric: MetricDefinition): EChartsCoreOption | null {
  const numeric = dataset.dimensions.filter(
    (dimension) => dimension.kind === 'number' || dimension.kind === 'integer',
  );
  const x = numeric[0];
  const y = numeric[1];
  if (!x || !y) return null;
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
        encode: {
          x: x.id,
          y: y.id,
          ...(label ? { itemName: label.id, tooltip: [label.id, x.id, y.id] } : {}),
        },
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
      reason:
        requestedShape === 'waterfall'
          ? 'Waterfall nu este implementat fără reconciliere.'
          : 'Forma nu este implementată.',
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
    dimensionId: category.id,
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
