import { describe, expect, it } from 'vitest';

import { moduleSubviewData, nativeWidgetQuery } from '../src/features/modules/AnalyticsModulePage';
import {
  filterPortfolioRows,
  portfolioPageCount,
  portfolioPageRows,
} from '../src/features/modules/portfolio';
import type { ModuleAnalytics } from '../src/features/modules/schemas';
import { moduleAnalyticsSchema, moduleAnalyticsSliceSchema } from '../src/features/modules/schemas';
import {
  specializedSubviewActions,
  subviewForId,
  unavailableSubviewCopy,
} from '../src/features/modules/subviews';
import { moduleWidgetQuerySpec, moduleWidgets } from '../src/features/modules/widget-catalog';
import type { MetricDefinition } from '../src/features/query/schemas';

const slice = {
  axes: [
    { key: 'primary', label: 'Vânzări nete', unit: 'currency' },
    { key: 'secondary', label: 'Cantitate netă', unit: 'integer' },
    { key: 'tertiary', label: 'Cantitate retur semnată', unit: 'integer' },
    { key: 'quaternary', label: 'Incidențe SKU în bonuri', unit: 'integer' },
  ],
  supported_charts: ['kpi', 'bar', 'donut', 'table'],
  kpis: [
    {
      id: 'sales.portfolio_sales',
      label: 'Vânzări nete',
      value: 100,
      unit: 'currency',
      risk: 'healthy',
    },
  ],
  trend: [],
  distribution: [{ id: 'SKU-1', label: 'Produs', value: 100, share_pct: 100 }],
  breakdown: [
    {
      id: 'SKU-1',
      label: 'Produs',
      context: 'Brand · Categorie',
      primary: 100,
      secondary: 2,
      tertiary: -1,
      quaternary: 3,
      risk: 'healthy',
    },
  ],
  matrix: [],
  calendar: [],
  alerts: [],
  entity_dimension: 'product',
  distribution_dimension: 'product',
};

const metric = {
  id: 'sales.portfolio_sales',
  version: 1,
  display_name: 'Portfolio sales',
  description: 'Portfolio sales',
  unit: 'currency',
  aggregation: 'sum',
  allowed_dimensions: ['category', 'subcategory', 'brand', 'product'],
  allowed_grains: ['month'],
  comparison_policy: 'none',
  allowed_comparisons: [],
  missing_policy: 'missing',
  required_capability: 'insight:analytics',
  formula_reference: 'portfolio',
  allowed_shapes: ['kpi', 'donut', 'table'],
  suppressible: false,
  source_authority: 'unihub-retail',
  query_contract_version: 1,
  effective_from: null,
  effective_to: null,
} satisfies MetricDefinition;

