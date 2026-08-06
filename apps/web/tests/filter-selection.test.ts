import { describe, expect, it } from 'vitest';

import { analyticsSearchParams } from '../src/lib/download';
import {
  activeFilterCount,
  globalSearchSchema,
  parseSelection,
  serializeSelection,
} from '../src/lib/search';

describe('Retail master filter selection contract', () => {
  it('parses and serializes ordered CSV selections without duplicates', () => {
    expect(parseSelection('Nord, Sud, Nord,,Sud')).toEqual(['Nord', 'Sud']);
    expect(serializeSelection(['Nord', ' Sud ', 'Nord', ''])).toBe('Nord,Sud');
    expect(serializeSelection([])).toBeUndefined();
  });

  it('keeps RM, stores and agents in the router URL state', () => {
    const search = globalSearchSchema.parse({
      period: '2026-08',
      regional: 'Andrei Sud,Dobrogea,Andrei Sud',
      stores: 'B001,C001,B001',
      agent: 'Agent 01,Agent 03,Agent 01',
    });

    expect(parseSelection(search.regional)).toEqual(['Andrei Sud', 'Dobrogea']);
    expect(parseSelection(search.stores)).toEqual(['B001', 'C001']);
    expect(parseSelection(search.agent)).toEqual(['Agent 01', 'Agent 03']);
    expect(activeFilterCount(search)).toBe(3);
  });

  it('sends the same CSV scope to analytics APIs and never emits ASM', () => {
    const params = analyticsSearchParams({
      period: '2026-08',
      comparison: 'previous-year',
      regional: 'Andrei Sud,Dobrogea',
      stores: 'B001,C001',
      agent: 'Agent 01,Agent 03',
      asm: 'legacy internal drill',
    });

    expect(params.get('regional')).toBe('Andrei Sud,Dobrogea');
    expect(params.get('stores')).toBe('B001,C001');
    expect(params.get('agent')).toBe('Agent 01,Agent 03');
    expect(params.has('asm')).toBe(false);
  });
});
