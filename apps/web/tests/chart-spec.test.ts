import { describe, expect, it } from 'vitest';

import {
  applyWidgetChartOptions,
  buildSafePngExport,
  chartEventToUrlState,
  chartRangeEventToUrlState,
  resolveChartSpec,
} from '../src/components/charts/chart-spec';
import type { MetricDefinition, QueryDataset } from '../src/features/query/schemas';

const metric: MetricDefinition = {
  id: 'sales.total',
  version: 1,
  display_name: 'Vânzări',
  description: 'Suma vânzărilor nete.',
  unit: 'currency',
  aggregation: 'sum',
  allowed_dimensions: ['store', 'time'],
  allowed_grains: ['day', 'month'],
  comparison_policy: 'previous-year',
  allowed_comparisons: ['previous-year'],
  missing_policy: 'null',
  required_capability: 'insight:analytics',
  formula_reference: 'retail',
  allowed_shapes: ['line', 'table', 'waterfall', 'scatter', 'heatmap', 'calendar'],
  suppressible: false,
  source_authority: 'retail',
  query_contract_version: 1,
  effective_from: null,
  effective_to: null,
};

const dataset: QueryDataset = {
  dimensions: [
    { id: 'id', label: 'Magazin', kind: 'string', role: 'key', source_dimension: 'store' },
    { id: 'label', label: 'Etichetă', kind: 'string', role: 'label' },
    { id: 'value', label: 'Vânzări', kind: 'number', role: 'value' },
  ],
  rows: [{ id: 'S001', label: 'Magazin 1', value: 1250 }],
};

