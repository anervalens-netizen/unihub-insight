import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback } from 'react';

import {
  type GlobalSearch,
  type GlobalSearchPatch,
  globalSearchSchema,
} from '../lib/search';

export function useGlobalSearch(): GlobalSearch {
  return useSearch({ from: '__root__' });
}

export function useUpdateGlobalSearch() {
  const navigate = useNavigate({ from: '__root__' });
  const search = useGlobalSearch();
  return useCallback(
    (patch: GlobalSearchPatch, replace = false): void => {
      const nextSearch = globalSearchSchema.parse({ ...search, ...patch });
      void navigate({ search: nextSearch, replace });
    },
    [navigate, search],
  );
}
