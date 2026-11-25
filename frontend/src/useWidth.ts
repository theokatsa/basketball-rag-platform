import { useCallback, useRef, useState } from 'react';

/** The element's width in pixels, so charts can be drawn without stretching. Works for elements that appear later. */
export function useWidth<T extends HTMLElement>(initial = 1000) {
  const observer = useRef<ResizeObserver | null>(null);
  const [width, setWidth] = useState(initial);
  const ref = useCallback((element: T | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!element) return;
    observer.current = new ResizeObserver(([entry]) => setWidth(Math.max(280, Math.round(entry.contentRect.width))));
    observer.current.observe(element);
  }, []);
  return [ref, width] as const;
}

/** A smooth curve through the points that never overshoots them (monotone cubic). */
export function smoothPath(points: (readonly [number, number])[]): string {
  if (points.length < 3) return points.map(([x, y], i) => `${i ? 'L' : 'M'}${x} ${y}`).join('');
  const n = points.length;
  const slope = points.slice(1).map(([x, y], i) => (y - points[i][1]) / (x - points[i][0]));
  const tangent = points.map((_, i) => {
    if (i === 0) return slope[0];
    if (i === n - 1) return slope[n - 2];
    return slope[i - 1] * slope[i] <= 0 ? 0 : (2 * slope[i - 1] * slope[i]) / (slope[i - 1] + slope[i]);
  });
  let d = `M${points[0][0]} ${points[0][1]}`;
  for (let i = 0; i < n - 1; i++) {
    const [x0, y0] = points[i], [x1, y1] = points[i + 1], third = (x1 - x0) / 3;
    d += `C${x0 + third} ${y0 + tangent[i] * third} ${x1 - third} ${y1 - tangent[i + 1] * third} ${x1} ${y1}`;
  }
  return d;
}
