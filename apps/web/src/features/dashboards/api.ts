import { queryOptions } from '@tanstack/react-query';

import { getJson, requestEmpty, requestJson } from '../../lib/api';
import { dashboardDocumentSchema, dashboardListSchema, type DashboardCreateInput, type DashboardUpdateInput } from './schemas';

export const dashboardsQuery = queryOptions({
  queryKey: ['dashboards'] as const,
  queryFn: ({ signal }) => getJson('/dashboards', new URLSearchParams(), { schema: dashboardListSchema, signal }),
  staleTime: 30_000,
});

export function createDashboard(input: DashboardCreateInput) {
  return requestJson('/dashboards', undefined, { schema: dashboardDocumentSchema, method: 'POST', body: input });
}

export function updateDashboard(id: string, input: DashboardUpdateInput) {
  return requestJson(`/dashboards/${id}`, undefined, { schema: dashboardDocumentSchema, method: 'PUT', body: input });
}

export function deleteDashboard(id: string) {
  return requestEmpty(`/dashboards/${id}`);
}
