import { describe, expect, it } from 'vitest';

import { csvCell, rowsFor } from '../src/features/modules/DataInspector';
import type { ModuleAnalytics } from '../src/features/modules/schemas';

describe('native module inspector', () => {
  it('resolves KPI rows by metric id, independent of subview order', () => {
    const data = {
      kpis: [
        {
          id: 'sales.total',
          label: 'Vânzări',
          value: 100,
          unit: 'currency',
          risk: 'healthy',
        },
        {
          id: 'receipts.average_value',
          label: 'Valoare medie bon',
          value: 25,
          unit: 'currency',
          risk: 'healthy',
        },
      ],
    } as ModuleAnalytics;

    expect(rowsFor('kpi:receipts.average_value', data)).toMatchObject([
      { metric: 'Valoare medie bon', value: 25 },
    ]);
  });

  it('neutralizes spreadsheet formulas only for text values', () => {
    expect(csvCell('=SUM(A1:A2)')).toBe("'=SUM(A1:A2)");
    expect(csvCell('  @cmd')).toBe("'  @cmd");
    expect(csvCell(-7)).toBe('-7');
  });
});
