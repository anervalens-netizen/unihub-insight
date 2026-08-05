import { useLocation, useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback } from 'react';

import { type GlobalSearch, type GlobalSearchPatch, globalSearchSchema } from '../lib/search';

export function useGlobalSearch(): GlobalSearch {
  return useSearch({ from: '__root__' });
}

export function useUpdateGlobalSearch() {
  const navigate = useNavigate();
  const pathname = useLocation({ select: (location) => location.pathname });
  const search = useGlobalSearch();
  return useCallback(
    (patch: GlobalSearchPatch, replace = false): void => {
      const nextSearch = globalSearchSchema.parse({ ...search, ...patch });
      // The pathname is runtime-dynamic but constrained to the registered router location.
      void navigate({ to: pathname, search: nextSearch, replace } as never);
    },
    [navigate, pathname, search],
  );
}
