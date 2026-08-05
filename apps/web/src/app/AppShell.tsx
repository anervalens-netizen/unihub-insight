import { useQuery } from '@tanstack/react-query';
import { Outlet, useLocation } from '@tanstack/react-router';
import { Laptop, Moon, Sun } from 'lucide-react';
import { useEffect, useState } from 'react';

import {
  ChartPreferencesButton,
  ChartPreferencesProvider,
} from '../components/charts/ChartPreferences';
import { ErrorState } from '../components/ui/ErrorState';
import { LoadingState } from '../components/ui/LoadingState';
import { identityQuery } from '../features/identity/api';
import { IdentityProvider } from '../features/identity/context';
import { GlobalFilters } from './GlobalFilters';
import { moduleMetadata } from './navigation';
import { Sidebar } from './Sidebar';

function usePersistentBoolean(key: string, initial: boolean): [boolean, (value: boolean) => void] {
  const [value, setValue] = useState(() => {
    const stored = localStorage.getItem(key);
    return stored === null ? initial : stored === 'true';
  });
  const update = (next: boolean): void => {
    setValue(next);
    localStorage.setItem(key, String(next));
  };
  return [value, update];
}

function useTheme() {
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const [dark, setDark] = usePersistentBoolean('unihub-insight:dark', systemDark);
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  }, [dark]);
  return { dark, setDark };
}

export function AppShell() {
  const identity = useQuery(identityQuery);
  const [collapsed, setCollapsed] = usePersistentBoolean('unihub-insight:sidebar-collapsed', false);
  const { dark, setDark } = useTheme();
  const pathname = useLocation({ select: (location) => location.pathname });
  const metadata = moduleMetadata[pathname as keyof typeof moduleMetadata] ?? moduleMetadata['/'];

  if (identity.isPending) return <LoadingState label="Se verifică identitatea și permisiunile…" />;
  if (identity.isError)
    return (
      <ErrorState
        title="Autentificarea nu este disponibilă"
        message={
          identity.error instanceof Error
            ? identity.error.message
            : 'Identitatea nu a putut fi verificată.'
        }
        onRetry={() => void identity.refetch()}
      />
    );
  const user = identity.data;
  const theme = dark ? 'dark' : 'light';
  return (
    <IdentityProvider user={user}>
      <ChartPreferencesProvider theme={theme}>
        <div className="app-root">
          <div className="desktop-warning">
            <Laptop size={24} />
            <strong>UniHub Insight este optimizat pentru desktop</strong>
            <span>Folosește o fereastră de minimum 1180 px pentru analiza completă.</span>
          </div>
          <Sidebar
            collapsed={collapsed}
            onToggle={() => setCollapsed(!collapsed)}
            capabilities={user.capabilities}
          />
          <div className="workspace">
            <header className="topbar">
              <div className="page-identity">
                <span>Retail Intelligence</span>
                <h1>{metadata.title}</h1>
                <p>{metadata.description}</p>
              </div>
              <div className="topbar-actions">
                <div className="identity-summary">
                  <strong>{user.name ?? user.email ?? user.subject}</strong>
                  <span>
                    {user.is_demo
                      ? 'Demo administrator'
                      : `${user.capabilities.length} capabilități`}
                  </span>
                </div>
                <span className="environment-badge">v1.0.0-rc.1</span>
                <ChartPreferencesButton />
                <button
                  type="button"
                  className="icon-button icon-button--topbar"
                  onClick={() => setDark(!dark)}
                  aria-label={dark ? 'Folosește tema luminoasă' : 'Folosește tema întunecată'}
                >
                  {dark ? <Sun size={17} /> : <Moon size={17} />}
                </button>
              </div>
            </header>
            <GlobalFilters />
            <main className="content-canvas">
              <Outlet />
            </main>
          </div>
        </div>
      </ChartPreferencesProvider>
    </IdentityProvider>
  );
}
