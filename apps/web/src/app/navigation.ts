import {
  BadgeDollarSign,
  ChartNoAxesCombined,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  Megaphone,
  SlidersHorizontal,
  Sparkles,
  UsersRound,
  WalletCards,
} from 'lucide-react';

import type { Capability } from '../features/identity/schemas';

export const navigationItems = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, capability: 'insight:analytics' },
  {
    to: '/monthly-review',
    label: 'Raport lunar',
    icon: ClipboardList,
    capability: 'insight:analytics',
  },
  { to: '/sales', label: 'Sales', icon: ChartNoAxesCombined, capability: 'insight:analytics' },
  { to: '/performance', label: 'Performance', icon: Gauge, capability: 'insight:analytics' },
  { to: '/campaigns', label: 'Campaigns', icon: Megaphone, capability: 'insight:analytics' },
  { to: '/workforce', label: 'Workforce', icon: UsersRound, capability: 'insight:analytics' },
  {
    to: '/compensation',
    label: 'Compensation',
    icon: WalletCards,
    capability: 'insight:analytics',
  },
  { to: '/finance', label: 'Finance', icon: BadgeDollarSign, capability: 'insight:analytics' },
  { to: '/planning', label: 'Planning', icon: Sparkles, capability: 'insight:analytics' },
  { to: '/dashboards', label: 'Custom', icon: SlidersHorizontal, capability: 'insight:analytics' },
] as const satisfies ReadonlyArray<{
  to:
    | '/'
    | '/monthly-review'
    | '/sales'
    | '/performance'
    | '/campaigns'
    | '/workforce'
    | '/compensation'
    | '/finance'
    | '/planning'
    | '/dashboards';
  label: string;
  icon: typeof LayoutDashboard;
  capability: Capability;
}>;

export const moduleMetadata = {
  '/': {
    title: 'Executive Overview',
    description: 'Business health, pace, risc și priorități într-un singur ecran.',
  },
  '/monthly-review': {
    title: 'Raport lunar',
    description: 'Raport managerial complet: YoY, MoM, istoric recent și export Excel.',
  },
  '/sales': {
    title: 'Sales Intelligence',
    description: 'Pace, trend, mix, tranzacții și calendar comercial.',
  },
  '/performance': {
    title: 'Performance',
    description: 'Rețea, RM, ASM, magazin și agent cu drill-down coerent.',
  },
  '/campaigns': {
    title: 'Campaigns',
    description: 'Focus și mecanisme comerciale peste aceeași sursă de adevăr.',
  },
  '/workforce': {
    title: 'Workforce',
    description: 'Headcount, stabilitate, productivitate, acoperire și Grile.',
  },
  '/compensation': {
    title: 'Compensation',
    description: 'Cost salarial, distribuție și relația cu performanța.',
  },
  '/finance': {
    title: 'Finance & P&L',
    description: 'Venit, cost, profit, marjă, reconciliere și profitabilitate.',
  },
  '/planning': {
    title: 'Planning',
    description: 'Forecast, target, scenarii și acuratețe în timp.',
  },
  '/dashboards': {
    title: 'Custom Dashboards',
    description: 'Template-uri, layouturi personale și preseturi partajabile.',
  },
} as const;
