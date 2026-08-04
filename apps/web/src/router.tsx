import {
  createRootRoute,
  createRoute,
  createRouter,
  type ErrorComponentProps,
} from '@tanstack/react-router';
import { lazy, Suspense, type ReactNode } from 'react';

import { AppShell } from './app/AppShell';
import { ErrorState } from './components/ui/ErrorState';
import { LoadingState } from './components/ui/LoadingState';
import { globalSearchSchema } from './lib/search';

const OverviewPage = lazy(() =>
  import('./features/overview/OverviewPage').then((module) => ({ default: module.OverviewPage })),
);
const ModulePage = lazy(() =>
  import('./features/module/ModulePage').then((module) => ({ default: module.ModulePage })),
);

function RouteError({ error, reset }: ErrorComponentProps) {
  return (
    <ErrorState
      title="Ecranul nu a putut fi randat"
      message={error instanceof Error ? error.message : 'Eroare necunoscută.'}
      onRetry={reset}
    />
  );
}

function suspense(element: ReactNode) {
  return <Suspense fallback={<LoadingState label="Se încarcă modulul…" />}>{element}</Suspense>;
}

const rootRoute = createRootRoute({
  validateSearch: (input) => globalSearchSchema.parse(input),
  component: AppShell,
  errorComponent: RouteError,
  notFoundComponent: () => (
    <ErrorState title="Pagina nu există" message="Ruta solicitată nu face parte din UniHub Insight." />
  ),
});

const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => suspense(<OverviewPage />),
});

const salesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sales',
  component: () => suspense(<ModulePage module="sales" />),
});
const performanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/performance',
  component: () => suspense(<ModulePage module="performance" />),
});
const campaignsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/campaigns',
  component: () => suspense(<ModulePage module="campaigns" />),
});
const workforceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workforce',
  component: () => suspense(<ModulePage module="workforce" />),
});
const financeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/finance',
  component: () => suspense(<ModulePage module="finance" />),
});
const planningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/planning',
  component: () => suspense(<ModulePage module="planning" />),
});
const dashboardsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboards',
  component: () => suspense(<ModulePage module="dashboards" />),
});

const routeTree = rootRoute.addChildren([
  overviewRoute,
  salesRoute,
  performanceRoute,
  campaignsRoute,
  workforceRoute,
  financeRoute,
  planningRoute,
  dashboardsRoute,
]);

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 30_000,
  scrollRestoration: true,
});

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
