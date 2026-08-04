import { z } from 'zod';

const monthPattern = /^\d{4}-(0[1-9]|1[0-2])$/;

export const comparisonModes = ['previous-month', 'previous-year', 'none'] as const;

export const globalSearchSchema = z.object({
  period: z.string().regex(monthPattern).optional(),
  comparison: z.enum(comparisonModes).optional().default('previous-year'),
  firm: z.string().max(120).optional(),
  regional: z.string().max(120).optional(),
  asm: z.string().max(120).optional(),
  stores: z.string().max(2_000).optional(),
  agent: z.string().max(180).optional(),
});

export type GlobalSearch = z.infer<typeof globalSearchSchema>;
export type GlobalSearchPatch = {
  [Key in keyof GlobalSearch]?: GlobalSearch[Key] | undefined;
};
export type ComparisonMode = (typeof comparisonModes)[number];

export function currentBusinessMonth(now = new Date()): string {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Bucharest',
    year: 'numeric',
    month: '2-digit',
  });
  const parts = Object.fromEntries(
    formatter.formatToParts(now).map((part) => [part.type, part.value]),
  );
  const year = parts['year'];
  const month = parts['month'];
  if (!year || !month) throw new Error('Business month could not be resolved.');
  return `${year}-${month}`;
}

export function parseStoreSelection(value: string | undefined): string[] {
  if (!value) return [];
  return [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))];
}

export function serializeStoreSelection(values: readonly string[]): string | undefined {
  const normalized = [...new Set(values.map((item) => item.trim()).filter(Boolean))];
  return normalized.length > 0 ? normalized.join(',') : undefined;
}

export function activeFilterCount(search: GlobalSearch): number {
  return [search.firm, search.regional, search.asm, search.stores, search.agent].filter(Boolean)
    .length;
}
