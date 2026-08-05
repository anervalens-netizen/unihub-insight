import { describe, expect, it } from 'vitest';

import { nullableReviewNumeric } from '../src/features/monthly-review/schemas';

describe('monthly review nullable numbers', () => {
  it('preserves null instead of coercing it to zero', () => {
    expect(nullableReviewNumeric.parse(null)).toBeNull();
  });

  it('still coerces numeric database strings', () => {
    expect(nullableReviewNumeric.parse('12.50')).toBe(12.5);
  });
});
