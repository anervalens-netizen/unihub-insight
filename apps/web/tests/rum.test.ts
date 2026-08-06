import { describe, expect, it } from 'vitest';

import { rumSurface } from '../src/lib/rum';

describe('RUM surface attribution', () => {
  it('maps only finite analytical routes', () => {
    expect(rumSurface('/')).toBe('overview');
    expect(rumSurface('/monthly-review')).toBe('monthly-review');
    expect(rumSurface('/sales')).toBe('module-sales');
    expect(rumSurface('/finance/')).toBe('module-finance');
    expect(rumSurface('/dashboards')).toBe('custom-dashboards');
    expect(rumSurface('/unexpected/user-controlled-value')).toBe('other');
  });
});
