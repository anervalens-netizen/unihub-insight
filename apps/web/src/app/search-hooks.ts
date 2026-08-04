import { useNavigate, useSearch } from '@tanstack/react-router';
import { useCallback } from 'react';

import type { GlobalSearch } from '../lib/search';

export function useGlobalSearch(): GlobalSearch {
  return useSearch({ from: '__root__' });
}

export function useUpdateGlobalSearch() {
  const navigate = useNavigate();
  return useCallback(
    (patch: Partial<GlobalSearch>, replace = false): void => {
      void navigate({
        search: (previous) => ({ ...previous, ...patch }),
        replace,
      });
    },
    [navigate],
  );
}
