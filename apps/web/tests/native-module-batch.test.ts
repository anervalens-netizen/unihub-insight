import { describe, expect, it } from 'vitest';

import { applyNativeBatchResults } from '../src/features/modules/native-batch';
import type { ModuleAnalytics } from '../src/features/modules/schemas';
import type { WidgetQueryResult } from '../src/features/query/schemas';

const base = {
  module: 'performance',
  kpis: [
    { id: 'performance.average', value: 1, supporting_value: null },
    { id: 'performance.at_target', value: 1, supporting_value: null },
  ],
  trend: [],
  distribution: [],
  breakdown: [],
  matrix: [{ x: 'legacy', y: 'legacy', value: 999, label: null, risk: 'risk' }],
  calendar: [],
} as unknown as ModuleAnalytics;

function result(
  widgetId: string,
  visualization: WidgetQueryResult['query']['visualization'],
  rows: NonNullable<WidgetQueryResult['dataset']>['rows'],
): WidgetQueryResult {
  return {
    widget_id: widgetId,
    query: {
      widget_id: widgetId,
      module: 'performance',
      metric_id: 'performance.average',
      metric_version: 1,
      query_contract_version: 1,
      dimensions: [],
      time_range: null,
      time_grain: 'month',
      filters: {},
      comparisons: [],
      sort: [],
      limit: 100,
      visualization,
    },
    dataset: { dimensions: [], rows },
    meta: null,
    error: null,
  };
}

describe('native module query batch projection', () => {
  it('replaces native KPI and matrix values with the common batch result', () => {
    const projected = applyNativeBatchResults(base, [
      result('kpi:performance.average', 'kpi', [{ value: '88.5' }]),
      result('matrix', 'heatmap', [{ x: '2026-08', y: 'S001', value: '91' }]),
    ]);

    expect(projected.kpis[0]?.value).toBe(88.5);
    expect(projected.matrix).toEqual([
      { x: '2026-08', y: 'S001', value: 91, label: null, risk: 'healthy' },
    ]);
  });

  it('does not reuse the legacy module payload when a batch widget fails', () => {
    const failed = result('matrix', 'heatmap', []);
    failed.dataset = null;
    failed.error = { code: 'unavailable', message: 'Sursă lipsă', retryable: false };

    expect(applyNativeBatchResults(base, [failed]).matrix).toEqual([]);
  });
});
