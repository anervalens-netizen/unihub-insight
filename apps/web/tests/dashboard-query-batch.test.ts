import { describe, expect, it } from 'vitest';

import { dashboardBatchRequest } from '../src/features/dashboards/query-mapping';
import { dashboardDocumentSchema } from '../src/features/dashboards/schemas';

const widget = (id: string) => ({
  id,
  module: 'sales' as const,
  title: id,
  metric_id: 'sales.total',
  visualization: 'line' as const,
  dimension: 'store',
  dimensions: ['store', 'time'],
  time_grain: 'month',
  filter_mode: 'augment' as const,
  filters: { stores: 'S001' },
  options: {},
  layout: { x: 0, y: 0, w: 6, h: 4, min_w: 4, min_h: 3 },
});

describe('custom dashboard batch mapping', () => {
  it('maps legacy widgets to one bounded batch with compatibility defaults', () => {
    const dashboard = dashboardDocumentSchema.parse({
      id: 'dashboard-1',
      name: 'Sales',
      description: '',
      owner_subject: 'andrei',
      visibility: 'private',
      version: 1,
      widgets: Array.from({ length: 13 }, (_, index) => widget(`w-${index}`)),
      created_at: '2026-08-05T08:00:00Z',
      updated_at: '2026-08-05T08:00:00Z',
    });
    const request = dashboardBatchRequest(dashboard, {
      period: '2026-08',
      comparison: 'previous-year',
      firm: 'MOBIUP',
    });

    expect(request.dashboard_id).toBe('dashboard-1');
    expect(request.widgets).toHaveLength(12);
    expect(request.widgets[0]).toMatchObject({
      metric_version: 1,
      query_contract_version: 1,
      dimensions: ['store', 'time'],
      time_range: { start: '2026-08', end: '2026-08' },
      filters: { firm: 'MOBIUP', stores: 'S001' },
      comparisons: ['previous-year'],
    });
    expect(request.widgets[0]?.filters).not.toHaveProperty('range');
    expect(request.widgets[0]?.filters).not.toHaveProperty('drill');
  });
});
