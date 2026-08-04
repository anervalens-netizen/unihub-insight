import { z } from 'zod';

import { chartKinds, moduleIds } from '../modules/schemas';

export const filterModes = ['inherit', 'augment', 'override', 'ignore'] as const;
export const visibilityModes = ['private', 'shared'] as const;

const optionValue = z.union([z.string(), z.number(), z.boolean()]);
export const dashboardWidgetSchema = z.object({
  id: z.string(),
  module: z.enum(moduleIds),
  title: z.string(),
  metric_id: z.string(),
  visualization: z.enum(chartKinds),
  dimension: z.string().nullable().optional(),
  time_grain: z.string(),
  filter_mode: z.enum(filterModes),
  filters: z.record(z.string(), z.string()),
  options: z.record(z.string(), optionValue),
  layout: z.object({ x: z.number().int(), y: z.number().int(), w: z.number().int(), h: z.number().int(), min_w: z.number().int(), min_h: z.number().int() }),
});

export const dashboardDocumentSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  owner_subject: z.string(),
  visibility: z.enum(visibilityModes),
  version: z.number().int(),
  widgets: z.array(dashboardWidgetSchema),
  created_at: z.string(),
  updated_at: z.string(),
});

export const dashboardListSchema = z.object({ items: z.array(dashboardDocumentSchema) });
export type DashboardWidget = z.infer<typeof dashboardWidgetSchema>;
export type DashboardDocument = z.infer<typeof dashboardDocumentSchema>;
export type DashboardCreateInput = Pick<DashboardDocument, 'name' | 'description' | 'visibility' | 'widgets'>;
export type DashboardUpdateInput = DashboardCreateInput & { version: number };
