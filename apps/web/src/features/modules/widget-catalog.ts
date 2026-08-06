import { type ComponentType, createElement, lazy } from 'react';

import type { DashboardWidgetDefinition } from '../../components/dashboard/types';
import type { ModuleAnalytics, ModuleId } from './schemas';
import { type ModuleSubviewId, subviewForId } from './subviews';

type ModuleWidgetName =
  | 'ModuleAlertsWidget'
  | 'ModuleBreakdownWidget'
  | 'ModuleDistributionWidget'
  | 'ModuleKpiByMetric'
  | 'ModuleMatrixWidget'
  | 'ModuleTrendWidget';

function lazyModuleWidget<Props extends object = Record<string, never>>(name: ModuleWidgetName) {
  return lazy(() =>
    import('./widgets').then((module) => ({
      default: module[name] as unknown as ComponentType<Props>,
    })),
  );
}

const ModuleAlertsWidget = lazyModuleWidget('ModuleAlertsWidget');
const ModuleBreakdownWidget = lazyModuleWidget('ModuleBreakdownWidget');
const ModuleDistributionWidget = lazyModuleWidget('ModuleDistributionWidget');
const ModuleKpiByMetric = lazyModuleWidget<{ metricId: string }>('ModuleKpiByMetric');
const ModuleMatrixWidget = lazyModuleWidget('ModuleMatrixWidget');
const ModuleTrendWidget = lazyModuleWidget('ModuleTrendWidget');

type RecipeKind =
  | 'kpi'
  | 'trend'
  | 'distribution'
  | 'portfolio-distribution'
  | 'portfolio-table'
  | 'matrix'
  | 'breakdown'
  | 'alerts'
  | 'pace'
  | 'ranking'
  | 'scatter'
  | 'histogram'
  | 'waterfall'
  | 'forecast'
  | 'calendar'
  | 'focus-ranking'
  | 'accuracy-scatter'
  | 'visits-trend'
  | 'visits-breakdown'
  | 'visits-matrix';
type MetricSlot = 'primary' | 'secondary' | 'tertiary' | 'quaternary';
interface Recipe {
  kind: RecipeKind;
  slot?: MetricSlot;
  metricId?: string;
  title?: string;
  subtitle?: string;
}

export interface ModuleWidgetQuerySpec {
  kind:
    | 'kpi'
    | 'trend'
    | 'distribution'
    | 'matrix'
    | 'breakdown'
    | 'scatter'
    | 'histogram'
    | 'waterfall'
    | 'calendar'
    | 'table';
  metricId: string;
}

const metricSlots: Record<ModuleId, Record<MetricSlot, string>> = {
  sales: {
    primary: 'sales.total',
    secondary: 'target.progress_pct',
    tertiary: 'receipts.average_value',
    quaternary: 'receipt_2plus_pct',
  },
  performance: {
    primary: 'performance.average',
    secondary: 'performance.at_target',
    tertiary: 'performance.volatility',
    quaternary: 'performance.daily_productivity',
  },
  campaigns: {
    primary: 'campaigns.focus_sales',
    secondary: 'campaigns.focus_share',
    tertiary: 'campaigns.active_stores',
    quaternary: 'campaigns.active_products',
  },
  workforce: {
    primary: 'workforce.headcount',
    secondary: 'workforce.productivity',
    tertiary: 'workforce.coverage',
    quaternary: 'workforce.stability',
  },
  compensation: {
    primary: 'compensation.payroll',
    secondary: 'compensation.average',
    tertiary: 'compensation.median',
    quaternary: 'compensation.sales_ratio',
  },
  finance: {
    primary: 'finance.revenue',
    secondary: 'finance.ebit',
    tertiary: 'finance.ebit_margin',
    quaternary: 'finance.operating_costs',
  },
  planning: {
    primary: 'planning.forecast',
    secondary: 'planning.target_gap',
    tertiary: 'planning.accuracy',
    quaternary: 'planning.actual',
  },
};

const distributionMetrics: Partial<Record<ModuleId, string>> = {
  sales: 'sales.total',
  campaigns: 'campaigns.focus_sales',
  workforce: 'workforce.headcount',
  compensation: 'compensation.payroll',
  finance: 'finance.operating_costs',
};

const matrixMetrics: Partial<Record<ModuleId, string>> = {
  sales: 'target.progress_pct',
  performance: 'performance.average',
  campaigns: 'campaigns.focus_share',
  workforce: 'workforce.productivity',
  compensation: 'compensation.payroll',
  finance: 'finance.ebit_margin',
};

