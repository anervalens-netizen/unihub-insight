import { queryOptions } from '@tanstack/react-query';

import { getJson } from '../../lib/api';
import type { GlobalSearch } from '../../lib/search';
import { monthlyReviewSchema } from './schemas';

export function monthlyReviewQuery(
  search: GlobalSearch & { period: string },
  recentMonths: number,
) {
  const params = new URLSearchParams({
    period: search.period,
    comparison: search.comparison,
    recent_months: String(recentMonths),
  });
  if (search.firm) params.set('firm', search.firm);
  if (search.regional) params.set('regional', search.regional);
  if (search.stores) params.set('stores', search.stores);
  if (search.agent) params.set('agent', search.agent);
  return queryOptions({
    queryKey: ['monthly-review', Object.fromEntries(params)] as const,
    queryFn: ({ signal }) =>
      getJson('/monthly-review', params, {
        schema: monthlyReviewSchema,
        signal,
        timeoutMs: 12_000,
      }),
    staleTime: 60_000,
  });
}
