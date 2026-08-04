import { queryOptions } from '@tanstack/react-query';

import { getJson } from '../../lib/api';
import type { GlobalSearch } from '../../lib/search';
import { filterOptionsSchema, overviewSchema } from './schemas';

export function filterOptionsQuery(period: string) {
  return queryOptions({
    queryKey: ['filter-options', period] as const,
    queryFn: ({ signal }) =>
      getJson('/filters/options', new URLSearchParams({ period }), {
        schema: filterOptionsSchema,
        signal,
      }),
    staleTime: 5 * 60_000,
  });
}

export function overviewQuery(search: GlobalSearch & { period: string }) {
  const params = new URLSearchParams({
    period: search.period,
    comparison: search.comparison,
  });
  if (search.firm) params.set('firm', search.firm);
  if (search.regional) params.set('regional', search.regional);
  if (search.asm) params.set('asm', search.asm);
  if (search.stores) params.set('stores', search.stores);
  if (search.agent) params.set('agent', search.agent);

  return queryOptions({
    queryKey: ['overview', Object.fromEntries(params)] as const,
    queryFn: ({ signal }) =>
      getJson('/overview', params, {
        schema: overviewSchema,
        signal,
      }),
    staleTime: 60_000,
  });
}
