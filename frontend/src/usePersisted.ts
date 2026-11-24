import { useEffect, useState } from 'react';

/** State that survives moving between pages (per browser tab). */
export function usePersisted<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try { const raw = sessionStorage.getItem(key); return raw ? (JSON.parse(raw) as T) : initial; } catch { return initial; }
  });
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ } }, [key, value]);
  return [value, setValue] as const;
}
