import { queryOptions } from '@tanstack/react-query';

import { getJson } from '../../lib/api';
import { analyticsSearchParams } from '../../lib/download';
import type { GlobalSearch } from '../../lib/search';
import { type ModuleId, moduleAnalyticsSchema } from './schemas';

export function moduleAnalyticsQuery(module: ModuleId, search: GlobalSearch & { period: string }) {
  const params = analyticsSearchParams(search);
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
