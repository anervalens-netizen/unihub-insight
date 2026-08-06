import { describe, expect, it } from 'vitest';

import {
  crossFilterMultiPatch,
  crossFilterPatch,
  crossFilterRangePatch,
  resetCrossFilterPatch,
  truncateCrossFilterPatch,
} from '../src/lib/cross-filter';
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

  it('applies semantic hierarchy and time cross-filters to URL state', () => {
    const drill = 'firm:U/regional:N/asm:A/store:S/agent:I';
    expect(crossFilterPatch(drill, { dimensionId: 'rm', value: 'Sud', label: 'Sud' })).toEqual({
      drill: 'firm:U/regional:Sud:Sud',
      regional: 'Sud',
      asm: undefined,
      stores: undefined,
      agent: undefined,
    });
    expect(
      crossFilterPatch(undefined, {
        dimensionId: 'period',
        value: '2026-07',
        label: 'Iulie 2026',
      }),
    ).toEqual({
      drill: 'time:2026-07:Iulie%202026',
      period: '2026-07',
      range: 'month',
      start: undefined,
      end: undefined,
    });
    expect(
      crossFilterPatch(undefined, { dimensionId: 'category', value: 'device', label: 'Device' }),
    ).toEqual({});
  });

  it('applies a chart-selected temporal window as an exact custom URL range', () => {
    expect(crossFilterRangePatch('store:S001', { start: '2026-03', end: '2026-08' })).toEqual({
      drill: 'store:S001/time:2026-08:2026-03%20%E2%86%92%202026-08',
      period: '2026-08',
      range: 'custom',
      start: '2026-03',
      end: '2026-08',
    });
    expect(crossFilterRangePatch(undefined, { start: 'invalid', end: '2026-08' })).toEqual({});
  });

  it('applies both entity and time coordinates from a matrix cell', () => {
    expect(
      crossFilterMultiPatch(undefined, [
        { dimensionId: 'store', value: 'S001', label: 'Magazin 1' },
        { dimensionId: 'time', value: '2026-08', label: 'August 2026' },
      ]),
    ).toEqual({
      drill: 'store:S001:Magazin%201/time:2026-08:August%202026',
      stores: 'S001',
      agent: undefined,
      period: '2026-08',
      range: 'month',
      start: undefined,
      end: undefined,
    });
  });

  it('clears only filters represented by removed drill levels', () => {
    const drill = 'time:2026-07/firm:U/regional:N/store:S';
    expect(truncateCrossFilterPatch(drill, 2)).toEqual({
      drill: 'time:2026-07/firm:U',
      regional: undefined,
      stores: undefined,
    });
    expect(resetCrossFilterPatch(drill)).toEqual({
      drill: undefined,
      period: undefined,
      range: undefined,
      start: undefined,
      end: undefined,
      firm: undefined,
      regional: undefined,
      stores: undefined,
    });
  });
});
