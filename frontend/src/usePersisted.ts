import { createContext, useContext, useEffect, useState } from 'react';

/** The page a piece of remembered state belongs to, so a fresh visit can forget exactly that page. */
export const PageScope = createContext('app');

const storageKey = (scope: string, key: string) => `page:${scope}:${key}`;

/**
 * State that survives leaving a page and coming back with Back, or following a link (per browser tab).
 * Opening the page from the main navigation starts it fresh: see forgetPage.
 */
export function usePersisted<T>(key: string, initial: T) {
  const full = storageKey(useContext(PageScope), key);
  const [value, setValue] = useState<T>(() => {
    try { const raw = sessionStorage.getItem(full); return raw ? (JSON.parse(raw) as T) : initial; } catch { return initial; }
  });
  useEffect(() => { try { sessionStorage.setItem(full, JSON.stringify(value)); } catch { /* storage unavailable */ } }, [full, value]);
  return [value, setValue] as const;
}

/** Sets a page's remembered value before going there, e.g. which board the Top players page opens on. */
export function rememberFor(scope: string, key: string, value: unknown) {
  try { sessionStorage.setItem(storageKey(scope, key), JSON.stringify(value)); } catch { /* storage unavailable */ }
}

/** Forgets everything a page remembered, so it opens as new. */
export function forgetPage(scope: string) {
  try {
    const prefix = storageKey(scope, '');
    for (let i = sessionStorage.length - 1; i >= 0; i -= 1) {
      const key = sessionStorage.key(i);
      if (key?.startsWith(prefix)) sessionStorage.removeItem(key);
    }
  } catch { /* storage unavailable */ }
}
