import { z } from 'zod';

import { sourceMetadataSchema } from '../../lib/analytics-contracts';
import { chartKinds, moduleIds } from '../modules/schemas';

const chartKindSchema = z.enum(chartKinds);
const capabilitySchema = z.enum([
  'insight:analytics',
  'insight:management',
  'insight:hr',
  'insight:pnl',
  'insight:admin',
]);
const metricUnitSchema = z.enum(['currency', 'percent', 'integer', 'decimal']);
const queryComparisonSchema = z.enum([
  'target',
  'forecast',
  'previous-period',
  'previous-year',
  'recent-average',
]);
const filterValueSchema = z.union([z.string(), z.array(z.string())]);
const datasetValueSchema = z.union([z.string(), z.number(), z.boolean(), z.null()]);

export const metricDefinitionSchema = z.object({
  id: z.string(),
  version: z.number().int(),
  display_name: z.string(),
  description: z.string(),
  unit: metricUnitSchema,
  aggregation: z.string(),
  allowed_dimensions: z.array(z.string()),
  allowed_grains: z.array(z.string()),
  comparison_policy: z.string(),
  missing_policy: z.string(),
  required_capability: capabilitySchema,
  formula_reference: z.string(),
  allowed_shapes: z.array(chartKindSchema),
  suppressible: z.boolean(),
  source_authority: z.string(),
  query_contract_version: z.number().int(),
  effective_from: z.string().nullable(),
  effective_to: z.string().nullable(),
});

export const dimensionDefinitionSchema = z.object({
  id: z.string(),
  version: z.number().int(),
  display_name: z.string(),
  description: z.string(),
  stable_key: z.string(),
  allowed_grains: z.array(z.string()),
  required_capability: capabilitySchema,
  source_authority: z.string(),
});

export const queryContractSchema = z.object({
  version: z.number().int(),
  max_widgets: z.number().int(),
  max_dimensions: z.number().int(),
  max_rows: z.number().int(),
  default_deadline_ms: z.number().int(),
  supported_grains: z.array(z.string()),
});

export const analyticsCatalogSchema = z.object({
  version: z.number().int(),
  metrics: z.array(metricDefinitionSchema),
  dimensions: z.array(dimensionDefinitionSchema),
  query_contract: queryContractSchema,
});

export const queryTimeRangeSchema = z.object({
  start: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/),
  end: z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/),
});

export const querySortSchema = z.object({
  field: z.string().min(1).max(100),
  direction: z.enum(['asc', 'desc']),
});

export const widgetQuerySchema = z.object({
  widget_id: z.string().min(1).max(100),
  module: z.enum(moduleIds),
  metric_id: z.string().min(1).max(160),
  metric_version: z.number().int().default(1),
  query_contract_version: z.number().int().default(1),
  dimensions: z.array(z.string()).default([]),
  time_range: queryTimeRangeSchema.nullable().default(null),
  time_grain: z.enum(['day', 'week', 'month', 'quarter', 'year']).default('month'),
  filters: z.record(z.string(), filterValueSchema).default({}),
  comparisons: z.array(queryComparisonSchema).default([]),
  sort: z.array(querySortSchema).default([]),
  limit: z.number().int().default(30),
  visualization: chartKindSchema.default('table'),
});

export const queryBatchRequestSchema = z.object({
  snapshot_id: z.string().max(160).nullable().optional(),
  dashboard_id: z.string().max(100).nullable().optional(),
  widgets: z.array(widgetQuerySchema).min(1).max(12),
});

export const datasetDimensionSchema = z.object({
  id: z.string(),
  label: z.string(),
  kind: z.enum(['string', 'number', 'integer', 'boolean', 'time']),
  role: z.enum(['key', 'label', 'value', 'comparison', 'target', 'metadata']).default('value'),
});

export const queryDatasetSchema = z.object({
  dimensions: z.array(datasetDimensionSchema),
  rows: z.array(z.record(z.string(), datasetValueSchema)),
});

export const analyticalSnapshotSchema = z.object({
  id: z.string(),
  contract_version: z.number().int(),
  period: z.string(),
  resolved_at: z.string(),
  sources: z.record(z.string(), sourceMetadataSchema),
});

export const queryExecutionMetaSchema = z.object({
  period: z.string(),
  scope_label: z.string(),
  snapshot_id: z.string(),
  source: sourceMetadataSchema,
  sources: z.record(z.string(), sourceMetadataSchema).default({}),
  metric_id: z.string(),
  metric_version: z.number().int(),
  query_contract_version: z.number().int(),
  generated_at: z.string(),
  warnings: z.array(z.string()),
});

export const queryErrorSchema = z.object({
  code: z.enum(['invalid-query', 'unavailable', 'unauthorized', 'deadline-exceeded', 'internal']),
  message: z.string(),
  retryable: z.boolean(),
});

export const widgetQueryResultSchema = z
  .object({
    widget_id: z.string(),
    query: widgetQuerySchema,
    dataset: queryDatasetSchema.nullable(),
    meta: queryExecutionMetaSchema.nullable(),
    error: queryErrorSchema.nullable(),
  })
  .superRefine((value, context) => {
    if ((value.dataset === null) === (value.error === null)) {
      context.addIssue({ code: 'custom', message: 'Exactly one of dataset or error is required.' });
    }
  });

export const queryBatchResponseSchema = z.object({
  snapshot: analyticalSnapshotSchema,
  results: z.array(widgetQueryResultSchema),
  deadline_ms: z.number().int(),
  generated_at: z.string(),
});

export const inspectRequestSchema = z.object({
  snapshot_id: z.string(),
  dashboard_id: z.string().nullable().optional(),
  query: widgetQuerySchema,
  page: z.number().int().default(1),
  page_size: z.number().int().default(100),
});

export const inspectResponseSchema = z.object({
  snapshot: analyticalSnapshotSchema,
  query: widgetQuerySchema,
  dataset: queryDatasetSchema,
  page: z.number().int(),
  page_size: z.number().int(),
  total_rows: z.number().int(),
  generated_at: z.string(),
});

export type AnalyticsCatalog = z.infer<typeof analyticsCatalogSchema>;
export type MetricDefinition = z.infer<typeof metricDefinitionSchema>;
export type QueryContract = z.infer<typeof queryContractSchema>;
export type DatasetDimension = z.infer<typeof datasetDimensionSchema>;
export type DatasetValue = z.infer<typeof datasetValueSchema>;
export type QueryDataset = z.infer<typeof queryDatasetSchema>;
export type WidgetQuery = z.infer<typeof widgetQuerySchema>;
export type QueryBatchRequest = z.infer<typeof queryBatchRequestSchema>;
export type QueryBatchResponse = z.infer<typeof queryBatchResponseSchema>;
export type WidgetQueryResult = z.infer<typeof widgetQueryResultSchema>;
export type QueryExecutionMeta = z.infer<typeof queryExecutionMetaSchema>;
export type QueryError = z.infer<typeof queryErrorSchema>;
export type InspectRequest = z.infer<typeof inspectRequestSchema>;
export type InspectResponse = z.infer<typeof inspectResponseSchema>;
