import { type ComponentType, createElement } from 'react';

import type { DashboardWidgetDefinition } from '../../components/dashboard/types';
import type { ModuleAnalytics, ModuleId } from './schemas';
import { type ModuleSubviewId, subviewForId } from './subviews';
import {
  ModuleAlertsWidget,
  ModuleBreakdownWidget,
  ModuleDistributionWidget,
  ModuleKpiByMetric,
  ModuleMatrixWidget,
  ModuleTrendWidget,
} from './widgets';

type RecipeKind = 'kpi' | 'trend' | 'distribution' | 'matrix' | 'breakdown' | 'alerts';
type MetricSlot = 'primary' | 'secondary' | 'tertiary' | 'quaternary';
interface Recipe {
  kind: RecipeKind;
  slot?: MetricSlot;
  title?: string;
  subtitle?: string;
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

const recipes: Partial<Record<ModuleSubviewId, readonly Recipe[]>> = {
  pace: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
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
  drivers: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'breakdown', title: 'Drivers observați' },
    { kind: 'alerts', title: 'Atenție managerială' },
  ],
  transactions: [
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'kpi', slot: 'quaternary' },
    { kind: 'breakdown', title: 'Tranzacții / volum disponibil' },
    { kind: 'distribution', title: 'Distribuție volum' },
  ],
  calendar: [
    { kind: 'matrix', title: 'Calendar / acoperire temporală' },
    { kind: 'trend', title: 'Evoluție pe interval' },
    { kind: 'breakdown', title: 'Detaliu perioade' },
  ],
  overview: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'trend', title: 'Performanță în timp' },
    { kind: 'alerts', title: 'Alerte și coverage' },
  ],
  rankings: [
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'breakdown', title: 'Rankings' },
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
    { kind: 'kpi', slot: 'primary' },
    { kind: 'breakdown', title: 'Vizite / acoperire disponibilă' },
    { kind: 'matrix', title: 'Vizite pe perioadă' },
  ],
  promo: [{ kind: 'alerts', title: 'Promo indisponibil' }],
  incentive: [{ kind: 'alerts', title: 'Incentive indisponibil' }],
  contest: [{ kind: 'alerts', title: 'Concurs indisponibil' }],
  focus: [
    { kind: 'kpi', slot: 'primary' },
    { kind: 'kpi', slot: 'secondary' },
    { kind: 'distribution', title: 'Focus mix' },
    { kind: 'breakdown', title: 'Focus pe magazine' },
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
    { kind: 'trend', title: 'Forecast 12 luni' },
    { kind: 'matrix', title: 'Forecast entitate × perioadă' },
  ],
  accuracy: [
    { kind: 'kpi', slot: 'tertiary' },
    { kind: 'trend', title: 'Acuratețe' },
    { kind: 'breakdown', title: 'Acuratețe pe entitate' },
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

const componentByKind: Record<Exclude<RecipeKind, 'kpi'>, ComponentType> = {
  trend: ModuleTrendWidget,
  distribution: ModuleDistributionWidget,
  matrix: ModuleMatrixWidget,
  breakdown: ModuleBreakdownWidget,
  alerts: ModuleAlertsWidget,
};

function kpiComponent(metricId: string): ComponentType {
  return () => createElement(ModuleKpiByMetric, { metricId });
}

function recipeTitle(data: ModuleAnalytics, recipe: Recipe): string {
  if (recipe.title) return recipe.title;
  const metricId = recipe.slot ? metricSlots[data.module][recipe.slot] : undefined;
  return data.kpis.find((metric) => metric.id === metricId)?.label ?? 'Metrica disponibilă';
}

export function moduleWidgets(
  data: ModuleAnalytics,
  subviewId: ModuleSubviewId = subviewForId(data.module, undefined).id,
): DashboardWidgetDefinition[] {
  const recipeList = recipes[subviewId] ?? recipes.overview ?? [];
  let kpiIndex = 0;
  let bodyIndex = 0;
  const definitions: DashboardWidgetDefinition[] = [];
  for (const recipe of recipeList) {
    const metricId = recipe.slot ? metricSlots[data.module][recipe.slot] : undefined;
    const isKpi = recipe.kind === 'kpi';
    const index = isKpi ? kpiIndex++ : bodyIndex++;
    const columns = isKpi
      ? 6
      : recipeList.filter((item) => item.kind !== 'kpi').length <= 2
        ? 12
        : 8;
    const x = isKpi ? (index % 4) * 6 : (index % Math.max(1, 24 / columns)) * columns;
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
