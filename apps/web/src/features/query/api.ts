import { queryOptions } from '@tanstack/react-query';

import { getJson, requestBlob, requestJson } from '../../lib/api';
import { analyticsSearchParams } from '../../lib/download';
import type { GlobalSearch } from '../../lib/search';
import {
  analyticsCatalogSchema,
  type InspectRequest,
  inspectResponseSchema,
  type QueryBatchRequest,
  queryBatchResponseSchema,
} from './schemas';

export const analyticsCatalogQuery = () =>
  queryOptions({
    queryKey: ['analytics-catalog'] as const,
    queryFn: ({ signal }) =>
      getJson('/catalog', new URLSearchParams(), {
        schema: analyticsCatalogSchema,
        signal,
        timeoutMs: 8_000,
      }),
    staleTime: 5 * 60_000,
  });

function analyticsParams(search: GlobalSearch & { period: string }) {
  return analyticsSearchParams(search);
}

export function queryBatch(
  input: QueryBatchRequest,
  search: GlobalSearch & { period: string },
  signal?: AbortSignal,
) {
  return requestJson('/query/batch', analyticsParams(search), {
    schema: queryBatchResponseSchema,
    method: 'POST',
    body: input,
    ...(signal ? { signal } : {}),
    timeoutMs: 8_000,
  });
}

export function queryBatchOptions(
  input: QueryBatchRequest,
  search: GlobalSearch & { period: string },
) {
  return queryOptions({
    queryKey: ['query-batch', search, input] as const,
    queryFn: ({ signal }) => queryBatch(input, search, signal),
    staleTime: 30_000,
  });
}

export function inspectQuery(
  input: InspectRequest,
  search: GlobalSearch & { period: string },
  signal?: AbortSignal,
) {
  return requestJson('/query/inspect', analyticsParams(search), {
    schema: inspectResponseSchema,
    method: 'POST',
    body: input,
    ...(signal ? { signal } : {}),
    timeoutMs: 8_000,
  });
}

export function buildInspectRequest(
  snapshotId: string,
  dashboardId: string | null,
  query: InspectRequest['query'],
): InspectRequest {
  return { snapshot_id: snapshotId, dashboard_id: dashboardId, query, page: 1, page_size: 100 };
}

export function buildExportRequest(
  snapshotId: string,
  dashboardId: string | null,
  query: InspectRequest['query'],
): InspectRequest {
  return buildInspectRequest(snapshotId, dashboardId, query);
}

export function inspectQueryOptions(
  input: InspectRequest,
  search: GlobalSearch & { period: string },
  enabled: boolean,
) {
  return {
    queryKey: ['query-inspect', input, search] as const,
    queryFn: ({ signal }: { signal: AbortSignal }) => inspectQuery(input, search, signal),
    enabled,
    staleTime: 30_000,
  };
}

export function exportQueryCsv(
  input: InspectRequest,
  search: GlobalSearch & { period: string },
  signal?: AbortSignal,
): Promise<{ blob: Blob; filename: string | null }> {
  return requestBlob('/query/export.csv', analyticsParams(search), {
    method: 'POST',
    body: input,
    ...(signal ? { signal } : {}),
    timeoutMs: 8_000,
  });
}
