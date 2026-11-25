import { useId, useState } from 'react';
import type { MouseEvent } from 'react';
import { smoothPath, useWidth } from '../useWidth';

export type TrendPoint = { key: string; value: number | null; title: string; note?: string; won?: boolean };
type Props = {
  points: TrendPoint[]; label: string; digits?: number; suffix?: string; signed?: boolean; onPick?: (key: string) => void; height?: number; tone?: 'average' | 'result';
  /** Games in the moving average; 0 is the average of the season so far. */
  rolling?: number;
  /** Average of the games from..to, when it is not the plain mean (percentages). */
  averageOf?: (from: number, to: number) => number | null;
  color?: string; low?: string;
};

const L = 44, R = 18, T = 24, B = 10;

/** One bar per game with a smooth average line: warm above the overall average, cool below it. */
export function BarTrend({ points, label, digits = 0, suffix = '', signed, rolling = 5, averageOf, onPick, height = 280, tone = 'average', color = '#ff6a13', low = '#5aa0f2' }: Props) {
  const id = useId().replace(/:/g, '');
  const [stage, W] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const values = points.map((p) => p.value).filter((v): v is number => v != null);
  const H = height;
  const plain = (from: number, to: number) => { const slice = points.slice(from, to + 1).map((p) => p.value).filter((v): v is number => v != null); return slice.length ? slice.reduce((s, v) => s + v, 0) / slice.length : null; };
  const average = averageOf ?? plain;
  if (values.length < 2) return <p className="status">Not enough games for a chart.</p>;
  const lo = Math.min(0, ...values), hi = Math.max(1, ...values);
  const y = (v: number) => T + ((hi - v) / (hi - lo)) * (H - T - B);
  const step = (W - L - R) / points.length;
  const bar = Math.max(2, Math.min(30, step * 0.62));
  const x = (i: number) => L + step * i + step / 2;
  const mean = average(0, points.length - 1) ?? 0;
  const text = (v: number, d = digits) => `${signed && v > 0 ? '+' : ''}${v.toFixed(d)}${suffix}`;
  const fine = Math.max(1, digits);
  const start = rolling === 0 ? Math.min(2, points.length - 1) : Math.min(rolling - 1, points.length - 1);
  const track = points.map((_, i) => (i < start ? null : average(rolling === 0 ? 0 : i - rolling + 1, i)));
  const line = track.flatMap((v, i) => (v == null ? [] : [[x(i), y(v)] as const]));
  const path = smoothPath(line);
  const area = line.length > 1 ? `${path}L${line[line.length - 1][0]} ${y(mean)}L${line[0][0]} ${y(mean)}Z` : '';
  const last = line[line.length - 1];
  const raw = (hi - lo) / 4, power = 10 ** Math.floor(Math.log10(raw));
  const tick = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / tick) * tick; v <= hi + 1e-9; v += tick) ticks.push(Number(v.toFixed(4)));
  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const i = Math.floor((e.clientX - e.currentTarget.getBoundingClientRect().left - L) / step);
    setHover(i >= 0 && i < points.length ? i : null);
  };
  const tip = hover != null ? points[hover] : null;
  const at = hover != null ? track[hover] : null;
  const good = (p: TrendPoint) => (tone === 'result' ? p.won : (p.value ?? 0) >= mean);
  const windowName = rolling === 0 ? 'Season so far' : `Last ${rolling}`;
  return (
    <div className="bar-trend" ref={stage}>
      <svg width={W} height={H} role="img" aria-label={`${label}, ${values.length} games, average ${text(mean, fine)}`} onMouseMove={onMove} onMouseLeave={() => setHover(null)} onClick={() => { if (tip && onPick) onPick(tip.key); }} className={onPick ? 'clickable' : ''}>
        <defs>
          <linearGradient id={`${id}u`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor={color} stopOpacity=".95" /><stop offset="1" stopColor={color} stopOpacity=".28" /></linearGradient>
          <linearGradient id={`${id}d`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#8b857e" stopOpacity=".6" /><stop offset="1" stopColor="#8b857e" stopOpacity=".16" /></linearGradient>
          <linearGradient id={`${id}n`} x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#8b857e" stopOpacity=".16" /><stop offset="1" stopColor="#8b857e" stopOpacity=".6" /></linearGradient>
          <linearGradient id={`${id}l`} gradientUnits="userSpaceOnUse" x1="0" x2="0" y1={T} y2={H - B}>
            <stop offset="0" stopColor="#ffe08a" /><stop offset={Math.max(0, (y(mean) - T) / (H - T - B) - 0.02)} stopColor="#ffb347" /><stop offset={Math.min(1, (y(mean) - T) / (H - T - B) + 0.02)} stopColor={low} /><stop offset="1" stopColor={low} />
          </linearGradient>
          <clipPath id={`${id}a`}><rect x={L} y={0} width={Math.max(0, W - L - R)} height={Math.max(0, y(mean))} /></clipPath>
          <clipPath id={`${id}b`}><rect x={L} y={y(mean)} width={Math.max(0, W - L - R)} height={Math.max(0, H - y(mean))} /></clipPath>
        </defs>
        {ticks.map((v) => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="grid" /><text x={L - 8} y={y(v) + 4} textAnchor="end" className="tick-text">{v}{suffix}</text></g>)}
        {points.map((p, i) => p.value != null && <rect key={p.key} x={x(i) - bar / 2} width={bar} y={Math.min(y(p.value), y(0))} height={Math.max(2, Math.abs(y(p.value) - y(0)))} rx={Math.min(4, bar / 2)} fill={`url(#${id}${good(p) ? 'u' : p.value < 0 ? 'n' : 'd'})`} className={`trend-bar ${hover === i ? 'lit' : hover != null ? 'rest' : ''}`} />)}
        {area && <><path d={area} clipPath={`url(#${id}a)`} fill="#ffb347" fillOpacity=".2" pointerEvents="none" /><path d={area} clipPath={`url(#${id}b)`} fill={low} fillOpacity=".2" pointerEvents="none" /></>}
        <line x1={L} x2={W - R} y1={y(mean)} y2={y(mean)} className="mean" />
        {line.length > 1 && <><path d={path} className="rolling-back" /><path d={path} className="rolling" stroke={`url(#${id}l)`} /></>}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={T - 8} y2={H - B} className="cross" />}
        {at != null && hover != null ? <circle cx={x(hover)} cy={y(at)} r={6} className="trend-dot" fill={at >= mean ? '#ffb347' : low} /> : last && <circle cx={last[0]} cy={last[1]} r={5.5} className="trend-dot pulse" fill={(track[track.length - 1] ?? 0) >= mean ? '#ffb347' : low} />}
      </svg>
      <span className="trend-mean" style={{ top: y(mean) }}>{text(mean, fine)} average</span>
      {tip && hover != null && (
        <div className={`trend-tip ${hover > points.length * 0.6 ? 'flip' : ''}`} style={{ left: x(hover) }}><b>{tip.value == null ? 'No attempts' : `${text(tip.value)} ${label.toLowerCase()}`}</b><span>{tip.title}</span>{tip.note && <span>{tip.note}</span>}{at != null && <span className="tip-line"><i style={{ background: at >= mean ? '#ffb347' : low }} />{windowName}: {text(at, fine)}</span>}</div>
      )}
    </div>
  );
}
