import { createContext, type ReactNode, useContext } from 'react';

import type { ModuleAnalytics } from './schemas';

export interface ModuleUrlStateEvent {
  dimensionId: string;
  value: string;
  label: string | null;
}

interface ModuleContextValue {
  data: ModuleAnalytics;
  onUrlStateChange?: (event: ModuleUrlStateEvent) => void;
}

const ModuleContext = createContext<ModuleContextValue | null>(null);

export function ModuleProvider({
  data,
  onUrlStateChange,
  children,
}: {
  data: ModuleAnalytics;
  onUrlStateChange?: (event: ModuleUrlStateEvent) => void;
  children: ReactNode;
}) {
  return (
    <ModuleContext.Provider value={{ data, ...(onUrlStateChange ? { onUrlStateChange } : {}) }}>
      {children}
    </ModuleContext.Provider>
  );
}

export function useModuleData(): ModuleAnalytics {
  const value = useContext(ModuleContext);
  if (!value) throw new Error('Module widgets must render inside ModuleProvider.');
  return value.data;
}

export function useModuleUrlStateChange(): ((event: ModuleUrlStateEvent) => void) | undefined {
  const value = useContext(ModuleContext);
  if (!value) throw new Error('Module widgets must render inside ModuleProvider.');
  return value.onUrlStateChange;
}
