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
  domain = 'campaigns',
) => ({
  domain,
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
  warnings: [] as string[],
});

const slice = (
  status: 'official' | 'partial' | 'stale' | 'unavailable',
  sourceMetadata = source(status),
  kpis: unknown[] = [],
) =>
  ({
    status,
    sources: { [sourceMetadata.domain]: sourceMetadata },
    axes: [],
    supported_charts: [],
    kpis,
    trend: [],
    distribution: [],
    breakdown: [],
    matrix: [],
    calendar: [],
    alerts: [],
  }) as unknown as NonNullable<ModuleAnalytics['campaigns']>[string];

describe('module subview availability', () => {
  it('requires the server-side slice for mechanism-specific campaign views', () => {
    const view = subviewForId('campaigns', 'promo');
    const status = subviewStatus(moduleData({ campaigns: source('official') }), view);
    expect(status.availability).toBe('unavailable');
    expect(status.reason).toContain('Slice-ul server-side');
  });

  it('uses the Focus slice status and keeps warnings non-authoritative', () => {
    const focusSource = source('official', 'reporting_focus_item_month');
    const partial = subviewStatus(
      {
        ...moduleData({ campaigns: focusSource }),
        subviews: { focus: slice('partial', focusSource) },
      } as ModuleAnalytics,
      subviewForId('campaigns', 'focus'),
    );
    expect(partial.availability).toBe('partial');
    expect(
      subviewStatus(
        {
          ...moduleData({
            campaigns: {
              ...source('official', 'reporting_focus_item_month'),
              warnings: ['focus_only_promo_incentive_contest_and_folii_unavailable'],
            },
          }),
          subviews: {
            focus: slice('official', {
              ...focusSource,
              warnings: ['focus_only_promo_incentive_contest_and_folii_unavailable'],
            }),
          },
        } as ModuleAnalytics,
        subviewForId('campaigns', 'focus'),
      ).availability,
    ).toBe('available');
    expect(subviewStatus(moduleData({}), subviewForId('campaigns', 'overview')).availability).toBe(
      'unavailable',
    );
  });

  it('keeps Promo, Incentive, Folii and Concurs distinct', () => {
    const campaignSource = source('partial', 'campaign_reporting_heads');
    const data = {
      ...moduleData({
        campaigns: campaignSource,
        contest: source('official', 'reporting_contest_month_v1', 'contest'),
      }),
      campaigns: {
        promo: slice('partial', campaignSource, [
          { id: 'campaigns.promo_sales', label: 'Vânzări Promo', value: 1, unit: 'currency' },
        ]),
        incentive: slice('official', campaignSource),
        folii: slice('official', campaignSource),
        contest: slice('official', source('official', 'reporting_contest_month_v1', 'contest')),
      },
      subviews: { focus: slice('partial', campaignSource) },
    } as ModuleAnalytics;

    expect(subviewStatus(data, subviewForId('campaigns', 'promo')).availability).toBe('partial');
    expect(moduleSubviewData(data, subviewForId('campaigns', 'promo')).kpis[0]?.id).toBe(
      'campaigns.promo_sales',
    );
    expect(subviewStatus(data, subviewForId('campaigns', 'incentive')).availability).toBe(
      'available',
    );
    expect(subviewStatus(data, subviewForId('campaigns', 'folii')).availability).toBe('available');
    expect(subviewStatus(data, subviewForId('campaigns', 'contest')).availability).toBe(
      'available',
    );
  });

  it('renders observed commercial workforce slices as partial with a clear warning', () => {
    const workforceSource = source('partial', 'reporting_agent_month', 'workforce');
    const data = {
      ...moduleData({ workforce: workforceSource }),
      subviews: {
        people: slice('partial', workforceSource),
        movements: slice('partial', workforceSource),
        stability: slice('partial', workforceSource),
        coverage: slice('partial', workforceSource),
      },
    } as ModuleAnalytics;
    for (const id of ['people', 'movements', 'stability', 'coverage'] as const) {
      const status = subviewStatus(data, subviewForId('workforce', id));
      expect(status.availability).toBe('partial');
      expect(status.reason).toContain('Activitate comercială observată');
    }
  });

  it('keeps Planning subviews without their own contract fail-closed', () => {
    const planningSource = {
      ...source('official', 'planning_authorities'),
      domain: 'planning',
      source_generation: 'target-scenario:42',
    };
    expect(
      subviewStatus(moduleData({ planning: planningSource }), subviewForId('planning', 'scenarios'))
        .availability,
    ).toBe('unavailable');
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
    expect(moduleWidgetQuerySpec('campaigns', 'trend', 'promo')).toEqual({
      kind: 'trend',
      metricId: 'campaigns.promo_sales',
    });
    expect(moduleWidgetQuerySpec('campaigns', 'breakdown', 'contest')).toEqual({
      kind: 'breakdown',
      metricId: 'campaigns.contest_points_total',
    });
    expect(moduleWidgetQuerySpec('campaigns', 'distribution', 'folii')).toEqual({
      kind: 'distribution',
      metricId: 'campaigns.folii_discount',
    });
    expect(moduleWidgetQuerySpec('workforce', 'breakdown', 'grile')).toEqual({
      kind: 'breakdown',
      metricId: 'grile.problem_stores',
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
      moduleWidgets({ ...base, module: 'campaigns' } as ModuleAnalytics, 'contest').map(
        (widget) => widget.id,
      ),
    ).toEqual([
      'kpi:campaigns.contest_points_total',
      'kpi:campaigns.contest_focus_units',
      'kpi:campaigns.contest_promo_units',
      'kpi:campaigns.contest_price_units',
      'kpi:campaigns.contest_focus_points',
      'kpi:campaigns.contest_promo_points',
      'kpi:campaigns.contest_price_points',
      'trend',
      'campaign-ranking',
      'breakdown',
      'distribution',
      'alerts',
    ]);
    expect(
      moduleWidgets({ ...base, module: 'campaigns' } as ModuleAnalytics, 'folii').map(
        (widget) => widget.id,
      ),
    ).toContain('kpi:campaigns.folii_sales');
    expect(
      moduleWidgets({ ...base, module: 'workforce' } as ModuleAnalytics, 'grile').map(
        (widget) => widget.id,
      ),
    ).toEqual(['kpi:grile.observed_stores', 'kpi:grile.problem_stores', 'breakdown', 'alerts']);
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
