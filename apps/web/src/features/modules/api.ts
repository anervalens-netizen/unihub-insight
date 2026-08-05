import { queryOptions } from '@tanstack/react-query';

import { getJson } from '../../lib/api';
import type { GlobalSearch } from '../../lib/search';
import { type ModuleId, moduleAnalyticsSchema } from './schemas';

export function moduleAnalyticsQuery(module: ModuleId, search: GlobalSearch & { period: string }) {
  const params = new URLSearchParams({ period: search.period, comparison: search.comparison });
  if (search.firm) params.set('firm', search.firm);
  if (search.regional) params.set('regional', search.regional);
  if (search.asm) params.set('asm', search.asm);
  if (search.stores) params.set('stores', search.stores);
  if (search.agent) params.set('agent', search.agent);
  return queryOptions({
    queryKey: ['module', module, Object.fromEntries(params)] as const,
    queryFn: ({ signal }) =>
      getJson(`/modules/${module}`, params, {
        schema: moduleAnalyticsSchema,
        signal,
        timeoutMs: 8_000,
      }),
    staleTime: 60_000,
  });
}
