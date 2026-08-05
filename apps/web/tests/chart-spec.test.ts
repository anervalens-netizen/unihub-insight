import { describe, expect, it } from 'vitest';

import {
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
  allowed_shapes: ['line', 'table', 'waterfall'],
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

  it('does not render a fake waterfall', () => {
    const resolved = resolveChartSpec(metric, 'waterfall', dataset);
    expect(resolved).toMatchObject({ kind: 'table' });
    if (resolved.kind === 'table') expect(resolved.reason).toContain('Waterfall');
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
});
