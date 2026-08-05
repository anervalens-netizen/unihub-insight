import { z } from 'zod';

export const sourceDomainSchema = z.enum([
  'sales',
  'campaigns',
  'workforce',
  'compensation',
  'visits',
  'finance',
  'planning',
  'grile',
]);

export const sourceStatusSchema = z.enum(['official', 'partial', 'stale', 'unavailable']);

export const sourceMetadataSchema = z.object({
  domain: sourceDomainSchema,
  source: z.string(),
  period: z.string(),
  cutoff: z.string().nullable(),
  as_of: z.string().nullable(),
  is_final: z.boolean(),
  coverage_numerator: z.number().int().nullable(),
  coverage_denominator: z.number().int().nullable(),
  source_generation: z.string().nullable(),
  authority: z.string(),
  authority_head: z.string().nullable(),
  contract_version: z.number().int(),
  rule_version: z.string().nullable(),
  status: sourceStatusSchema,
  produced_at: z.string().nullable(),
  warnings: z.array(z.string()),
});

export type SourceMetadata = z.infer<typeof sourceMetadataSchema>;