export function moduleWidgetQuerySpec(
  module: ModuleId,
  widgetId: string,
): ModuleWidgetQuerySpec | null {
  if (widgetId.startsWith('kpi:')) {
    return { kind: 'kpi', metricId: widgetId.slice(4) };
  }
  if (widgetId === 'alerts') return null;
  if (widgetId === 'pace' && module === 'sales') {
    return { kind: 'kpi', metricId: 'target.progress_pct' };
  }
  if (widgetId === 'calendar' && module === 'sales') {
    return { kind: 'calendar', metricId: 'sales.total' };
  }
  if (widgetId === 'ranking' && module === 'performance') {
    return { kind: 'breakdown', metricId: 'performance.average' };
  }
  if (widgetId === 'scatter' && module === 'performance') {
    return { kind: 'scatter', metricId: 'performance.average' };
  }
  if (widgetId === 'histogram' && module === 'performance') {
    return { kind: 'histogram', metricId: 'performance.average' };
  }
  if (widgetId === 'histogram' && module === 'compensation') {
    return { kind: 'histogram', metricId: 'compensation.average' };
  }
  if (widgetId === 'waterfall' && module === 'finance') {
    return { kind: 'waterfall', metricId: 'finance.ebit' };
  }
  if (widgetId === 'forecast' && module === 'planning') {
    return { kind: 'trend', metricId: 'planning.forecast' };
  }
  if (widgetId === 'focus-ranking' && module === 'campaigns') {
    return { kind: 'breakdown', metricId: 'campaigns.focus_share' };
  }
  if (widgetId === 'accuracy-scatter' && module === 'planning') {
    return { kind: 'scatter', metricId: 'planning.forecast' };
  }
  if (widgetId === 'visits-trend') {
    return { kind: 'trend', metricId: 'visits.total' };
  }
  if (widgetId === 'visits-breakdown') {
    return { kind: 'breakdown', metricId: 'visits.total' };
  }
  if (widgetId === 'visits-matrix') {
    return { kind: 'matrix', metricId: 'visits.total' };
  }
  if (widgetId === 'distribution') {
    const metricId = distributionMetrics[module];
    return metricId ? { kind: 'distribution', metricId } : null;
  }
  if (widgetId === 'portfolio-distribution' && module === 'sales') {
    return { kind: 'distribution', metricId: 'sales.portfolio_sales' };
  }
  if (widgetId === 'portfolio-table' && module === 'sales') {
    return { kind: 'table', metricId: 'sales.portfolio_sales' };
  }
  if (widgetId === 'matrix') {
    const metricId = matrixMetrics[module];
    return metricId ? { kind: 'matrix', metricId } : null;
  }
  if (widgetId === 'trend' || widgetId === 'breakdown') {
    return { kind: widgetId, metricId: metricSlots[module].primary };
  }
  return null;
}

