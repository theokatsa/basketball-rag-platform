import { useEffect, useState } from 'react';

/** Page numbers with gaps: 1 … 4 [5] 6 … 23 */
function pages(page: number, count: number): (number | null)[] {
  const keep = new Set([1, count, page - 1, page, page + 1].filter((n) => n >= 1 && n <= count));
  if (page <= 3) [2, 3, 4].forEach((n) => n <= count && keep.add(n));
  if (page >= count - 2) [count - 1, count - 2, count - 3].forEach((n) => n >= 1 && keep.add(n));
  const sorted = [...keep].sort((a, b) => a - b);
  return sorted.flatMap((n, i) => (i && n - sorted[i - 1] === 2 ? [n - 1, n] : i && n - sorted[i - 1] > 2 ? [null, n] : [n]));
}

export function Pagination({ page, pageCount, onPage, label = 'Pages' }: { page: number; pageCount: number; onPage: (page: number) => void; label?: string }) {
  if (pageCount <= 1) return null;
  return (
    <nav className="pager" aria-label={label}>
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">‹</button>
      {pages(page, pageCount).map((n, i) => (n == null ? <span key={`gap${i}`} aria-hidden="true">…</span> : <button type="button" key={n} aria-current={n === page ? 'page' : undefined} aria-label={`Page ${n}`} onClick={() => onPage(n)}>{n}</button>))}
      <button type="button" disabled={page >= pageCount} onClick={() => onPage(page + 1)} aria-label="Next page">›</button>
    </nav>
  );
}

/** One page of a list; goes back to page 1 whenever `reset` changes. */
export function usePaged<T>(items: T[], size: number, reset: string) {
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [reset]);
  const pageCount = Math.max(1, Math.ceil(items.length / size));
  const safe = Math.min(page, pageCount);
  return { items: items.slice((safe - 1) * size, safe * size), offset: (safe - 1) * size, page: safe, pageCount, onPage: setPage };
}
