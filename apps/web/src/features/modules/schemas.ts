import { z } from 'zod';

import { sourceMetadataSchema } from '../../lib/analytics-contracts';
import { capabilities } from '../identity/schemas';

const numeric = z.coerce.number();
export const nullableNumeric = z.union([z.null(), numeric]);
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
  'histogram',
  'boxplot',
  'treemap',
  'calendar',
  'forecast-band',
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
    analytical_snapshot_id: z.string().nullable().optional(),
    snapshot_contract_version: z.number().int().optional(),
    sources: z.record(z.string(), sourceMetadataSchema).optional(),
    range_start: z.string().nullable().optional(),
    range_end: z.string().nullable().optional(),
    requested_comparisons: z.array(z.string()).optional(),
    warnings: z.array(z.string()).optional(),
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
      comparisons: z.record(z.string(), nullableNumeric).default({}),
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
  calendar: z
    .array(
      z.object({
        date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
        sales: numeric,
        net_quantity: numeric,
        positive_quantity: numeric,
        return_quantity: numeric,
        receipt_count: numeric,
        receipt_2plus_count: numeric,
        observed_store_count: z.coerce.number().int().positive(),
        coverage_state: z.literal('observed'),
      }),
    )
    .default([]),
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
