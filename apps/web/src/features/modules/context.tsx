import { createContext, type ReactNode, useContext } from 'react';

import type { ChartUrlRangeEvent } from '../../components/charts/chart-spec';
import type { ModuleAnalytics } from './schemas';

export interface ModuleUrlStateEvent {
  dimensionId: string;
  value: string;
  label: string | null;
}

interface ModuleContextValue {
  data: ModuleAnalytics;
  onUrlStateChange?: (event: ModuleUrlStateEvent) => void;
  onUrlStateChanges?: (events: readonly ModuleUrlStateEvent[]) => void;
  onUrlRangeChange?: (event: ChartUrlRangeEvent) => void;
  onUrlStateReset?: () => void;
}

const ModuleContext = createContext<ModuleContextValue | null>(null);

export function ModuleProvider({
  data,
  onUrlStateChange,
  onUrlStateChanges,
  onUrlRangeChange,
  onUrlStateReset,
  children,
}: {
  data: ModuleAnalytics;
  onUrlStateChange?: (event: ModuleUrlStateEvent) => void;
  onUrlStateChanges?: (events: readonly ModuleUrlStateEvent[]) => void;
  onUrlRangeChange?: (event: ChartUrlRangeEvent) => void;
  onUrlStateReset?: () => void;
  children: ReactNode;
}) {
  return (
    <ModuleContext.Provider
      value={{
        data,
        ...(onUrlStateChange ? { onUrlStateChange } : {}),
        ...(onUrlStateChanges ? { onUrlStateChanges } : {}),
        ...(onUrlRangeChange ? { onUrlRangeChange } : {}),
        ...(onUrlStateReset ? { onUrlStateReset } : {}),
      }}
    >
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

export function useModuleUrlStateChanges():
  | ((events: readonly ModuleUrlStateEvent[]) => void)
  | undefined {
  const value = useContext(ModuleContext);
  if (!value) throw new Error('Module widgets must render inside ModuleProvider.');
  return value.onUrlStateChanges;
}

export function useModuleUrlRangeChange(): ((event: ChartUrlRangeEvent) => void) | undefined {
  const value = useContext(ModuleContext);
  if (!value) throw new Error('Module widgets must render inside ModuleProvider.');
  return value.onUrlRangeChange;
}

export function useModuleUrlStateReset(): (() => void) | undefined {
  const value = useContext(ModuleContext);
  if (!value) throw new Error('Module widgets must render inside ModuleProvider.');
  return value.onUrlStateReset;
}
