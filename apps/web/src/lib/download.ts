import { environment } from './environment';
import type { GlobalSearch } from './search';

export function analyticsSearchParams(search: GlobalSearch & { period: string }): URLSearchParams {
  const params = new URLSearchParams({
    period: search.period,
    comparison: search.comparison,
  });
  if (search.firm) params.set('firm', search.firm);
  if (search.regional) params.set('regional', search.regional);
  if (search.asm) params.set('asm', search.asm);
  if (search.stores) params.set('stores', search.stores);
  if (search.agent) params.set('agent', search.agent);
  return params;
}

function filenameFromDisposition(value: string | null, fallback: string): string {
  if (!value) return fallback;
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (utf8) return decodeURIComponent(utf8);
  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? fallback;
}

export async function downloadExcel(
  path: string,
  params: URLSearchParams,
  fallbackName: string,
): Promise<void> {
  const response = await fetch(`${environment.apiBaseUrl}${path}?${params}`, {
    credentials: 'include',
    headers: { Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  });
  if (!response.ok) {
    let message = `Exportul a eșuat (${response.status}).`;
    try {
      const payload = (await response.json()) as { detail?: unknown };
      if (typeof payload.detail === 'string') message = payload.detail;
    } catch {
      // Keep the bounded status message.
    }
    throw new Error(message);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filenameFromDisposition(
    response.headers.get('content-disposition'),
    fallbackName,
  );
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}
