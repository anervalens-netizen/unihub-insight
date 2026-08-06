import { z } from 'zod';

import { chartKinds, moduleIds } from '../modules/schemas';

export const filterModes = ['inherit', 'augment', 'override', 'ignore'] as const;
export const visibilityModes = ['private', 'shared'] as const;
export const dashboardPermissions = ['read', 'edit', 'admin'] as const;
export type DashboardPermission = (typeof dashboardPermissions)[number];

const dashboardAclEntrySchema = z.object({
  subject: z.string(),
  permission: z.enum(dashboardPermissions),
});

const dashboardWidgetOptionsSchema = z
  .object({
    show_legend: z.boolean().optional(),
    show_labels: z.boolean().optional(),
    top_n: z.number().int().positive().optional(),
    renderer: z.literal('canvas').optional(),
    smooth: z.boolean().optional(),
    stacked: z.boolean().optional(),
    pixel_ratio: z.union([z.literal(1), z.literal(2)]).optional(),
  })
  .strict();
export const dashboardWidgetSchema = z.object({
  id: z.string(),
  module: z.enum(moduleIds),
  title: z.string(),
  metric_id: z.string(),
  metric_version: z.number().int().default(1),
  query_contract_version: z.number().int().default(1),
  visualization: z.enum(chartKinds),
  dimension: z.string().nullable().optional(),
  dimensions: z.array(z.string()).max(2).default([]),
  time_grain: z.string().default('month'),
  comparisons: z.array(z.string()).default([]),
  sort: z.array(z.string()).default([]),
  limit: z.number().int().default(30),
  filter_mode: z.enum(filterModes).default('inherit'),
  filters: z.record(z.string(), z.string()).default({}),
  options: dashboardWidgetOptionsSchema.default({}),
  layout: z.object({
    x: z.number().int(),
    y: z.number().int(),
    w: z.number().int(),
    h: z.number().int(),
    min_w: z.number().int(),
    min_h: z.number().int(),
  }),
});

export const dashboardDocumentSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  owner_subject: z.string(),
  visibility: z.enum(visibilityModes),
  version: z.number().int(),
  widgets: z.array(dashboardWidgetSchema),
  acl: z.array(dashboardAclEntrySchema).default([]),
  scope_ceiling: z
    .object({
      firms: z.array(z.string()).default([]),
      regionals: z.array(z.string()).default([]),
      asms: z.array(z.string()).default([]),
      stores: z.array(z.string()).default([]),
      allow_agent: z.boolean().default(true),
    })
    .default({ firms: [], regionals: [], asms: [], stores: [], allow_agent: true }),
  query_contract_version: z.number().int().default(1),
  created_at: z.string(),
  updated_at: z.string(),
});

export const dashboardListSchema = z.object({ items: z.array(dashboardDocumentSchema) });
export const dashboardSubjectSchema = z.object({
  subject: z.string(),
  email: z.string().nullable().optional(),
  display_name: z.string().nullable().optional(),
  last_seen_at: z.string(),
});
export const dashboardSubjectsSchema = z.array(dashboardSubjectSchema);
export const filterPresetSchema = z.object({
  id: z.string(),
  owner_subject: z.string(),
  name: z.string(),
  filters: z.record(z.string(), z.string()),
  shared: z.boolean(),
  version: z.number().int(),
  created_at: z.string(),
  updated_at: z.string(),
});
export const filterPresetsSchema = z.array(filterPresetSchema);
export type DashboardWidget = z.infer<typeof dashboardWidgetSchema>;
export type DashboardDocument = z.infer<typeof dashboardDocumentSchema>;
export type DashboardSubject = z.infer<typeof dashboardSubjectSchema>;
export type DashboardAclEntry = z.infer<typeof dashboardAclEntrySchema>;
export type FilterPreset = z.infer<typeof filterPresetSchema>;
export type FilterPresetInput = Pick<FilterPreset, 'name' | 'filters' | 'shared'>;
export type FilterPresetUpdateInput = FilterPresetInput & { version: number };

export function dashboardWidgetDimensions(widget: DashboardWidget): string[] {
  if (widget.dimensions.length > 0) return widget.dimensions;
  return widget.dimension ? [widget.dimension] : [];
}
export type DashboardCreateInput = Pick<
  DashboardDocument,
  'name' | 'description' | 'visibility' | 'widgets'
> &
  Partial<Pick<DashboardDocument, 'acl' | 'scope_ceiling' | 'query_contract_version'>>;
export type DashboardUpdateInput = DashboardCreateInput & { version: number };