describe('ChartSpec registry', () => {
  it('builds dataset dimensions and encode from the whitelisted metric shape', () => {
    const resolved = resolveChartSpec(metric, 'line', dataset);
    expect(resolved.kind).toBe('chart');
    if (resolved.kind !== 'chart') return;
    expect(resolved.renderer).toBe('canvas');
    expect(resolved.option).toMatchObject({
      dataset: { dimensions: ['id', 'label', 'value'] },
      aria: { enabled: true },
    });
    const option = resolved.option as { series?: unknown };
    expect(option.series).toMatchObject([{ type: 'line', encode: { x: 'label', y: 'value' } }]);
  });

  it('falls back to a table for a non-whitelisted shape', () => {
    const resolved = resolveChartSpec(metric, 'donut', dataset);
    expect(resolved).toMatchObject({ kind: 'table', reason: expect.any(String) });
  });

  it('renders only a reconciled start/delta/total waterfall', () => {
    const waterfall: QueryDataset = {
      dimensions: [
        { id: 'label', label: 'Pas', kind: 'string', role: 'label' },
        { id: 'value', label: 'Valoare', kind: 'number', role: 'value' },
        { id: 'step_kind', label: 'Tip', kind: 'string', role: 'metadata' },
      ],
      rows: [
        { label: 'Venit', value: 100, step_kind: 'start' },
        { label: 'Costuri', value: -35, step_kind: 'delta' },
        { label: 'EBIT', value: 65, step_kind: 'total' },
      ],
    };
    expect(resolveChartSpec(metric, 'waterfall', waterfall)).toMatchObject({
      kind: 'chart',
      shape: 'waterfall',
    });
    waterfall.rows[2] = { label: 'EBIT', value: 64, step_kind: 'total' };
    expect(resolveChartSpec(metric, 'waterfall', waterfall)).toMatchObject({ kind: 'table' });
  });

  it('requires explicit semantic x/y axes for scatter', () => {
    expect(resolveChartSpec(metric, 'scatter', dataset)).toMatchObject({ kind: 'table' });
    const scatter: QueryDataset = {
      dimensions: [
        { id: 'id', label: 'Magazin', kind: 'string', role: 'key' },
        { id: 'x', label: 'Productivitate', kind: 'number', role: 'value' },
        { id: 'y', label: 'Realizare', kind: 'number', role: 'metadata' },
      ],
      rows: [{ id: 'S001', x: 1200, y: 98 }],
    };
    expect(resolveChartSpec(metric, 'scatter', scatter)).toMatchObject({
      kind: 'chart',
      shape: 'scatter',
      option: {
        series: [
          {
            data: [{ name: 'S001', value: [1200, 98] }],
            universalTransition: false,
          },
        ],
      },
    });
  });

  it('uses direct Canvas heatmap data without the dataset transform path', () => {
    const heatmap: QueryDataset = {
      dimensions: [
        { id: 'x', label: 'Perioadă', kind: 'string', role: 'key' },
        { id: 'y', label: 'Magazin', kind: 'string', role: 'label' },
        { id: 'value', label: 'Realizare', kind: 'number', role: 'value' },
      ],
      rows: [
        { x: '2026-07', y: 'S001', value: 90 },
        { x: '2026-08', y: 'S001', value: 105 },
      ],
    };
    expect(resolveChartSpec(metric, 'heatmap', heatmap)).toMatchObject({
      kind: 'chart',
      option: {
        dataset: { source: [] },
        xAxis: { data: ['2026-07', '2026-08'] },
        yAxis: { data: ['S001'] },
        series: [
          {
            data: [
              ['2026-07', 'S001', 90],
              ['2026-08', 'S001', 105],
            ],
          },
        ],
      },
    });
  });

  it('renders observed calendar rows without synthesizing missing dates', () => {
    const calendar: QueryDataset = {
      dimensions: [
        { id: 'date', label: 'Dată', kind: 'time', role: 'key', source_dimension: 'time' },
        { id: 'value', label: 'Vânzări', kind: 'number', role: 'value' },
        { id: 'coverage_state', label: 'Coverage', kind: 'string', role: 'metadata' },
      ],
      rows: [
        { date: '2026-08-01', value: 10, coverage_state: 'observed' },
        { date: '2026-08-03', value: 30, coverage_state: 'observed' },
      ],
    };
    const resolved = resolveChartSpec(metric, 'calendar', calendar);
    expect(resolved).toMatchObject({ kind: 'chart', shape: 'calendar' });
    if (resolved.kind !== 'chart') return;
    expect(resolved.option).toMatchObject({
      series: [
        {
          type: 'heatmap',
          data: [
            ['2026-08-01', 10],
            ['2026-08-03', 30],
          ],
        },
      ],
    });
  });

  it('adapts internal chart events to URL-state callbacks', () => {
    expect(
      chartEventToUrlState(dataset, { data: { id: 'S001', label: 'Magazin 1', value: 1250 } }),
    ).toEqual({
      dimensionId: 'store',
      value: 'S001',
      label: 'Magazin 1',
    });
    const resolved = resolveChartSpec(metric, 'line', dataset);
    if (resolved.kind === 'chart') {
      expect(buildSafePngExport(resolved, 'Dashboard / vânzări')).toEqual({
        filename: 'Dashboard / vânzări-line',
        pixelRatio: 2,
      });
    }
  });

  it('adapts a temporal dataZoom selection to a bounded month range', () => {
    const temporal: QueryDataset = {
      dimensions: [
        { id: 'period', label: 'Perioadă', kind: 'time', role: 'key', source_dimension: 'time' },
        { id: 'value', label: 'Vânzări', kind: 'number', role: 'value' },
      ],
      rows: [
        { period: '2026-01', value: 10 },
        { period: '2026-02', value: 20 },
        { period: '2026-03', value: 30 },
        { period: '2026-04', value: 40 },
      ],
    };
    expect(chartRangeEventToUrlState(temporal, { start: 25, end: 75 })).toEqual({
      start: '2026-02',
      end: '2026-03',
    });
    expect(
      chartRangeEventToUrlState(temporal, {
        batch: [{ startValue: '2026-04', endValue: '2026-02' }],
      }),
    ).toEqual({ start: '2026-02', end: '2026-04' });
  });

  it('applies only whitelisted presentation options without mutating the contract', () => {
    const resolved = resolveChartSpec(metric, 'line', dataset);
    if (resolved.kind !== 'chart') return;
    const options = {
      show_legend: false,
      show_labels: true,
      smooth: true,
      ignored: 'unsafe',
    };
    const configured = applyWidgetChartOptions(resolved.option, 'line', options) as {
      legend?: { show?: boolean };
      series?: Array<{ label?: { show?: boolean }; smooth?: boolean }>;
    };
    expect(configured.legend?.show).toBe(false);
    expect(configured.series?.[0]).toMatchObject({ label: { show: true }, smooth: true });
    expect(configured).not.toHaveProperty('ignored');
  });
});
