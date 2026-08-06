import type { ModuleId } from './schemas';

export const moduleEntityDimension: Record<ModuleId, string> = {
  sales: 'store',
  performance: 'store',
  campaigns: 'store',
  workforce: 'agent',
  compensation: 'firm',
  finance: 'store',
  planning: 'store',
};

export const moduleDistributionDimension: Partial<Record<ModuleId, string>> = {
  sales: 'category',
  campaigns: 'category',
  workforce: 'tenure',
  compensation: 'firm',
  finance: 'category',
};
