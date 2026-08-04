import type { DashboardCreateInput, DashboardWidget } from './schemas';

function widget(id: string, module: DashboardWidget['module'], title: string, metricId: string, visualization: DashboardWidget['visualization'], x: number, y: number, w: number, h: number): DashboardWidget {
  return { id, module, title, metric_id: metricId, visualization, dimension: null, time_grain: 'month', filter_mode: 'inherit', filters: {}, options: {}, layout: { x, y, w, h, min_w: Math.min(w, 4), min_h: Math.min(h, 4) } };
}

export interface DashboardTemplate extends DashboardCreateInput {
  id: string;
  requiredCapabilities: string[];
}

export const dashboardTemplates: DashboardTemplate[] = [
  {
    id: 'director',
    name: 'Director comercial',
    description: 'Vânzări, target, performanță, forecast și risc într-un singur cockpit.',
    visibility: 'private',
    requiredCapabilities: ['insight:analytics', 'insight:management'],
    widgets: [
      widget('director-sales', 'sales', 'Vânzări', 'sales.total', 'kpi', 0, 0, 6, 5),
      widget('director-target', 'sales', 'Realizare target', 'target.progress_pct', 'kpi', 6, 0, 6, 5),
      widget('director-forecast', 'planning', 'Forecast', 'planning.forecast', 'kpi', 12, 0, 6, 5),
      widget('director-risk', 'performance', 'Risc comercial', 'performance.average', 'kpi', 18, 0, 6, 5),
      widget('director-trend', 'sales', 'Evoluție vânzări', 'sales.total', 'area', 0, 5, 14, 13),
      widget('director-performance', 'performance', 'Magazine prioritare', 'performance.average', 'table', 14, 5, 10, 13),
    ],
  },
  {
    id: 'regional',
    name: 'Regional Manager',
    description: 'Pace, magazine, stabilitate și campanii pentru management regional.',
    visibility: 'private',
    requiredCapabilities: ['insight:analytics'],
    widgets: [
      widget('rm-sales', 'sales', 'Vânzări', 'sales.total', 'kpi', 0, 0, 8, 5),
      widget('rm-performance', 'performance', 'Realizare', 'performance.average', 'kpi', 8, 0, 8, 5),
      widget('rm-focus', 'campaigns', 'Focus', 'campaigns.focus_sales', 'kpi', 16, 0, 8, 5),
      widget('rm-matrix', 'performance', 'Matrice magazine', 'performance.average', 'heatmap', 0, 5, 12, 13),
      widget('rm-ranking', 'performance', 'Clasament', 'performance.average', 'table', 12, 5, 12, 13),
    ],
  },
  {
    id: 'finance',
    name: 'Finance',
    description: 'Venit, EBIT, costuri și trend de profitabilitate.',
    visibility: 'private',
    requiredCapabilities: ['insight:pnl'],
    widgets: [
      widget('fin-revenue', 'finance', 'Venit net', 'finance.revenue', 'kpi', 0, 0, 8, 5),
      widget('fin-ebit', 'finance', 'EBIT', 'finance.ebit', 'kpi', 8, 0, 8, 5),
      widget('fin-margin', 'finance', 'Marjă EBIT', 'finance.ebit_margin', 'kpi', 16, 0, 8, 5),
      widget('fin-trend', 'finance', 'Trend P&L', 'finance.revenue', 'line', 0, 5, 15, 13),
      widget('fin-cost', 'finance', 'Structură costuri', 'finance.operating_costs', 'donut', 15, 5, 9, 13),
    ],
  },
  {
    id: 'risk',
    name: 'Magazine în risc',
    description: 'Performanță, volatilitate, personal și semnale care cer intervenție.',
    visibility: 'private',
    requiredCapabilities: ['insight:management'],
    widgets: [
      widget('risk-performance', 'performance', 'Realizare medie', 'performance.average', 'kpi', 0, 0, 8, 5),
      widget('risk-volatility', 'performance', 'Volatilitate', 'performance.volatility', 'kpi', 8, 0, 8, 5),
      widget('risk-stability', 'workforce', 'Stabilitate', 'workforce.stability', 'kpi', 16, 0, 8, 5),
      widget('risk-matrix', 'performance', 'Heatmap risc', 'performance.average', 'heatmap', 0, 5, 12, 13),
      widget('risk-table', 'performance', 'Entități prioritare', 'performance.average', 'table', 12, 5, 12, 13),
    ],
  },
];

export const moduleMetrics: Record<DashboardWidget['module'], Array<{ id: string; label: string }>> = {
  sales: [{ id: 'sales.total', label: 'Vânzări' }, { id: 'target.progress_pct', label: 'Realizare target' }, { id: 'receipts.average_value', label: 'Valoare medie bon' }, { id: 'receipt_2plus_pct', label: 'Bonuri 2+' }],
  performance: [{ id: 'performance.average', label: 'Realizare medie' }, { id: 'performance.at_target', label: 'Entități la target' }, { id: 'performance.volatility', label: 'Volatilitate' }, { id: 'performance.daily_productivity', label: 'Productivitate' }],
  campaigns: [{ id: 'campaigns.focus_sales', label: 'Vânzări Focus' }, { id: 'campaigns.focus_share', label: 'Pondere Focus' }, { id: 'campaigns.active_stores', label: 'Magazine active' }, { id: 'campaigns.active_products', label: 'Produse active' }],
  workforce: [{ id: 'workforce.headcount', label: 'Headcount' }, { id: 'workforce.productivity', label: 'Productivitate' }, { id: 'workforce.coverage', label: 'Acoperire' }, { id: 'workforce.stability', label: 'Stabilitate' }],
  compensation: [{ id: 'compensation.payroll', label: 'Cost salarial' }, { id: 'compensation.average', label: 'Salariu mediu' }, { id: 'compensation.median', label: 'Salariu median' }, { id: 'compensation.sales_ratio', label: 'Cost / vânzări' }],
  finance: [{ id: 'finance.revenue', label: 'Venit net' }, { id: 'finance.ebit', label: 'EBIT' }, { id: 'finance.ebit_margin', label: 'Marjă EBIT' }, { id: 'finance.operating_costs', label: 'Cost operațional' }],
  planning: [{ id: 'planning.forecast', label: 'Forecast' }, { id: 'planning.target_gap', label: 'Gap target' }, { id: 'planning.accuracy', label: 'Acuratețe' }, { id: 'planning.actual', label: 'Actual' }],
};

export const compatibleVisualizations: DashboardWidget['visualization'][] = ['kpi', 'line', 'area', 'bar', 'donut', 'heatmap', 'scatter', 'waterfall', 'table'];
