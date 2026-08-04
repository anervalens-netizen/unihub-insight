import type { ZodType } from 'zod';

import { environment } from './environment';

export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(message: string, status: number, requestId: string | null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.requestId = requestId;
  }
}

interface RequestOptions<T> {
  schema: ZodType<T>;
  signal?: AbortSignal;
  timeoutMs?: number;
}

export async function getJson<T>(
  path: string,
  search: URLSearchParams,
  { schema, signal, timeoutMs = 5_000 }: RequestOptions<T>,
): Promise<T> {
  const timeoutController = new AbortController();
  const timeout = window.setTimeout(() => timeoutController.abort(), timeoutMs);
  const abort = (): void => timeoutController.abort();
  if (signal?.aborted) timeoutController.abort();
  else signal?.addEventListener('abort', abort, { once: true });

  try {
    const url = `${environment.apiBaseUrl}${path}?${search.toString()}`;
    const response = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: timeoutController.signal,
    });

    const requestId = response.headers.get('x-request-id');
    if (!response.ok) {
      let message = `Request failed with status ${response.status}.`;
      try {
        const body = (await response.json()) as { detail?: unknown };
        if (typeof body.detail === 'string') message = body.detail;
      } catch {
        // Keep the bounded HTTP status message when the body is not JSON.
      }
      throw new ApiError(message, response.status, requestId);
    }

    const body: unknown = await response.json();
    return schema.parse(body);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request cancelled or deadline exceeded.', 0, null);
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}
