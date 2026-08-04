import { createContext, type ReactNode, useContext } from 'react';

import type { ModuleAnalytics } from './schemas';

const ModuleContext = createContext<ModuleAnalytics | null>(null);

export function ModuleProvider({ data, children }: { data: ModuleAnalytics; children: ReactNode }) {
  return <ModuleContext.Provider value={data}>{children}</ModuleContext.Provider>;
}

export function useModuleData(): ModuleAnalytics {
  const value = useContext(ModuleContext);
  if (!value) throw new Error('Module widgets must render inside ModuleProvider.');
  return value;
}
