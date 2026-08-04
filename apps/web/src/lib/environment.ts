const normalizeBaseUrl = (value: string): string => value.replace(/\/+$/, '');

export const environment = {
  apiBaseUrl: normalizeBaseUrl(
    import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8100/api/v1',
  ),
  retailBaseUrl: normalizeBaseUrl(
    import.meta.env.VITE_RETAIL_BASE_URL ?? 'https://retail.unihub.ro',
  ),
} as const;