const recipes: Partial<Record<ModuleSubviewId, readonly Recipe[]>> = {
  pace: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    {
      kind: 'pace',
      title: 'Pace către target',
      subtitle: 'Realizat, target și gap din același snapshot.',
    },
    {
      kind: 'trend',
      title: 'Pace și repere',
      subtitle: 'Actual, comparație și target din snapshot.',
    },
    { kind: 'alerts', title: 'Semnale de date și risc' },
  ],
  trend: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'trend', title: 'Trend', subtitle: 'Serie temporală fără conectarea valorilor lipsă.' },
    { kind: 'matrix', title: 'Istoric entitate × perioadă' },
  ],
  mix: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'distribution', title: 'Mix livrat de API' },
    { kind: 'breakdown', title: 'Contribuții și diferențe' },
  ],
  'portfolio-category': [
    { kind: 'kpi', metricId: 'sales.portfolio_sales' },
    { kind: 'kpi', metricId: 'sales.portfolio_net_quantity' },
    { kind: 'portfolio-distribution', title: 'Distribuție vânzări pe categorie' },
    { kind: 'portfolio-table', title: 'Categorii', subtitle: 'Tabel local căutabil și paginat.' },
  ],
  'portfolio-subcategory': [
    { kind: 'kpi', metricId: 'sales.portfolio_sales' },
    { kind: 'kpi', metricId: 'sales.portfolio_net_quantity' },
    { kind: 'portfolio-distribution', title: 'Distribuție vânzări pe subcategorie' },
    {
      kind: 'portfolio-table',
      title: 'Subcategorii',
      subtitle: 'Tabel local căutabil și paginat.',
    },
  ],
  'portfolio-brand': [
    { kind: 'kpi', metricId: 'sales.portfolio_sales' },
    { kind: 'kpi', metricId: 'sales.portfolio_net_quantity' },
    { kind: 'kpi', metricId: 'sales.portfolio_return_quantity' },
    { kind: 'portfolio-distribution', title: 'Distribuție vânzări pe brand' },
    { kind: 'portfolio-table', title: 'Branduri', subtitle: 'Tabel local căutabil și paginat.' },
  ],
  'portfolio-product': [
    { kind: 'kpi', metricId: 'sales.portfolio_sales' },
    { kind: 'kpi', metricId: 'sales.portfolio_net_quantity' },
    { kind: 'kpi', metricId: 'sales.portfolio_return_quantity' },
    { kind: 'kpi', metricId: 'sales.portfolio_receipt_incidence' },
    {
      kind: 'portfolio-table',
      title: 'Produse / SKU',
      subtitle: 'Tabel local căutabil și paginat; fără donut SKU.',
    },
  ],
  drivers: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'breakdown', title: 'Drivers observați' },
    { kind: 'alerts', title: 'Atenție managerială' },
  ],
  transactions: [
    { kind: 'kpi', metricId: 'receipts.total' },
    { kind: 'kpi', metricId: 'receipts.average_value' },
    { kind: 'kpi', metricId: 'receipt_2plus_pct' },
    {
      kind: 'alerts',
      title: 'Contract tranzacțional agregat',
      subtitle:
        'Bonuri și volum agregat din contractul Retail; fără linii de tranzacție inventate.',
    },
  ],
  calendar: [
    {
      kind: 'calendar',
      title: 'Calendar zilnic observat',
      subtitle: 'Zilele absente rămân lipsă; retururile sunt cantități negative.',
    },
    { kind: 'trend', title: 'Evoluție lunară' },
    { kind: 'alerts', title: 'Cutoff și coverage sursă' },
  ],
  overview: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'trend', title: 'Performanță în timp' },
    { kind: 'alerts', title: 'Alerte și coverage' },
  ],
  rankings: [
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'ranking', title: 'Rankings' },
    { kind: 'matrix', title: 'Rank × perioadă' },
  ],
  consistency: [
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'trend', title: 'Consistență în timp' },
    { kind: 'matrix', title: 'Volatilitate entitate × perioadă' },
  ],
  productivity: [
    { kind: 'kpi', slot: 'quaternary' },
    { kind: 'breakdown', title: 'Productivitate' },
    { kind: 'trend', title: 'Productivitate în timp' },
  ],
  visits: [
    { kind: 'kpi', metricId: 'visits.total' },
    { kind: 'kpi', metricId: 'visits.distinct_stores' },
    { kind: 'kpi', metricId: 'visits.avg_completion' },
    { kind: 'kpi', metricId: 'visits.checklist_score' },
    { kind: 'visits-trend', title: 'Vizite în timp' },
    { kind: 'visits-breakdown', title: 'Vizite pe Team Leader autor' },
    { kind: 'visits-matrix', title: 'Team Leader × perioadă' },
  ],
  promo: [
    { kind: 'kpi', metricId: 'campaigns.promo_sales' },
    { kind: 'kpi', metricId: 'campaigns.promo_quantity' },
    { kind: 'kpi', metricId: 'campaigns.promo_discount' },
    { kind: 'kpi', metricId: 'campaigns.promo_active_stores' },
    { kind: 'kpi', metricId: 'campaigns.promo_active_products' },
    { kind: 'kpi', metricId: 'campaigns.promo_qualifying_receipts' },
    { kind: 'kpi', metricId: 'campaigns.promo_discounted_units' },
    { kind: 'trend', metricId: 'campaigns.promo_sales', title: 'Vânzări Promo în timp' },
    { kind: 'breakdown', metricId: 'campaigns.promo_sales', title: 'Promo pe magazine' },
    { kind: 'distribution', metricId: 'campaigns.promo_discount', title: 'Discount pe campanie' },
    { kind: 'matrix', metricId: 'campaigns.promo_discount', title: 'Discount magazin × perioadă' },
    { kind: 'alerts', title: 'Coverage Promo' },
  ],
  incentive: [
    { kind: 'kpi', metricId: 'campaigns.incentive_sales' },
    { kind: 'kpi', metricId: 'campaigns.incentive_quantity' },
    { kind: 'kpi', metricId: 'campaigns.incentive_reward' },
    { kind: 'kpi', metricId: 'campaigns.incentive_active_stores' },
    { kind: 'kpi', metricId: 'campaigns.incentive_active_products' },
    { kind: 'kpi', metricId: 'campaigns.incentive_qualified_quantity' },
    { kind: 'kpi', metricId: 'campaigns.incentive_eligible_quantity' },
    { kind: 'trend', metricId: 'campaigns.incentive_sales', title: 'Vânzări Incentive în timp' },
    { kind: 'breakdown', metricId: 'campaigns.incentive_sales', title: 'Incentive pe magazine' },
    {
      kind: 'distribution',
      metricId: 'campaigns.incentive_reward',
      title: 'Recompensă pe campanie',
    },
    {
      kind: 'matrix',
      metricId: 'campaigns.incentive_reward',
      title: 'Recompensă magazin × perioadă',
    },
    { kind: 'alerts', title: 'Coverage Incentive' },
  ],
  contest: [{ kind: 'alerts', title: 'Concurs indisponibil' }],
  focus: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'kpi', slot: 'quaternary' },
    { kind: 'focus-ranking', title: 'Top / Bottom magazine observate' },
    { kind: 'distribution', title: 'Focus mix' },
    { kind: 'matrix', title: 'Pondere Focus magazin × perioadă' },
  ],
  folii: [{ kind: 'alerts', title: 'Folii indisponibil' }],
  people: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'breakdown', title: 'People agregat' },
    { kind: 'matrix', title: 'Headcount în timp' },
  ],
  movements: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'breakdown', title: 'Mișcări livrate de sursă' },
    { kind: 'alerts', title: 'Coverage și lipsuri' },
  ],
  stability: [
    { kind: 'kpi', slot: 'quaternary' },
    { kind: 'trend', title: 'Stabilitate' },
    { kind: 'matrix', title: 'Stabilitate în timp' },
  ],
  coverage: [
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'breakdown', title: 'Acoperire' },
    { kind: 'matrix', title: 'Acoperire entitate × perioadă' },
  ],
  grile: [{ kind: 'alerts', title: 'Grile indisponibil' }],
  distribution: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'distribution', title: 'Distribuție agregată' },
    { kind: 'histogram', title: 'Profilul agregatelor eligibile' },
    { kind: 'breakdown', title: 'Cohorte agregate' },
  ],
  'payroll-ratios': [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'quaternary' },
    { kind: 'trend', title: 'Payroll ratios' },
    { kind: 'alerts', title: 'Suprimare și lipsuri' },
  ],
  'cost-structure': [
    { kind: 'kpi', slot: 'quaternary' },
    { kind: 'distribution', title: 'Structură costuri' },
    { kind: 'breakdown', title: 'Categorii Finance' },
  ],
  profitability: [
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'trend', title: 'Profitabilitate' },
    { kind: 'breakdown', title: 'Profit pe entitate' },
  ],
  reconciliation: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'waterfall', title: 'Venit → costuri → EBIT' },
    { kind: 'breakdown', title: 'Reconciliere' },
    { kind: 'alerts', title: 'Autoritate și warnings' },
  ],
  'break-even': [{ kind: 'alerts', title: 'Break-even indisponibil' }],
  current: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'trend', title: 'Current run' },
    { kind: 'alerts', title: 'Snapshot și coverage' },
  ],
  '12-months': [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'forecast', title: 'Forecast 12 luni' },
    { kind: 'matrix', title: 'Forecast entitate × perioadă' },
  ],
  accuracy: [
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'accuracy-scatter', title: 'Actual × forecast pe magazin' },
    { kind: 'forecast', title: 'Forecast și actual observat în timp' },
    { kind: 'alerts', title: 'Coverage actual și autoritate forecast' },
  ],
  scenarios: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'breakdown', title: 'Scenarii versionate' },
    { kind: 'alerts', title: 'Status snapshot' },
  ],
  sensitivity: [
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'matrix', title: 'Sensibilitate livrată' },
    { kind: 'alerts', title: 'Contract sensibilitate' },
  ],
};

