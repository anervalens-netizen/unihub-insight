export const BOXPLOT_MIN_SAMPLE_SIZE = 5;

export interface DistributionSummary {
  readonly minimum: number;
  readonly q1: number;
  readonly median: number;
  readonly q3: number;
  readonly maximum: number;
  readonly whiskerLow: number;
  readonly whiskerHigh: number;
  readonly outliers: readonly number[];
}

export interface HistogramBin {
  readonly start: number;
  readonly end: number;
  count: number;
}

export function finiteSortedValues(values: readonly (number | null | undefined)[]): number[] {
  return values
    .filter(
      (value): value is number => value !== null && value !== undefined && Number.isFinite(value),
    )
    .sort((left, right) => left - right);
}

function quantile(sortedValues: readonly number[], percentile: number): number {
  const position = (sortedValues.length - 1) * percentile;
  const lowerIndex = Math.floor(position);
  const upperIndex = Math.ceil(position);
  const lower = sortedValues[lowerIndex] ?? 0;
  const upper = sortedValues[upperIndex] ?? lower;
  return lower + (upper - lower) * (position - lowerIndex);
}

export function summarizeDistribution(inputValues: readonly number[]): DistributionSummary | null {
  const values = finiteSortedValues(inputValues);
  if (values.length === 0) return null;
  const q1 = quantile(values, 0.25);
  const median = quantile(values, 0.5);
  const q3 = quantile(values, 0.75);
  const iqr = q3 - q1;
  const lowerFence = q1 - iqr * 1.5;
  const upperFence = q3 + iqr * 1.5;
  const minimum = values[0] ?? 0;
  const maximum = values.at(-1) ?? minimum;
  const whiskerLow = values.find((value) => value >= lowerFence) ?? minimum;
  const whiskerHigh = [...values].reverse().find((value) => value <= upperFence) ?? maximum;
  return {
    minimum,
    q1,
    median,
    q3,
    maximum,
    whiskerLow,
    whiskerHigh,
    outliers: values.filter((value) => value < whiskerLow || value > whiskerHigh),
  };
}

export function buildHistogramBins(
  inputValues: readonly number[],
  { minimumBins = 1, maximumBins = 8 }: { minimumBins?: number; maximumBins?: number } = {},
): HistogramBin[] {
  const values = finiteSortedValues(inputValues);
  if (values.length === 0) return [];
  const minimum = values[0] ?? 0;
  const maximum = values.at(-1) ?? minimum;
  if (minimum === maximum) {
    return [{ start: minimum, end: maximum, count: values.length }];
  }
  const safeMinimum = Math.max(1, Math.floor(minimumBins));
  const safeMaximum = Math.max(safeMinimum, Math.floor(maximumBins));
  const count = Math.min(safeMaximum, Math.max(safeMinimum, Math.ceil(Math.sqrt(values.length))));
  const width = (maximum - minimum) / count;
  const bins = Array.from({ length: count }, (_, index) => ({
    start: minimum + width * index,
    end: index === count - 1 ? maximum : minimum + width * (index + 1),
    count: 0,
  }));
  for (const value of values) {
    const index = Math.min(count - 1, Math.floor((value - minimum) / width));
    const bin = bins[index];
    if (bin) bin.count += 1;
  }
  return bins;
}
