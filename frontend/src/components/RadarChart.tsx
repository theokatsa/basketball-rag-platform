import { topLabel } from '../utils';
import type { RadarMetric } from '../utils';

export type RadarSeries = { name: string; color: string; metrics: RadarMetric[] };

const CENTER = 140;
const RADIUS = 92;
const LABEL_RADIUS = 116;

const strength = (percentile: number | null) => (percentile == null ? 0 : 1 - percentile);
const angleFor = (index: number, count: number) => (Math.PI * 2 * index) / count - Math.PI / 2;
const point = (index: number, count: number, scale: number) => {
  const angle = angleFor(index, count);
  return [CENTER + Math.cos(angle) * RADIUS * scale, CENTER + Math.sin(angle) * RADIUS * scale] as const;
};

/** Strength 1 = best in the pool, 0 = worst. Rings are drawn at 25/50/75/100. */
export function RadarChart({ series, label }: { series: RadarSeries[]; label: string }) {
  const labels = series[0]?.metrics ?? [];
  const count = labels.length;
  if (!count) return null;
  const ring = (scale: number) => labels.map((_, i) => point(i, count, scale).join(',')).join(' ');
  return (
    <svg viewBox="0 0 280 280" role="img" aria-label={label} className="radar-svg">
      {[0.25, 0.5, 0.75, 1].map((scale) => (
        <polygon key={scale} points={ring(scale)} className={scale === 0.5 ? 'radar-ring radar-ring-mid' : 'radar-ring'} />
      ))}
      {labels.map((_, i) => {
        const [x, y] = point(i, count, 1);
        return <line key={i} x1={CENTER} y1={CENTER} x2={x} y2={y} className="radar-spoke" />;
      })}
      {series.map((s) => (
        <g key={s.name}>
          <polygon points={s.metrics.map((m, i) => point(i, count, strength(m.percentile)).join(',')).join(' ')} fill={s.color} fillOpacity={0.2} stroke={s.color} strokeWidth={2.5} strokeLinejoin="round" />
          {s.metrics.map((m, i) => {
            const [x, y] = point(i, count, strength(m.percentile));
            return <circle key={i} cx={x} cy={y} r={3.5} fill={s.color} stroke="#0b0b0c" strokeWidth={1.5}><title>{`${s.name} ${m.label}: ${topLabel(m.percentile)}`}</title></circle>;
          })}
        </g>
      ))}
      {labels.map((metric, i) => {
        const angle = angleFor(i, count);
        const x = CENTER + Math.cos(angle) * LABEL_RADIUS;
        const y = CENTER + Math.sin(angle) * LABEL_RADIUS;
        const anchor = Math.abs(Math.cos(angle)) < 0.2 ? 'middle' : Math.cos(angle) > 0 ? 'start' : 'end';
        return (
          <text key={metric.label} x={x} y={y} textAnchor={anchor} dominantBaseline="middle" className="radar-label">
            {metric.label}
            {series.length === 1 && <tspan x={x} dy="1.25em" className="radar-sub">{topLabel(series[0].metrics[i].percentile)}</tspan>}
          </text>
        );
      })}
    </svg>
  );
}

export function averageStrength(metrics: RadarMetric[]): number {
  return metrics.length ? metrics.reduce((sum, m) => sum + strength(m.percentile), 0) / metrics.length : 0;
}

export function toneFor(avg: number): string {
  return avg >= 0.95 ? '#ffc247' : avg >= 0.75 ? '#ff7a1f' : '#9c968d';
}
