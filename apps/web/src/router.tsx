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
  import('./features/overview/OverviewPage').then((module) => ({
    default: module.OverviewPage,
  })),
);
const MonthlyReviewPage = lazy(() =>
  import('./features/monthly-review/MonthlyReviewPage').then((module) => ({
    default: module.MonthlyReviewPage,
  })),
);
const AnalyticsModulePage = lazy(() =>
  import('./features/modules/AnalyticsModulePage').then((module) => ({
    default: module.AnalyticsModulePage,
  })),
);
const CustomDashboardsPage = lazy(() =>
  import('./features/dashboards/CustomDashboardsPage').then((module) => ({
    default: module.CustomDashboardsPage,
  })),
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
    <ErrorState
      title="Pagina nu există"
      message="Ruta solicitată nu face parte din UniHub Insight."
    />
  ),
});
const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: () => suspense(<OverviewPage />),
});
const monthlyReviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/monthly-review',
  component: () => suspense(<MonthlyReviewPage />),
});
const salesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/sales',
  component: () => suspense(<AnalyticsModulePage module="sales" />),
});
const performanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/performance',
  component: () => suspense(<AnalyticsModulePage module="performance" />),
});
const campaignsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/campaigns',
  component: () => suspense(<AnalyticsModulePage module="campaigns" />),
});
const workforceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workforce',
  component: () => suspense(<AnalyticsModulePage module="workforce" />),
});
const compensationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/compensation',
  component: () => suspense(<AnalyticsModulePage module="compensation" />),
});
const financeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/finance',
  component: () => suspense(<AnalyticsModulePage module="finance" />),
});
const planningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/planning',
  component: () => suspense(<AnalyticsModulePage module="planning" />),
});
const dashboardsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/dashboards',
  component: () => suspense(<CustomDashboardsPage />),
});

const routeTree = rootRoute.addChildren([
  overviewRoute,
  monthlyReviewRoute,
  salesRoute,
  performanceRoute,
  campaignsRoute,
  workforceRoute,
  compensationRoute,
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
