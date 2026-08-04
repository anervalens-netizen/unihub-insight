import { createContext, type ReactNode, useContext } from 'react';

import type { Capability, UserContext } from './schemas';

const IdentityContext = createContext<UserContext | null>(null);

export function IdentityProvider({ user, children }: { user: UserContext; children: ReactNode }) {
  return <IdentityContext.Provider value={user}>{children}</IdentityContext.Provider>;
}

export function useIdentity(): UserContext {
  const value = useContext(IdentityContext);
  if (!value) throw new Error('IdentityProvider is missing.');
  return value;
}

export function useCapability(capability: Capability): boolean {
  return useIdentity().capabilities.includes(capability);
}
