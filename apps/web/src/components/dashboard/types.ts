import type { ComponentType } from 'react';

export interface DashboardLayoutItem {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

export interface DashboardWidgetDefinition extends DashboardLayoutItem {
  title: string;
  subtitle?: string;
  component: ComponentType;
}
