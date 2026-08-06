import { describe, expect, it } from 'vitest';
import { moduleSubviewData } from '../src/features/modules/AnalyticsModulePage';
import type { ModuleAnalytics } from '../src/features/modules/schemas';
import { subviewForId, subviewStatus } from '../src/features/modules/subviews';
import { moduleWidgetQuerySpec, moduleWidgets } from '../src/features/modules/widget-catalog';

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

  it('understands normalized Retail warnings and never substitutes Focus for absent mechanisms', () => {
    const campaignSource = {
      ...source('partial', 'reporting_focus_item_month'),
      warnings: ['focus_only_promo_incentive_contest_and_folii_unavailable'],
    };
    expect(
      subviewStatus(moduleData({ campaigns: campaignSource }), subviewForId('campaigns', 'promo'))
        .availability,
    ).toBe('unavailable');
    expect(
      subviewStatus(moduleData({ campaigns: campaignSource }), subviewForId('campaigns', 'focus'))
        .availability,
    ).toBe('partial');
  });

  it('blocks official-roster surfaces when Workforce is only sales-derived activity', () => {
    const workforceSource = {
      ...source('partial', 'reporting_agent_month'),
      domain: 'workforce',
      warnings: ['sales_activity_is_not_an_official_workforce_roster'],
    };
    const data = moduleData({ workforce: workforceSource });
    expect(subviewStatus(data, subviewForId('workforce', 'people')).availability).toBe(
      'unavailable',
    );
    expect(subviewStatus(data, subviewForId('workforce', 'movements')).availability).toBe(
      'unavailable',
    );
    expect(subviewStatus(data, subviewForId('workforce', 'productivity')).availability).toBe(
      'partial',
    );
  });

  it('recognizes scenario lineage outside the source label', () => {
    const planningSource = {
      ...source('official', 'planning_authorities'),
      domain: 'planning',
      source_generation: 'target-scenario:42',
    };
    expect(
      subviewStatus(moduleData({ planning: planningSource }), subviewForId('planning', 'scenarios'))
        .availability,
    ).toBe('available');
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
    expect(moduleWidgetQuerySpec('performance', 'scatter')).toEqual({
      kind: 'scatter',
      metricId: 'performance.average',
    });
    expect(moduleWidgetQuerySpec('performance', 'histogram')).toEqual({
      kind: 'histogram',
      metricId: 'performance.average',
    });
    expect(moduleWidgetQuerySpec('compensation', 'histogram')).toEqual({
      kind: 'histogram',
      metricId: 'compensation.average',
    });
    expect(moduleWidgetQuerySpec('finance', 'waterfall')).toEqual({
      kind: 'waterfall',
      metricId: 'finance.ebit',
    });
    expect(moduleWidgetQuerySpec('planning', 'forecast')).toEqual({
      kind: 'trend',
      metricId: 'planning.forecast',
    });
    expect(moduleWidgetQuerySpec('sales', 'calendar')).toEqual({
      kind: 'calendar',
      metricId: 'sales.total',
    });
    expect(moduleWidgetQuerySpec('campaigns', 'focus-ranking')).toEqual({
      kind: 'breakdown',
      metricId: 'campaigns.focus_share',
    });
    expect(moduleWidgetQuerySpec('planning', 'accuracy-scatter')).toEqual({
      kind: 'scatter',
      metricId: 'planning.forecast',
    });
    expect(moduleWidgetQuerySpec('performance', 'visits-trend')).toEqual({
      kind: 'trend',
      metricId: 'visits.total',
    });
    expect(moduleWidgetQuerySpec('workforce', 'visits-breakdown')).toEqual({
      kind: 'breakdown',
      metricId: 'visits.total',
    });
    expect(moduleWidgetQuerySpec('workforce', 'visits-matrix')).toEqual({
      kind: 'matrix',
      metricId: 'visits.total',
    });
  });

  it('uses specialized recipes instead of the generic template where data supports them', () => {
    const base = {
      meta: { period: '2026-08', sources: {} },
      kpis: [],
      trend: [],
      distribution: [],
      breakdown: [],
      matrix: [],
      alerts: [],
    } as unknown as ModuleAnalytics;
    expect(
      moduleWidgets({ ...base, module: 'sales' } as ModuleAnalytics, 'pace').map(
        (widget) => widget.id,
      ),
    ).toContain('pace');
    expect(
      moduleWidgets({ ...base, module: 'performance' } as ModuleAnalytics, 'rankings').map(
        (widget) => widget.id,
      ),
    ).toContain('ranking');
    expect(
      moduleWidgets({ ...base, module: 'performance' } as ModuleAnalytics, 'consistency').map(
        (widget) => widget.id,
      ),
    ).toContain('histogram');
    expect(
      moduleWidgets({ ...base, module: 'finance' } as ModuleAnalytics, 'reconciliation').map(
        (widget) => widget.id,
      ),
    ).toContain('waterfall');
    expect(
      moduleWidgets({ ...base, module: 'planning' } as ModuleAnalytics, '12-months').map(
        (widget) => widget.id,
      ),
    ).toContain('forecast');
    expect(
      moduleWidgets({ ...base, module: 'sales' } as ModuleAnalytics, 'transactions').map(
        (widget) => widget.id,
      ),
    ).toEqual([
      'kpi:receipts.total',
      'kpi:receipts.average_value',
      'kpi:receipt_2plus_pct',
      'alerts',
    ]);
    expect(
      moduleWidgets({ ...base, module: 'campaigns' } as ModuleAnalytics, 'focus').map(
        (widget) => widget.id,
      ),
    ).toEqual([
      'kpi:campaigns.focus_sales',
      'kpi:campaigns.focus_share',
      'kpi:campaigns.active_stores',
      'kpi:campaigns.active_products',
      'focus-ranking',
      'distribution',
      'matrix',
    ]);
    expect(
      moduleWidgets({ ...base, module: 'planning' } as ModuleAnalytics, 'accuracy').map(
        (widget) => widget.id,
      ),
    ).toContain('accuracy-scatter');
    const visitsSlice = {
      axes: [],
      supported_charts: [],
      kpis: [
        { id: 'visits.total' },
        { id: 'visits.distinct_stores' },
        { id: 'visits.avg_completion' },
        { id: 'visits.checklist_score' },
      ],
      trend: [],
      distribution: [],
      breakdown: [],
      matrix: [],
      calendar: [],
      alerts: [],
    } as unknown as NonNullable<ModuleAnalytics['visits']>;
    const visitsData = moduleSubviewData(
      { ...base, module: 'performance', visits: visitsSlice } as ModuleAnalytics,
      subviewForId('performance', 'visits'),
    );
    expect(visitsData.kpis[0]?.id).toBe('visits.total');
    expect(moduleWidgets(visitsData, 'visits').map((widget) => widget.id)).toEqual([
      'kpi:visits.total',
      'kpi:visits.distinct_stores',
      'kpi:visits.avg_completion',
      'kpi:visits.checklist_score',
      'visits-trend',
      'visits-breakdown',
      'visits-matrix',
    ]);
  });
});
