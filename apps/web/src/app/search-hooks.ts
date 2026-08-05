import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback } from 'react';

import { type GlobalSearch, type GlobalSearchPatch, globalSearchSchema } from '../lib/search';

export function useGlobalSearch(): GlobalSearch {
  return useSearch({ from: '__root__' });
}

export function useUpdateGlobalSearch() {
  const navigate = useNavigate();
  return useCallback(
    (patch: GlobalSearchPatch, replace = false): void => {
      void navigate({
        search: (previous) => globalSearchSchema.parse({ ...previous, ...patch }),
        replace,
      });
    },
    [navigate],
  );
}
