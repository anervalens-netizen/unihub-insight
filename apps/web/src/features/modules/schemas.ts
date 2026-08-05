import { z } from 'zod';

import { capabilities } from '../identity/schemas';

const numeric = z.coerce.number();
const nullableNumeric = z.union([numeric, z.null()]);
export const moduleIds = [
  'sales',
  'performance',
  'campaigns',
  'workforce',
  'compensation',
  'finance',
  'planning',
] as const;
export type ModuleId = (typeof moduleIds)[number];
export const chartKinds = [
  'line',
  'area',
  'bar',
  'stacked-bar',
  'donut',
  'heatmap',
  'scatter',
  'waterfall',
  'table',
  'kpi',
] as const;
export type ChartKind = (typeof chartKinds)[number];
const units = ['currency', 'percent', 'integer', 'decimal'] as const;
const risk = z.enum(['healthy', 'watch', 'risk']);

const kpiSchema = z.object({
  id: z.string(),
  label: z.string(),
  value: numeric,
  unit: z.enum(units),
  delta_pct: nullableNumeric.optional(),
  delta_label: z.string().nullable().optional(),
  risk,
  supporting_value: nullableNumeric.optional(),
  supporting_label: z.string().nullable().optional(),
});

export const moduleAnalyticsSchema = z.object({
  meta: z.object({
    period: z.string(),
    comparison: z.enum(['previous-month', 'previous-year', 'none']),
    as_of: z.string().nullable(),
    is_final: z.boolean(),
    data_mode: z.enum(['demo', 'postgres']),
    currency: z.string(),
    scope_label: z.string(),
    generated_at: z.string(),
    source: z.string(),
  }),
  module: z.enum(moduleIds),
  title: z.string(),
  description: z.string(),
  required_capability: z.enum(capabilities),
  axes: z.array(z.object({ key: z.string(), label: z.string(), unit: z.enum(units) })),
  supported_charts: z.array(z.enum(chartKinds)),
  kpis: z.array(kpiSchema),
  trend: z.array(
    z.object({
      key: z.string(),
      label: z.string(),
      primary: nullableNumeric,
      comparison: nullableNumeric.optional(),
      target: nullableNumeric.optional(),
      secondary: nullableNumeric.optional(),
      is_estimate: z.boolean(),
    }),
  ),
  distribution: z.array(
    z.object({ id: z.string(), label: z.string(), value: numeric, share_pct: numeric }),
  ),
  breakdown: z.array(
    z.object({
      id: z.string(),
      label: z.string(),
      context: z.string(),
      primary: numeric,
      secondary: nullableNumeric.optional(),
      tertiary: nullableNumeric.optional(),
      progress_pct: nullableNumeric.optional(),
      delta_pct: nullableNumeric.optional(),
      risk,
    }),
  ),
  matrix: z.array(
    z.object({
      x: z.string(),
      y: z.string(),
      value: numeric,
      label: z.string().nullable().optional(),
      risk,
    }),
  ),
  alerts: z.array(
    z.object({
      id: z.string(),
      severity: z.enum(['info', 'warning', 'critical']),
      title: z.string(),
      description: z.string(),
      entity_label: z.string().nullable().optional(),
    }),
  ),
});

export type ModuleAnalytics = z.infer<typeof moduleAnalyticsSchema>;
export type ModuleKpi = z.infer<typeof kpiSchema>;
export type BreakdownRow = ModuleAnalytics['breakdown'][number];
