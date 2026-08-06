import { describe, expect, it } from 'vitest';

import {
  retailContextUrl,
  retailDashboardEntityContextUrl,
  retailEntityContextUrl,
} from '../src/features/modules/retail-link';

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
        regional: 'Nord,Sud',
        asm: 'ASM legacy drill',
        stores: 'S001',
        agent: 'Agent 1,Agent 2',
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
      rm: 'Nord,Sud',
      asm: 'ASM legacy drill',
      magazin: 'S001',
      agent: 'Agent 1,Agent 2',
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

  it('opens one selected entity without retaining a conflicting multi-store scope', () => {
    const url = new URL(
      retailEntityContextUrl(
        'https://retail.unihub.ro',
        'performance',
        'rankings',
        {
          period: '2026-08',
          comparison: 'none',
          stores: 'S001,S002',
        },
        { dimensionId: 'store', value: 'S003', label: 'Magazin 3' },
      ),
    );
    expect(url.pathname).toBe('/agenti');
    expect(url.searchParams.get('magazin')).toBe('S003');
    expect(url.searchParams.has('stores')).toBe(false);
  });

  it('maps a custom dashboard time detail to the module default Retail surface', () => {
    const url = new URL(
      retailDashboardEntityContextUrl(
        'https://retail.unihub.ro',
        'sales',
        { period: '2026-08', comparison: 'none', range: '12' },
        { dimensionId: 'time', value: '2026-04', label: 'aprilie 2026' },
      ),
    );
    expect(url.pathname).toBe('/hub');
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      source_context: 'insight',
      section: 'history',
      period: '2026-04',
      range_start: '2026-04',
      range_end: '2026-04',
    });
  });
});
