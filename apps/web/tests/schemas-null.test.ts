import { describe, expect, it } from 'vitest';

import { nullableNumeric } from '../src/features/modules/schemas';
import { nullableNumber } from '../src/features/overview/schemas';

describe('nullable analytical numbers', () => {
  it('preserves null in module responses before numeric coercion', () => {
    expect(nullableNumeric.parse(null)).toBeNull();
    expect(nullableNumeric.parse('12.50')).toBe(12.5);
  });

  it('preserves null in overview responses before numeric coercion', () => {
    expect(nullableNumber.parse(null)).toBeNull();
    expect(nullableNumber.parse('12.50')).toBe(12.5);
  });
});
