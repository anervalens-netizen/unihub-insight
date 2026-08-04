import {
  BadgeDollarSign,
  ChartNoAxesCombined,
  Gauge,
  LayoutDashboard,
  Megaphone,
  SlidersHorizontal,
  Sparkles,
  UsersRound,
} from 'lucide-react';

export const navigationItems = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/sales', label: 'Sales', icon: ChartNoAxesCombined },
  { to: '/performance', label: 'Performance', icon: Gauge },
  { to: '/campaigns', label: 'Campaigns', icon: Megaphone },
  { to: '/workforce', label: 'Workforce', icon: UsersRound },
  { to: '/finance', label: 'Finance', icon: BadgeDollarSign },
  { to: '/planning', label: 'Planning', icon: Sparkles },
  { to: '/dashboards', label: 'Custom', icon: SlidersHorizontal },
] as const;

export const moduleMetadata = {
  '/': {
    title: 'Executive Overview',
    description: 'Business health, pace, risc și priorități într-un singur ecran.',
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
    description: 'Promo, Incentive, Concurs, Focus și Folii premium.',
  },
  '/workforce': {
    title: 'Workforce',
    description: 'Headcount, stabilitate, productivitate, Grile și compensații.',
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
