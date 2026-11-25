import { useEffect, useState } from 'react';

const cache = new Map<string, Promise<unknown>>();

/** GET once per page load and share the result between pages. */
function load<T>(path: string): Promise<T> {
  let request = cache.get(path) as Promise<T> | undefined;
  if (!request) {
    request = fetch(`/api${path}`).then(async (response) => {
      if (!response.ok) throw new Error('Unable to load this data from the API.');
      return (await response.json()) as T;
    });
    request.catch(() => cache.delete(path));
    cache.set(path, request);
  }
  return request;
}
/** Forget an answer that changed, so the next page asks again. */
export const forget = (start: string) => { for (const key of cache.keys()) if (key.startsWith(start)) cache.delete(key); };

/** A null path loads nothing yet. */
export function useApi<T>(path: string | null): { data: T | null; error: string | null } {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string | null }>({ path, data: null, error: null });
  useEffect(() => {
    if (path == null) return;
    let cancelled = false;
    load<T>(path)
      .then((data) => { if (!cancelled) setState({ path, data, error: null }); })
      .catch((err: Error) => { if (!cancelled) setState({ path, data: null, error: err.message }); });
    return () => { cancelled = true; };
  }, [path]);
  return state.path === path ? state : { data: null, error: null };
}

/** POST/PUT/DELETE with JSON; throws the server's own message. */
export async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { method, headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'The request failed. Check the values and try again.');
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}
