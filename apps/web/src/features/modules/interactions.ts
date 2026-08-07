import type { ModuleId } from './schemas';

export const moduleEntityDimension: Record<ModuleId, string> = {
  sales: 'store',
  performance: 'store',
  campaigns: 'store',
  workforce: 'agent',
  compensation: 'person',
  finance: 'store',
  planning: 'store',
};

export const moduleDistributionDimension: Partial<Record<ModuleId, string>> = {
  sales: 'category',
  campaigns: 'subcategory',
  workforce: 'tenure',
  compensation: 'firm',
  finance: 'category',
};
