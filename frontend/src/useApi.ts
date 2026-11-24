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

export function useApi<T>(path: string): { data: T | null; error: string | null } {
  const [state, setState] = useState<{ path: string; data: T | null; error: string | null }>({ path, data: null, error: null });
  useEffect(() => {
    let cancelled = false;
    load<T>(path)
      .then((data) => { if (!cancelled) setState({ path, data, error: null }); })
      .catch((err: Error) => { if (!cancelled) setState({ path, data: null, error: err.message }); });
    return () => { cancelled = true; };
  }, [path]);
  return state.path === path ? state : { data: null, error: null };
}