describe('Sales Portfolio web contract', () => {
  it('parses quaternary and taxonomy dimensions on portfolio slices', () => {
    const parsedSlice = moduleAnalyticsSliceSchema.parse(slice);
    expect(parsedSlice.breakdown[0]?.quaternary).toBe(3);
    expect(parsedSlice.entity_dimension).toBe('product');
    expect(parsedSlice.distribution_dimension).toBe('product');

    const parsedModule = moduleAnalyticsSchema.parse({
      meta: {
        period: '2026-08',
        comparison: 'none',
        as_of: null,
        is_final: false,
        data_mode: 'demo',
        currency: 'RON',
        scope_label: 'Toate magazinele',
        generated_at: '2026-08-06T10:00:00Z',
        source: 'retail',
      },
      module: 'sales',
      title: 'Sales',
      description: 'Sales',
      required_capability: 'insight:analytics',
      axes: [],
      supported_charts: [],
      kpis: [],
      trend: [],
      distribution: [],
      breakdown: [],
      matrix: [],
      calendar: [],
      alerts: [],
      portfolio: { product: slice },
    });
    expect(Object.values(parsedModule.portfolio)[0]?.entity_dimension).toBe('product');
  });

  it('uses exactly the selected taxonomy dimension for portfolio KPI and table queries', () => {
    const search = { period: '2026-08', comparison: 'none' as const };
    const expectedDimensions = {
      'portfolio-category': 'category',
      'portfolio-subcategory': 'subcategory',
      'portfolio-brand': 'brand',
      'portfolio-product': 'product',
    } as const;
    for (const [subview, dimension] of Object.entries(expectedDimensions)) {
      const kpi = nativeWidgetQuery(
        'sales',
        'kpi:sales.portfolio_sales',
        search,
        metric,
        subview as keyof typeof expectedDimensions,
      );
      const table = nativeWidgetQuery(
        'sales',
        'portfolio-table',
        search,
        metric,
        subview as keyof typeof expectedDimensions,
      );
      expect(kpi?.dimensions).toEqual([dimension]);
      expect(table?.dimensions).toEqual([dimension]);
      expect(table?.visualization).toBe('table');
      expect(table?.limit).toBe(5000);
    }
  });

  it('uses the published Campaigns distribution dimensions', () => {
    const search = { period: '2026-08', comparison: 'none' as const };
    const campaignMetric = {
      ...metric,
      id: 'campaigns.promo_discount',
      allowed_dimensions: ['campaign'],
    } satisfies MetricDefinition;
    const focusMetric = {
      ...metric,
      id: 'campaigns.focus_sales',
      allowed_dimensions: ['subcategory'],
    } satisfies MetricDefinition;
    const contestMetric = {
      ...metric,
      id: 'campaigns.contest_points_total',
      allowed_dimensions: ['contest'],
    } satisfies MetricDefinition;

    expect(
      nativeWidgetQuery('campaigns', 'distribution', search, campaignMetric, 'promo')?.dimensions,
    ).toEqual(['campaign']);
    expect(
      nativeWidgetQuery('campaigns', 'distribution', search, focusMetric, 'focus')?.dimensions,
    ).toEqual(['subcategory']);
    expect(
      nativeWidgetQuery('campaigns', 'distribution', search, contestMetric, 'contest')?.dimensions,
    ).toEqual(['contest']);
  });

  it('renders the required portfolio widgets and omits product distribution', () => {
    const base = {
      module: 'sales',
      kpis: [],
      trend: [],
      distribution: [],
      breakdown: [],
      matrix: [],
      alerts: [],
    } as unknown as ModuleAnalytics;
    expect(moduleWidgetQuerySpec('sales', 'portfolio-table')).toEqual({
      kind: 'table',
      metricId: 'sales.portfolio_sales',
    });
    expect(moduleWidgets(base, 'portfolio-category').map((widget) => widget.id)).toEqual([
      'kpi:sales.portfolio_sales',
      'kpi:sales.portfolio_net_quantity',
      'portfolio-distribution',
      'portfolio-table',
    ]);
    const productWidgets = moduleWidgets(base, 'portfolio-product');
    expect(productWidgets.map((widget) => widget.id)).toEqual([
      'kpi:sales.portfolio_sales',
      'kpi:sales.portfolio_net_quantity',
      'kpi:sales.portfolio_return_quantity',
      'kpi:sales.portfolio_receipt_incidence',
      'portfolio-table',
    ]);
    expect(productWidgets.at(-1)?.w).toBe(24);
  });

  it('keeps portfolio search local and paginates in pages of 50', () => {
    const rows = Array.from({ length: 101 }, (_, index) => ({
      id: `SKU-${index}`,
      label: `Produs ${index}`,
      context: `Brand ${index % 2}`,
      primary: index === 100 ? -10 : index,
      secondary: 1,
      tertiary: -1,
      quaternary: 2,
      risk: 'healthy' as const,
    }));
    expect(filterPortfolioRows(rows, 'brand 1')).toHaveLength(50);
    expect(filterPortfolioRows(rows, 'SKU-100')[0]?.primary).toBe(-10);
    expect(portfolioPageCount(rows.length)).toBe(3);
    expect(portfolioPageRows(rows, 2)).toHaveLength(50);
    expect(portfolioPageRows(rows, 3)).toHaveLength(1);
  });

  it('keeps unavailable actions safe and explains Contest without Focus substitution', () => {
    expect(specializedSubviewActions('unavailable')).toEqual({
      showRetailLink: true,
      showRefresh: true,
      showExport: false,
      showLayout: false,
    });
    const copy = unavailableSubviewCopy(subviewForId('campaigns', 'contest'));
    expect(copy).toContain('Retail poate avea mecanismul Concurs');
    expect(copy).toContain('head/read-model oficial eligibil');
    expect(copy).toContain('Cifrele Focus nu sunt folosite ca substitut');
  });

  it('selects the matching portfolio slice for each sales subview', () => {
    const data = { portfolio: { product: slice } } as unknown as ModuleAnalytics;
    const display = moduleSubviewData(data, subviewForId('sales', 'portfolio-product'));
    expect(display.entity_dimension).toBe('product');
    expect(display.breakdown[0]?.quaternary).toBe(3);
  });
});
