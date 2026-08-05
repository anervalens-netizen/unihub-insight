import { queryOptions } from '@tanstack/react-query';

import { getJson, requestEmpty, requestJson } from '../../lib/api';
import {
  type DashboardCreateInput,
  type DashboardUpdateInput,
  dashboardDocumentSchema,
  dashboardListSchema,
  dashboardSubjectsSchema,
  type FilterPresetInput,
  type FilterPresetUpdateInput,
  filterPresetSchema,
  filterPresetsSchema,
} from './schemas';

export const dashboardsQuery = queryOptions({
  queryKey: ['dashboards'] as const,
  queryFn: ({ signal }) =>
    getJson('/dashboards', new URLSearchParams(), { schema: dashboardListSchema, signal }),
  staleTime: 30_000,
});

export const dashboardSubjectsQuery = queryOptions({
  queryKey: ['dashboard-subjects'] as const,
  queryFn: ({ signal }) =>
    getJson('/dashboards/subjects', new URLSearchParams(), {
      schema: dashboardSubjectsSchema,
      signal,
    }),
  staleTime: 5 * 60_000,
});

export const filterPresetsQuery = queryOptions({
  queryKey: ['filter-presets'] as const,
  queryFn: ({ signal }) =>
    getJson('/dashboards/presets', new URLSearchParams(), {
      schema: filterPresetsSchema,
      signal,
    }),
  staleTime: 30_000,
});

export function dashboardVersionsQuery(id: string) {
  return queryOptions({
    queryKey: ['dashboard-versions', id] as const,
    queryFn: ({ signal }) =>
      getJson(`/dashboards/${id}/versions`, new URLSearchParams(), {
        schema: dashboardListSchema.shape.items,
        signal,
      }),
    staleTime: 30_000,
  });
}

export function createDashboard(input: DashboardCreateInput) {
  return requestJson('/dashboards', undefined, {
    schema: dashboardDocumentSchema,
    method: 'POST',
    body: input,
  });
}

export function updateDashboard(id: string, input: DashboardUpdateInput) {
  return requestJson(`/dashboards/${id}`, undefined, {
    schema: dashboardDocumentSchema,
    method: 'PUT',
    body: input,
  });
}

export function deleteDashboard(id: string) {
  return requestEmpty(`/dashboards/${id}`);
}

export function createFilterPreset(input: FilterPresetInput) {
  return requestJson('/dashboards/presets', undefined, {
    schema: filterPresetSchema,
    method: 'POST',
    body: input,
  });
}

export function updateFilterPreset(id: string, input: FilterPresetUpdateInput) {
  return requestJson(`/dashboards/presets/${id}`, undefined, {
    schema: filterPresetSchema,
    method: 'PUT',
    body: input,
  });
}

export function deleteFilterPreset(id: string) {
  return requestEmpty(`/dashboards/presets/${id}`);
}
