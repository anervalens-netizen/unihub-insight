import { queryOptions } from '@tanstack/react-query';

import { getJson } from '../../lib/api';
import { userSchema } from './schemas';

export const identityQuery = queryOptions({
  queryKey: ['identity'] as const,
  queryFn: ({ signal }) => getJson('/me', new URLSearchParams(), { schema: userSchema, signal }),
  staleTime: 5 * 60_000,
});
