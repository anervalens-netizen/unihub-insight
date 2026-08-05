import { describe, expect, it } from 'vitest';

import {
  queryBatchResponseSchema,
  queryDatasetSchema,
  widgetQuerySchema,
} from '../src/features/query/schemas';

const source = {
  domain: 'sales' as const,
  source: 'reporting_sales_month_v1',
  period: '2026-08',
  cutoff: '2026-08-04',
  as_of: '2026-08-04',
  is_final: false,
  coverage_numerator: 4,
  coverage_denominator: 5,
  source_generation: 'sales-2026-08-r3',
  authority: 'retail-import',
  authority_head: 'head-3',
  contract_version: 1,
  rule_version: 'sales-v1',
  status: 'partial' as const,
  produced_at: '2026-08-05T08:00:00Z',
  warnings: ['open period'],
};

const query = widgetQuerySchema.parse({
  widget_id: 'sales-trend',
  module: 'sales',
  metric_id: 'sales.total',
  dimensions: ['time'],
  time_range: { start: '2026-08', end: '2026-08' },
  visualization: 'line',
});

describe('query contract schemas', () => {
  it('retains snapshot, source metadata and per-widget errors', () => {
    const response = queryBatchResponseSchema.parse({
      snapshot: {
        id: 'snapshot-42',
        contract_version: 1,
        period: '2026-08',
        resolved_at: '2026-08-05T08:00:00Z',
        sources: { sales: source },
      },
      results: [
        {
          widget_id: query.widget_id,
          query,
          dataset: null,
          meta: null,
          error: { code: 'deadline-exceeded', message: 'slow', retryable: true },
        },
      ],
      deadline_ms: 8_000,
      generated_at: '2026-08-05T08:00:01Z',
    });

    expect(response.snapshot.id).toBe('snapshot-42');
    const sources = response.snapshot.sources as { sales?: { source_generation?: string | null } };
    expect(sources.sales?.source_generation).toBe('sales-2026-08-r3');
    expect(response.results[0]?.error?.code).toBe('deadline-exceeded');
    expect(response.results[0]?.error?.retryable).toBe(true);
  });

  it('keeps null dataset values as null', () => {
    const dataset = queryDatasetSchema.parse({
      dimensions: [
        { id: 'label', label: 'Perioadă', kind: 'string', role: 'label' },
        { id: 'value', label: 'Vânzări', kind: 'number', role: 'value' },
      ],
      rows: [{ label: '2026-08', value: null }],
    });
    const firstRow = dataset.rows[0] as { value?: unknown } | undefined;
    expect(firstRow?.value).toBeNull();
  });
});
