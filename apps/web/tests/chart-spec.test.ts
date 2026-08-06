import { describe, expect, it } from 'vitest';

import {
  applyWidgetChartOptions,
  buildSafePngExport,
  chartEventToUrlState,
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
  allowed_grains: ['month'],
  comparison_policy: 'previous-year',
  missing_policy: 'null',
  required_capability: 'insight:analytics',
  formula_reference: 'retail',
  allowed_shapes: ['line', 'table', 'waterfall', 'scatter', 'heatmap'],
  suppressible: false,
  source_authority: 'retail',
  query_contract_version: 1,
  effective_from: null,
  effective_to: null,
};

const dataset: QueryDataset = {
  dimensions: [
    { id: 'id', label: 'Magazin', kind: 'string', role: 'key' },
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
      aria: { enabled: true, decal: { show: true } },
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
    });
  });

  it('adapts internal chart events to URL-state callbacks', () => {
    expect(
      chartEventToUrlState(dataset, { data: { id: 'S001', label: 'Magazin 1', value: 1250 } }),
    ).toEqual({
      dimensionId: 'id',
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
