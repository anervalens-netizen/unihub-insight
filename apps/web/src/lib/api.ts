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
  method?: 'GET' | 'POST' | 'PUT';
  body?: unknown;
}

function requestUrl(path: string, search?: URLSearchParams): string {
  const suffix = search && search.size > 0 ? `?${search.toString()}` : '';
  return `${environment.apiBaseUrl}${path}${suffix}`;
}

async function parseError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get('x-request-id');
  let message = `Request failed with status ${response.status}.`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') message = body.detail;
  } catch {
    // Keep the bounded status message for non-JSON failures.
  }
  return new ApiError(message, response.status, requestId);
}

export async function requestJson<T>(
  path: string,
  search: URLSearchParams | undefined,
  {
    schema,
    signal,
    timeoutMs = 5_000,
    method = 'GET',
    body,
  }: RequestOptions<T>,
): Promise<T> {
  const timeoutController = new AbortController();
  const timeout = window.setTimeout(() => timeoutController.abort(), timeoutMs);
  const abort = (): void => timeoutController.abort();
  if (signal?.aborted) timeoutController.abort();
  else signal?.addEventListener('abort', abort, { once: true });

  try {
    const response = await fetch(requestUrl(path, search), {
      method,
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: timeoutController.signal,
    });
    if (!response.ok) throw await parseError(response);
    const payload: unknown = await response.json();
    return schema.parse(payload);
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

export async function requestEmpty(
  path: string,
  { signal, timeoutMs = 5_000 }: { signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<void> {
  const timeoutController = new AbortController();
  const timeout = window.setTimeout(() => timeoutController.abort(), timeoutMs);
  const abort = (): void => timeoutController.abort();
  if (signal?.aborted) timeoutController.abort();
  else signal?.addEventListener('abort', abort, { once: true });
  try {
    const response = await fetch(requestUrl(path), {
      method: 'DELETE',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: timeoutController.signal,
    });
    if (!response.ok) throw await parseError(response);
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

export function getJson<T>(
  path: string,
  search: URLSearchParams,
  options: Omit<RequestOptions<T>, 'method' | 'body'>,
): Promise<T> {
  return requestJson(path, search, options);
}
