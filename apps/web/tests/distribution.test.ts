import { describe, expect, it } from 'vitest';

import {
  BOXPLOT_MIN_SAMPLE_SIZE,
  buildHistogramBins,
  finiteSortedValues,
  summarizeDistribution,
} from '../src/components/charts/distribution';

describe('distribution statistics', () => {
  it('uses interpolated quartiles and reports only IQR outliers', () => {
    expect(summarizeDistribution([100, 5, 1, 4, 2, 3])).toEqual({
      minimum: 1,
      q1: 2.25,
      median: 3.5,
      q3: 4.75,
      maximum: 100,
      whiskerLow: 1,
      whiskerHigh: 5,
      outliers: [100],
    });
  });

  it('keeps a constant eligible sample visible in both summaries', () => {
    const values = Array.from({ length: BOXPLOT_MIN_SAMPLE_SIZE }, () => 7);
    expect(summarizeDistribution(values)).toMatchObject({
      q1: 7,
      median: 7,
      q3: 7,
      whiskerLow: 7,
      whiskerHigh: 7,
      outliers: [],
    });
    expect(buildHistogramBins(values)).toEqual([{ start: 7, end: 7, count: 5 }]);
  });

  it('drops missing and non-finite values before sorting', () => {
    expect(
      finiteSortedValues([3, null, Number.NaN, 1, undefined, Number.POSITIVE_INFINITY]),
    ).toEqual([1, 3]);
  });
});
