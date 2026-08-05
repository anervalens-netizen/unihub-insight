import { describe, expect, it } from 'vitest';

import {
  globalSearchSchema,
  parseComparisons,
  parseDrillPath,
  rangeBounds,
  serializeDrillPath,
} from '../src/lib/search';

describe('analytical URL state', () => {
  it('round-trips range, simultaneous comparisons, dashboard version and drill path', () => {
    const search = globalSearchSchema.parse({
      period: '2026-08',
      range: 'custom',
      start: '2026-01',
      end: '2026-08',
      comparisons: 'target,previous-year,recent-average',
      dashboard_id: 'dash-1',
      dashboard_version: '4',
      drill: 'store:S001:Magazin%201',
    });

    expect(search.dashboard_version).toBe(4);
    expect(parseComparisons(search)).toEqual(['target', 'previous-year', 'recent-average']);
    expect(rangeBounds({ ...search, period: search.period ?? '2026-08' })).toEqual({
      start: '2026-01',
      end: '2026-08',
    });
    expect(parseDrillPath(search.drill)).toEqual([
      { dimension: 'store', value: 'S001', label: 'Magazin 1' },
    ]);
    expect(serializeDrillPath(parseDrillPath(search.drill))).toBe(search.drill);
  });

  it('keeps legacy comparison URLs meaningful for range requests', () => {
    const search = globalSearchSchema.parse({ period: '2026-08', comparison: 'previous-month' });
    expect(parseComparisons(search)).toEqual(['previous-period']);
    expect(rangeBounds({ ...search, period: search.period ?? '2026-08' })).toEqual({
      start: '2026-08',
      end: '2026-08',
    });
  });

  it('accepts numeric range presets parsed by the router', () => {
    expect(globalSearchSchema.parse({ range: 3 }).range).toBe('3');
    expect(globalSearchSchema.parse({ range: 6 }).range).toBe('6');
    expect(globalSearchSchema.parse({ range: 12 }).range).toBe('12');
  });
});