const moduleRecipeOverrides: Partial<Record<`${ModuleId}:${ModuleSubviewId}`, readonly Recipe[]>> =
  {
    'performance:productivity': [
      { kind: 'kpi', slot: 'quaternary' },
      { kind: 'scatter', title: 'Productivitate × realizare target' },
      { kind: 'breakdown', title: 'Productivitate' },
      { kind: 'trend', title: 'Productivitate în timp' },
    ],
    'performance:consistency': [
      { kind: 'kpi', slot: 'tertiary' },
      { kind: 'histogram', title: 'Distribuția realizării targetului' },
      { kind: 'trend', title: 'Consistență în timp' },
      { kind: 'matrix', title: 'Volatilitate entitate × perioadă' },
    ],
  };

const ModulePaceWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModulePaceWidget })),
);
const ModuleRankingWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModuleRankingWidget })),
);
const ModuleProductivityScatterWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({
    default: module.ModuleProductivityScatterWidget,
  })),
);
const ModuleHistogramWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModuleHistogramWidget })),
);
const ModuleWaterfallWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModuleWaterfallWidget })),
);
const ModuleForecastWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModuleForecastWidget })),
);
const ModuleCalendarWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModuleCalendarWidget })),
);
const ModuleFocusRankingWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({ default: module.ModuleFocusRankingWidget })),
);
const ModulePlanningAccuracyWidget = lazy(() =>
  import('./specialized-widgets').then((module) => ({
    default: module.ModulePlanningAccuracyWidget,
  })),
);
const PortfolioDistributionWidget = lazy(() =>
  import('./portfolio').then((module) => ({ default: module.PortfolioDistributionWidget })),
);
const PortfolioTableWidget = lazy(() =>
  import('./portfolio').then((module) => ({ default: module.PortfolioTableWidget })),
);

