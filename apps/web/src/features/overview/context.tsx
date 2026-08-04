import { createContext, type ReactNode, useContext } from 'react';

import type { Overview } from './schemas';

const OverviewContext = createContext<Overview | null>(null);

export function OverviewProvider({ data, children }: { data: Overview; children: ReactNode }) {
  return <OverviewContext.Provider value={data}>{children}</OverviewContext.Provider>;
}

export function useOverviewData(): Overview {
  const value = useContext(OverviewContext);
  if (!value) throw new Error('Overview widgets must render inside OverviewProvider.');
  return value;
}
