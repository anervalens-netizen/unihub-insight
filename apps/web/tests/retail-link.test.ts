import { describe, expect, it } from 'vitest';

import { retailContextUrl } from '../src/features/modules/retail-link';

describe('Retail contextual deep links', () => {
  it('maps a single-store Sales interval to the Retail history surface', () => {
    const url = new URL(
      retailContextUrl('https://retail.unihub.ro', 'sales', 'trend', {
        period: '2026-08',
        comparison: 'previous-year',
        range: 'custom',
        start: '2026-03',
        end: '2026-08',
        firm: 'Mobicell',
        regional: 'Nord',
        stores: 'S001',
        agent: 'Agent Test',
      }),
    );
    expect(url.pathname).toBe('/hub');
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      source_context: 'insight',
      section: 'history',
      period: '2026-08',
      range_start: '2026-03',
      range_end: '2026-08',
      firma: 'Mobicell',
      rm: 'Nord',
      magazin: 'S001',
      agent: 'Agent Test',
    });
  });

  it.each([
    ['campaigns', 'promo', '/focus', 'promo', null],
    ['workforce', 'visits', '/hub', 'visits', null],
    ['workforce', 'grile', '/agenti', 'grile', null],
    ['compensation', 'overview', '/management', null, 'salarii'],
    ['finance', 'profitability', '/management/pnl', null, 'pnl'],
    ['planning', 'scenarios', '/management', null, 'target-calculator'],
  ] as const)(
    'maps %s/%s to its operational Retail surface',
    (module, view, path, section, subtab) => {
      const url = new URL(
        retailContextUrl('https://retail.unihub.ro/', module, view, {
          period: '2026-08',
          comparison: 'none',
        }),
      );
      expect(url.pathname).toBe(path);
      expect(url.searchParams.get('section')).toBe(section);
      expect(url.searchParams.get('subtab')).toBe(subtab);
    },
  );

  it('preserves a multi-store scope without inventing one selected store', () => {
    const url = new URL(
      retailContextUrl('https://retail.unihub.ro', 'performance', 'rankings', {
        period: '2026-08',
        comparison: 'previous-year',
        stores: 'S001,S002,S001',
      }),
    );
    expect(url.searchParams.has('magazin')).toBe(false);
    expect(url.searchParams.get('stores')).toBe('S001,S002');
  });
});
