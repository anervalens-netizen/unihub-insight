import type { WidgetQueryResult } from '../query/schemas';
import type { BreakdownRow, ModuleAnalytics } from './schemas';

interface NativeBatchRow {
  readonly [key: string]: unknown;
  readonly actual?: unknown;
  readonly context?: unknown;
  readonly date?: unknown;
  readonly id?: unknown;
  readonly is_estimate?: unknown;
  readonly key?: unknown;
  readonly label?: unknown;
  readonly net_quantity?: unknown;
  readonly observed_store_count?: unknown;
  readonly positive_quantity?: unknown;
  readonly progress_pct?: unknown;
  readonly receipt_2plus_count?: unknown;
  readonly receipt_count?: unknown;
  readonly return_quantity?: unknown;
  readonly risk?: unknown;
  readonly secondary?: unknown;
  readonly share_pct?: unknown;
  readonly step_kind?: unknown;
  readonly target?: unknown;
  readonly tertiary?: unknown;
  readonly quaternary?: unknown;
  readonly value?: unknown;
  readonly x?: unknown;
  readonly y?: unknown;
}

function numeric(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value !== 'string' || value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function risk(value: unknown): BreakdownRow['risk'] {
  return value === 'watch' || value === 'risk' ? value : 'healthy';
}

function comparisonKey(value: string): string {
  return (
    {
      previous_period: 'previous-period',
      previous_year: 'previous-year',
      recent_average: 'recent-average',
    }[value] ?? value
  );
}

function clearFailedProjection(data: ModuleAnalytics, result: WidgetQueryResult): ModuleAnalytics {
  const shape = result.query.visualization;
  if (shape === 'kpi') {
    return { ...data, kpis: data.kpis.filter((item) => item.id !== result.query.metric_id) };
  }
  if (shape === 'line' || shape === 'area') return { ...data, trend: [] };
  if (shape === 'donut' || shape === 'treemap' || shape === 'waterfall') {
    return { ...data, distribution: [] };
  }
  if (shape === 'heatmap') return { ...data, matrix: [] };
  if (shape === 'calendar') return { ...data, calendar: [] };
  if (shape === 'scatter' || shape === 'table' || shape === 'histogram') {
    return { ...data, breakdown: [] };
  }
  return data;
}

export function applyNativeBatchResults(
  data: ModuleAnalytics,
  results: readonly WidgetQueryResult[],
): ModuleAnalytics {
  let next: ModuleAnalytics = {
    ...data,
    kpis: data.kpis.map((item) => ({ ...item })),
    trend: data.trend.map((item) => ({ ...item, comparisons: { ...item.comparisons } })),
    distribution: data.distribution.map((item) => ({ ...item })),
    breakdown: data.breakdown.map((item) => ({ ...item })),
    matrix: data.matrix.map((item) => ({ ...item })),
    calendar: data.calendar.map((item) => ({ ...item })),
  };

  for (const result of results) {
    const dataset = result.dataset;
    if (!dataset || result.error) {
      next = clearFailedProjection(next, result);
      continue;
    }
    const rows = dataset.rows as NativeBatchRow[];
    const first = rows[0];
    const metricId = result.query.metric_id;

    if (result.query.visualization === 'kpi') {
      const value = numeric(first?.value);
      next = {
        ...next,
        kpis: next.kpis.map((item) =>
          item.id === metricId && value !== null
            ? {
                ...item,
                value,
                ...(metricId === 'target.progress_pct' && numeric(first?.target) !== null
                  ? { supporting_value: numeric(first?.target) }
                  : {}),
              }
            : item,
        ),
      };
      continue;
    }

    if (result.query.visualization === 'line' || result.query.visualization === 'area') {
      const comparisonDimensions = dataset.dimensions.filter(
        (dimension) => dimension.role === 'comparison',
      );
      next = {
        ...next,
        trend: rows.flatMap((row) => {
          const value = numeric(row.value);
          if (value === null || typeof row.key !== 'string') return [];
          const comparisons = Object.fromEntries(
            comparisonDimensions.flatMap((dimension) => {
              const comparison = numeric(row[dimension.id]);
              return comparison === null ? [] : [[comparisonKey(dimension.id), comparison]];
            }),
          );
          const actual = numeric(row.actual);
          return [
            {
              key: row.key,
              label: typeof row.label === 'string' ? row.label : row.key,
              primary: value,
              comparison: actual ?? Object.values(comparisons)[0] ?? null,
              comparisons,
              target: numeric(row.target),
              secondary: null,
              is_estimate: row.is_estimate === true,
            },
          ];
        }),
      };
      continue;
    }

    if (result.query.visualization === 'donut' || result.query.visualization === 'treemap') {
      next = {
        ...next,
        distribution: rows.flatMap((row) => {
          const value = numeric(row.value);
          if (value === null || typeof row.id !== 'string') return [];
          return [
            {
              id: row.id,
              label: typeof row.label === 'string' ? row.label : row.id,
              value,
              share_pct: numeric(row.share_pct) ?? 0,
            },
          ];
        }),
      };
      continue;
    }

    if (result.query.visualization === 'heatmap') {
      const existing = new Map(next.matrix.map((cell) => [`${cell.x}\u0000${cell.y}`, cell]));
      next = {
        ...next,
        matrix: rows.flatMap((row) => {
          const value = numeric(row.value);
          if (value === null || typeof row.x !== 'string' || typeof row.y !== 'string') return [];
          const previous = existing.get(`${row.x}\u0000${row.y}`);
          return [
            {
              x: row.x,
              y: row.y,
              value,
              label: typeof row.label === 'string' ? row.label : null,
              risk: previous?.risk ?? 'healthy',
            },
          ];
        }),
      };
      continue;
    }

    if (result.query.visualization === 'calendar') {
      next = {
        ...next,
        calendar: rows.flatMap((row) => {
          const sales = numeric(row.value);
          if (sales === null || typeof row.date !== 'string') return [];
          return [
            {
              date: row.date,
              sales,
              net_quantity: numeric(row.net_quantity) ?? 0,
              positive_quantity: numeric(row.positive_quantity) ?? 0,
              return_quantity: numeric(row.return_quantity) ?? 0,
              receipt_count: numeric(row.receipt_count) ?? 0,
              receipt_2plus_count: numeric(row.receipt_2plus_count) ?? 0,
              observed_store_count: numeric(row.observed_store_count) ?? 1,
              coverage_state: 'observed' as const,
            },
          ];
        }),
      };
      continue;
    }

    if (result.query.visualization === 'waterfall') {
      const waterfallRows = rows.filter(
        (row) => typeof row.label === 'string' && numeric(row.value) !== null,
      );
      const start = waterfallRows.find((row) => row.step_kind === 'start');
      const total = waterfallRows.find((row) => row.step_kind === 'total');
      next = {
        ...next,
        kpis: next.kpis.map((item) => {
          if (item.id === 'finance.revenue' && numeric(start?.value) !== null) {
            return { ...item, value: numeric(start?.value) ?? item.value };
          }
          if (item.id === 'finance.ebit' && numeric(total?.value) !== null) {
            return { ...item, value: numeric(total?.value) ?? item.value };
          }
          return item;
        }),
        distribution: waterfallRows
          .filter((row) => row.step_kind === 'delta')
          .map((row, index) => ({
            id: `waterfall-${index}`,
            label: String(row.label),
            value: -(numeric(row.value) ?? 0),
            share_pct: 0,
          })),
      };
      continue;
    }

    if (result.query.visualization === 'scatter') {
      next = {
        ...next,
        breakdown: rows.flatMap((row) => {
          const x = numeric(row.x);
          const y = numeric(row.y);
          if (x === null || y === null || typeof row.id !== 'string') return [];
          return [
            {
              id: row.id,
              label: typeof row.label === 'string' ? row.label : row.id,
              context: 'Query batch',
              primary: y,
              secondary: data.module === 'planning' ? x : null,
              tertiary: data.module === 'performance' ? x : null,
              progress_pct: data.module === 'performance' ? y : null,
              delta_pct: null,
              risk: risk(row.risk),
            },
          ];
        }),
      };
      continue;
    }

    if (result.query.visualization === 'table' || result.query.visualization === 'histogram') {
      next = {
        ...next,
        breakdown: rows.flatMap((row) => {
          const value = numeric(row.value);
          if (value === null || typeof row.id !== 'string') return [];
          return [
            {
              id: row.id,
              label: typeof row.label === 'string' ? row.label : row.id,
              context: typeof row.context === 'string' ? row.context : 'Query batch',
              primary: value,
              secondary: numeric(row.secondary),
              tertiary: numeric(row.tertiary),
              quaternary: numeric(row.quaternary),
              progress_pct: numeric(row.progress_pct),
              delta_pct: null,
              risk: risk(row.risk),
            },
          ];
        }),
      };
    }
  }
  return next;
}
