import { z } from 'zod';

const monthPattern = /^\d{4}-(0[1-9]|1[0-2])$/;

export const comparisonModes = ['previous-month', 'previous-year', 'none'] as const;
export const analyticalComparisons = [
  'target',
  'forecast',
  'previous-period',
  'previous-year',
  'recent-average',
] as const;
export const rangePresets = ['month', 'ytd', '3', '6', '12', 'year', 'custom'] as const;

export const globalSearchSchema = z.object({
  period: z.string().regex(monthPattern).optional(),
  comparison: z.enum(comparisonModes).optional().default('previous-year'),
  comparisons: z.string().max(240).optional(),
  range: z.preprocess(
    (value) => (typeof value === 'number' ? String(value) : value),
    z.enum(rangePresets).optional(),
  ),
  start: z.string().regex(monthPattern).optional(),
  end: z.string().regex(monthPattern).optional(),
  firm: z.string().max(120).optional(),
  regional: z.string().max(120).optional(),
  asm: z.string().max(120).optional(),
  stores: z.string().max(2_000).optional(),
  agent: z.string().max(180).optional(),
  drill: z.string().max(2_000).optional(),
  subview: z.string().max(80).optional(),
  dashboard_id: z.string().max(100).optional(),
  dashboard_version: z.coerce.number().int().positive().optional(),
});

export type GlobalSearch = z.infer<typeof globalSearchSchema>;
export type GlobalSearchPatch = {
  [Key in keyof GlobalSearch]?: GlobalSearch[Key] | undefined;
};
export type ComparisonMode = (typeof comparisonModes)[number];
export type AnalyticalComparison = (typeof analyticalComparisons)[number];
export type RangePreset = (typeof rangePresets)[number];

export interface DrillPathItem {
  dimension: string;
  value: string;
  label?: string | null;
}

export function currentBusinessMonth(now = new Date()): string {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Bucharest',
    year: 'numeric',
    month: '2-digit',
  });
  const parts = formatter.formatToParts(now);
  const year = parts.find((part) => part.type === 'year')?.value;
  const month = parts.find((part) => part.type === 'month')?.value;
  if (!year || !month) throw new Error('Business month could not be resolved.');
  return `${year}-${month}`;
}

export function parseStoreSelection(value: string | undefined): string[] {
  if (!value) return [];
  return [
    ...new Set(
      value
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ];
}

export function serializeStoreSelection(values: readonly string[]): string | undefined {
  const normalized = [...new Set(values.map((item) => item.trim()).filter(Boolean))];
  return normalized.length > 0 ? normalized.join(',') : undefined;
}

export function activeFilterCount(search: GlobalSearch): number {
  return [search.firm, search.regional, search.asm, search.stores, search.agent].filter(Boolean)
    .length;
}

export function parseComparisons(
  search: Pick<GlobalSearch, 'comparison' | 'comparisons'>,
): AnalyticalComparison[] {
  const values = (search.comparisons ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter((value): value is AnalyticalComparison =>
      analyticalComparisons.includes(value as AnalyticalComparison),
    );
  if (values.length > 0) return [...new Set(values)];
  if (search.comparison === 'previous-month') return ['previous-period'];
  if (search.comparison === 'previous-year') return ['previous-year'];
  return [];
}

export function serializeComparisons(values: readonly AnalyticalComparison[]): string | undefined {
  const normalized = [...new Set(values)].filter((value) => analyticalComparisons.includes(value));
  return normalized.length > 0 ? normalized.join(',') : undefined;
}

function shiftMonth(period: string, offset: number): string {
  const [yearText = '1970', monthText = '01'] = period.split('-');
  const year = Number(yearText);
  const month = Number(monthText);
  const absolute = year * 12 + month - 1 + offset;
  const nextYear = Math.floor(absolute / 12);
  const nextMonth = (absolute % 12) + 1;
  return `${nextYear.toString().padStart(4, '0')}-${nextMonth.toString().padStart(2, '0')}`;
}

export function rangeBounds(
  search: Pick<GlobalSearch, 'period' | 'range' | 'start' | 'end'> & { period: string },
): { start: string; end: string } {
  const range = search.range ?? 'month';
  const end = range === 'custom' ? (search.end ?? search.period) : search.period;
  switch (range) {
    case 'ytd':
    case 'year':
      return { start: `${end.slice(0, 4)}-01`, end };
    case '3':
      return { start: shiftMonth(end, -2), end };
    case '6':
      return { start: shiftMonth(end, -5), end };
    case '12':
      return { start: shiftMonth(end, -11), end };
    case 'custom':
      return { start: search.start ?? end, end };
    default:
      return { start: search.start ?? end, end };
  }
}

export function parseDrillPath(value: string | undefined): DrillPathItem[] {
  if (!value) return [];
  return value.split('/').reduce<DrillPathItem[]>((items, part) => {
    const [dimension, rawValue, rawLabel] = part.split(':');
    if (!dimension || !rawValue) return items;
    items.push({
      dimension: decodeURIComponent(dimension),
      value: decodeURIComponent(rawValue),
      ...(rawLabel ? { label: decodeURIComponent(rawLabel) } : {}),
    });
    return items;
  }, []);
}

export function serializeDrillPath(items: readonly DrillPathItem[]): string | undefined {
  if (items.length === 0) return undefined;
  return items
    .map((item) =>
      [item.dimension, item.value, item.label]
        .filter((value): value is string => Boolean(value))
        .map(encodeURIComponent)
        .join(':'),
    )
    .join('/');
}

export function updateDrillPath(
  current: string | undefined,
  next: DrillPathItem,
): string | undefined {
  const items = parseDrillPath(current);
  const existingIndex = items.findIndex((item) => item.dimension === next.dimension);
  if (existingIndex >= 0) items[existingIndex] = next;
  else items.push(next);
  return serializeDrillPath(items);
}
