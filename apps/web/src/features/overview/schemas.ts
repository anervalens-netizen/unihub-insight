import { z } from 'zod';

const number = z.coerce.number();
const nullableNumber = z.union([number, z.null()]);

export const filterStoreSchema = z.object({
  site_code: z.string(),
  label: z.string(),
  firm: z.string(),
  regional: z.string(),
  asm: z.string().nullable().optional(),
});

export const filterAgentSchema = z.object({
  name: z.string(),
  site_code: z.string(),
  firm: z.string(),
  regional: z.string(),
  asm: z.string().nullable().optional(),
});

export const filterOptionsSchema = z.object({
  periods: z.array(z.string()),
  firms: z.array(z.string()),
  regionals: z.array(z.string()),
  asms: z.array(z.string()),
  stores: z.array(filterStoreSchema),
  agents: z.array(filterAgentSchema),
  data_mode: z.enum(['demo', 'postgres']),
});

export type FilterOptions = z.infer<typeof filterOptionsSchema>;
export type FilterStore = z.infer<typeof filterStoreSchema>;
export type FilterAgent = z.infer<typeof filterAgentSchema>;

const riskSchema = z.enum(['healthy', 'watch', 'risk']);

const kpiSchema = z.object({
  id: z.string(),
  label: z.string(),
  value: number,
  unit: z.enum(['currency', 'percent', 'integer', 'decimal']),
  delta_pct: nullableNumber.optional(),
  delta_label: z.string().nullable().optional(),
  risk: riskSchema,
  supporting_value: nullableNumber.optional(),
  supporting_label: z.string().nullable().optional(),
});

const dailyPointSchema = z.object({
  day: z.number().int().min(1).max(31),
  sales: nullableNumber,
  target_pace: number,
  forecast: nullableNumber.optional(),
  comparison: nullableNumber.optional(),
});

const dimensionShareSchema = z.object({
  id: z.string(),
  label: z.string(),
  value: number,
  share_pct: number,
});

const performanceRowSchema = z.object({
  id: z.string(),
  label: z.string(),
  context: z.string(),
  sales: number,
  target: number,
  progress_pct: nullableNumber,
  delta_pct: nullableNumber.optional(),
  risk: riskSchema,
});

const alertSchema = z.object({
  id: z.string(),
  severity: z.enum(['info', 'warning', 'critical']),
  title: z.string(),
  description: z.string(),
  entity_label: z.string().nullable().optional(),
});

export const overviewSchema = z.object({
  meta: z.object({
    period: z.string(),
    comparison: z.enum(['previous-month', 'previous-year', 'none']),
    as_of: z.string().nullable(),
    is_final: z.boolean(),
    data_mode: z.enum(['demo', 'postgres']),
    currency: z.literal('RON'),
    scope_label: z.string(),
    generated_at: z.string(),
    source: z.string(),
  }),
  kpis: z.array(kpiSchema),
  daily: z.array(dailyPointSchema),
  contribution: z.array(dimensionShareSchema),
  performance: z.array(performanceRowSchema),
  alerts: z.array(alertSchema),
});

export type Overview = z.infer<typeof overviewSchema>;
export type KpiMetric = z.infer<typeof kpiSchema>;
export type PerformanceRow = z.infer<typeof performanceRowSchema>;
