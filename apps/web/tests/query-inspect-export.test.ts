import { describe, expect, it } from 'vitest';

import { buildExportRequest, buildInspectRequest } from '../src/features/query/api';
import { widgetQuerySchema } from '../src/features/query/schemas';

const query = widgetQuerySchema.parse({
  widget_id: 'widget-1',
  module: 'sales',
  metric_id: 'sales.total',
  dimensions: ['store'],
  time_range: { start: '2026-01', end: '2026-08' },
  comparisons: ['target', 'previous-year'],
  visualization: 'table',
});

describe('custom widget inspect/export request construction', () => {
  it('reuses the batch snapshot and exact widget query for inspect and CSV export', () => {
    const inspect = buildInspectRequest('snapshot-42', 'dash-1', query);
    const exportRequest = buildExportRequest('snapshot-42', 'dash-1', query);
    expect(inspect).toEqual({
      snapshot_id: 'snapshot-42',
      dashboard_id: 'dash-1',
      query,
      page: 1,
      page_size: 100,
    });
    expect(exportRequest).toEqual(inspect);
    expect(exportRequest.query).toBe(query);
  });

  it('supports native widgets without a saved dashboard identity', () => {
    expect(buildInspectRequest('snapshot-42', null, query)).toMatchObject({
      snapshot_id: 'snapshot-42',
      dashboard_id: null,
      query,
    });
  });
});
