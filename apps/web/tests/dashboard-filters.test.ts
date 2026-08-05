import { describe, expect, it } from 'vitest';

import {
  resolveWidgetSearch,
  widgetFilterLabel,
} from '../src/features/dashboards/filter-resolution';
import type { DashboardWidget } from '../src/features/dashboards/schemas';

const widget: DashboardWidget = {
  id: 'w1',
  module: 'sales',
  title: 'Sales',
  metric_id: 'sales.total',
  metric_version: 1,
  query_contract_version: 1,
  visualization: 'kpi',
  dimension: null,
  time_grain: 'month',
  filter_mode: 'inherit',
  filters: {},
  options: {},
  comparisons: [],
  sort: [],
  limit: 30,
  layout: { x: 0, y: 0, w: 6, h: 4, min_w: 4, min_h: 3 },
};
const global = {
  period: '2026-08',
  comparison: 'previous-year' as const,
  firm: 'MOBIUP',
  regional: 'Sud',
  agent: 'Agent 1',
};

describe('widget filter resolution', () => {
  it('inherits the complete global scope', () => {
    expect(resolveWidgetSearch(global, widget)).toEqual(global);
  });
  it('augments or overrides scope explicitly', () => {
    expect(
      resolveWidgetSearch(global, {
        ...widget,
        filter_mode: 'augment',
        filters: { stores: 'S001' },
      }),
    ).toMatchObject({ firm: 'MOBIUP', stores: 'S001' });
    expect(
      resolveWidgetSearch(global, {
        ...widget,
        filter_mode: 'override',
        filters: { firm: 'MOBICELL' },
      }),
    ).toEqual({ period: '2026-08', comparison: 'previous-year', firm: 'MOBICELL' });
  });
  it('ignores business filters and removes agent from unsupported modules', () => {
    expect(resolveWidgetSearch(global, { ...widget, filter_mode: 'ignore' })).toEqual({
      period: '2026-08',
      comparison: 'previous-year',
    });
    expect(resolveWidgetSearch(global, { ...widget, module: 'finance' })).not.toHaveProperty(
      'agent',
    );
  });
  it('describes local filter state visibly', () => {
    expect(
      widgetFilterLabel({ ...widget, filter_mode: 'augment', filters: { firm: 'MOBIUP' } }),
    ).toBe('Completează · 1 locale');
  });
});