const componentByKind: Record<Exclude<RecipeKind, 'kpi'>, ComponentType> = {
  trend: ModuleTrendWidget,
  distribution: ModuleDistributionWidget,
  'portfolio-distribution': PortfolioDistributionWidget,
  'portfolio-table': PortfolioTableWidget,
  matrix: ModuleMatrixWidget,
  breakdown: ModuleBreakdownWidget,
  alerts: ModuleAlertsWidget,
  pace: ModulePaceWidget,
  ranking: ModuleRankingWidget,
  scatter: ModuleProductivityScatterWidget,
  histogram: ModuleHistogramWidget,
  waterfall: ModuleWaterfallWidget,
  forecast: ModuleForecastWidget,
  calendar: ModuleCalendarWidget,
  'focus-ranking': ModuleFocusRankingWidget,
  'accuracy-scatter': ModulePlanningAccuracyWidget,
  'visits-trend': ModuleTrendWidget,
  'visits-breakdown': ModuleBreakdownWidget,
  'visits-matrix': ModuleMatrixWidget,
};

function kpiComponent(metricId: string): ComponentType {
  return () => createElement(ModuleKpiByMetric, { metricId });
}

function recipeTitle(data: ModuleAnalytics, recipe: Recipe): string {
  if (recipe.title) return recipe.title;
  const metricId =
    recipe.metricId ?? (recipe.slot ? metricSlots[data.module][recipe.slot] : undefined);
  if (metricId === 'sales.portfolio_receipt_incidence') return 'Incidențe SKU în bonuri';
  return data.kpis.find((metric) => metric.id === metricId)?.label ?? 'Metrica disponibilă';
}

export function moduleWidgets(
  data: ModuleAnalytics,
  subviewId: ModuleSubviewId = subviewForId(data.module, undefined).id,
): DashboardWidgetDefinition[] {
  const recipeList =
    moduleRecipeOverrides[`${data.module}:${subviewId}`] ??
    recipes[subviewId] ??
    recipes.overview ??
    [];
  let kpiIndex = 0;
  let bodyIndex = 0;
  const kpiCount = recipeList.filter((item) => item.kind === 'kpi').length;
  const bodyCount = recipeList.length - kpiCount;
  const kpiColumns = kpiCount > 0 ? Math.floor(24 / Math.min(4, kpiCount)) : 6;
  const definitions: DashboardWidgetDefinition[] = [];
  for (const recipe of recipeList) {
    const metricId =
      recipe.metricId ?? (recipe.slot ? metricSlots[data.module][recipe.slot] : undefined);
    const isKpi = recipe.kind === 'kpi';
    const index = isKpi ? kpiIndex++ : bodyIndex++;
    const columns = isKpi ? kpiColumns : bodyCount <= 2 ? 12 : 8;
    const x = isKpi
      ? (index % Math.max(1, 24 / kpiColumns)) * kpiColumns
      : (index % Math.max(1, 24 / columns)) * columns;
    const y = isKpi ? 0 : 5 + Math.floor(index / Math.max(1, 24 / columns)) * 14;
    const height = isKpi ? 5 : 14;
    const component =
      isKpi && metricId
        ? kpiComponent(metricId)
        : componentByKind[recipe.kind as Exclude<RecipeKind, 'kpi'>];
    if (!component) continue;
    definitions.push({
      id: isKpi && metricId ? `kpi:${metricId}` : recipe.kind,
      title: recipeTitle(data, recipe),
      subtitle: recipe.subtitle ?? subviewForId(data.module, subviewId).description,
      component,
      x,
      y,
      w: columns,
      h: height,
      minW: isKpi ? 4 : Math.min(columns, 8),
      minH: isKpi ? 4 : 9,
    });
  }
  return definitions;
}
