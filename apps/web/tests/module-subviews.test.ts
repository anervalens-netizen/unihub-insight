import { describe, expect, it } from 'vitest';
import type { ModuleAnalytics } from '../src/features/modules/schemas';
import { subviewForId, subviewStatus } from '../src/features/modules/subviews';
import { moduleWidgetQuerySpec } from '../src/features/modules/widget-catalog';

function moduleData(sources: Record<string, unknown>): ModuleAnalytics {
  return { meta: { sources, period: '2026-08' } } as ModuleAnalytics;
}

const source = (
  status: 'official' | 'partial' | 'stale' | 'unavailable',
  sourceName = 'reporting_campaign_month_v1',
) => ({
  domain: 'campaigns',
  source: sourceName,
  period: '2026-08',
  cutoff: null,
  as_of: null,
  is_final: false,
  coverage_numerator: null,
  coverage_denominator: null,
  source_generation: null,
  authority: 'retail',
  authority_head: null,
  contract_version: 1,
  rule_version: null,
  status,
  produced_at: null,
  warnings: [],
});

describe('module subview availability', () => {
  it('keeps mechanism-specific campaign views unavailable without metadata proof', () => {
    const view = subviewForId('campaigns', 'promo');
    const status = subviewStatus(moduleData({ campaigns: source('official') }), view);
    expect(status.availability).toBe('unavailable');
    expect(status.reason).toContain('contract');
  });

  it('shows Focus as partial when the source says so and preserves missing status', () => {
    const partial = subviewStatus(
      moduleData({ campaigns: source('partial', 'reporting_focus_item_month') }),
      subviewForId('campaigns', 'focus'),
    );
    expect(partial.availability).toBe('partial');
    expect(subviewStatus(moduleData({}), subviewForId('campaigns', 'overview')).availability).toBe(
      'unavailable',
    );
  });

  it('maps native analytical widgets to canonical query metrics and excludes alerts', () => {
    expect(moduleWidgetQuerySpec('sales', 'kpi:sales.total')).toEqual({
      kind: 'kpi',
      metricId: 'sales.total',
    });
    expect(moduleWidgetQuerySpec('finance', 'matrix')).toEqual({
      kind: 'matrix',
      metricId: 'finance.ebit_margin',
    });
    expect(moduleWidgetQuerySpec('campaigns', 'distribution')).toEqual({
      kind: 'distribution',
      metricId: 'campaigns.focus_sales',
    });
    expect(moduleWidgetQuerySpec('planning', 'matrix')).toBeNull();
    expect(moduleWidgetQuerySpec('sales', 'alerts')).toBeNull();
  });
});
