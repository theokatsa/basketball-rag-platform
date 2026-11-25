import { useId, useMemo } from 'react';
import type { MouseEvent, ReactNode } from 'react';
import type { ZoneRow } from '../types';
import { useApi } from '../useApi';

export type Zone = { key: string; label: string; group: 'Paint' | 'Mid-range' | 'Three'; x: number; y: number; size?: 's' | 'line' | 'up' };
export type ZoneStat = { att: number; made: number };
export type ZoneMap = Map<string, ZoneStat>;

/**
 * Every spot in the half court belongs to exactly one zone. The zones come from shot
 * coordinates, so the shape that is drawn is the shape that is counted.
 * backend/app/services/shot_service.py holds the same rules; keep them in step.
 */
export const ZONES: Zone[] = [
  { key: 'rim', label: 'At the rim', group: 'Paint', x: 0, y: 6 },
  { key: 'lane-low', label: 'Short paint', group: 'Paint', x: 0, y: 60, size: 'line' },
  { key: 'lane-high', label: 'Floater range', group: 'Paint', x: 0, y: 99 },
  { key: 'ft', label: 'Free throw line', group: 'Mid-range', x: 0, y: 159 },
  { key: 'key', label: 'Top of the key', group: 'Mid-range', x: 0, y: 211 },
  { key: 'base-L', label: 'Left baseline', group: 'Mid-range', x: -150, y: 12 },
  { key: 'base-R', label: 'Right baseline', group: 'Mid-range', x: 150, y: 12 },
  { key: 'midw-L', label: 'Left elbow', group: 'Mid-range', x: -132, y: 122 },
  { key: 'midw-R', label: 'Right elbow', group: 'Mid-range', x: 132, y: 122 },
  { key: 'corner-L', label: 'Left corner 3', group: 'Three', x: -235, y: 18, size: 'up' },
  { key: 'corner-R', label: 'Right corner 3', group: 'Three', x: 235, y: 18, size: 'up' },
  { key: 'wing-L', label: 'Left wing 3', group: 'Three', x: -216, y: 138, size: 's' },
  { key: 'wing-R', label: 'Right wing 3', group: 'Three', x: 216, y: 138, size: 's' },
  { key: 'slot-L', label: 'Left slot 3', group: 'Three', x: -134, y: 217, size: 's' },
  { key: 'slot-R', label: 'Right slot 3', group: 'Three', x: 134, y: 217, size: 's' },
  { key: 'top', label: 'Top of the arc 3', group: 'Three', x: 0, y: 257, size: 's' },
  { key: 'deep', label: 'Deep 3 (28 ft and out)', group: 'Three', x: 0, y: 312 },
];
export const zoneLabel = (key: string) => ZONES.find((z) => z.key === key)?.label ?? '';
export const isThreeZone = (key: string) => ZONES.find((z) => z.key === key)?.group === 'Three';
export const MIN_ATTEMPTS = 5;

export function zoneOf(x: number, y: number, three: boolean): string {
  const r2 = x * x + y * y, ax = Math.abs(x), side = x < 0 ? 'L' : 'R';
  if (y > 418) return 'backcourt';
  if (three) {
    if (y <= 89 && ax >= 200) return `corner-${side}`;
    if (r2 >= 78400) return 'deep';
    if (ax <= 80) return 'top';
    return y < ax ? `wing-${side}` : `slot-${side}`;
  }
  if (r2 <= 1600) return 'rim';
  if (ax <= 80) return y <= 70 ? 'lane-low' : y <= 137 ? 'lane-high' : r2 <= 36100 ? 'ft' : 'key';
  return y < 80 ? `base-${side}` : `midw-${side}`;
}

/** One shape per zone, painted back to front inside its clip. */
const THREE_SHAPES: [string, string][] = [
  ['wing-L', 'M-80 -60H-420V420L-80 80Z'], ['wing-R', 'M80 -60H420V420L80 80Z'],
  ['slot-L', 'M-80 80L-420 420H-80Z'], ['slot-R', 'M80 80L420 420H80Z'],
  ['top', 'M-80 80H80V420H-80Z'],
];
const TWO_SHAPES: [string, string][] = [
  ['base-L', 'M-80 -52H-240V80H-80Z'], ['base-R', 'M80 -52H240V80H80Z'],
  ['midw-L', 'M-80 80H-240V240H-80Z'], ['midw-R', 'M80 80H240V240H80Z'],
  ['key', 'M-80 150H80V240H-80Z'],
  ['ft', 'M-80 137.5H80V172.3A190 190 0 0 1 -80 172.3Z'],
  ['lane-high', 'M-80 70H80V137.5H-80Z'], ['lane-low', 'M-80 -52H80V70H-80Z'],
];

const TWO_POINT = 'M-220 -52V89.5A237.5 237.5 0 0 0 220 89.5V-52Z';

export const pct = (made: number, att: number) => (att ? `${((made / att) * 100).toFixed(1)}%` : '–');
export const signed = (v: number, digits = 1) => `${v > 0 ? '+' : ''}${v.toFixed(digits)}`;

const COLD = [58, 118, 200];
const NEUTRAL = [104, 98, 92];
const HOT = [255, 106, 19];
/** t from -1 (cold) through 0 (average) to +1 (hot). */
export function heat(t: number): string {
  const k = Math.min(1, Math.abs(t));
  const end = t < 0 ? COLD : HOT;
  return `rgb(${NEUTRAL.map((c, i) => Math.round(c + (end[i] - c) * k)).join(',')})`;
}

export function CourtLines() {
  return (
    <g className="court-lines" fill="none">
      <rect x={-250} y={-52} width={500} height={470} />
      <rect x={-60} y={-52} width={120} height={190} className="thin" />
      <rect x={-80} y={-52} width={160} height={190} />
      <circle cx={0} cy={138} r={60} />
      <path d="M-40 -8V0A40 40 0 0 0 40 0V-8" />
      <line x1={-30} y1={-9} x2={30} y2={-9} />
      <circle cx={0} cy={0} r={7.5} className="court-hoop" />
      <path d="M-220 -52V89.5A237.5 237.5 0 0 0 220 89.5V-52" />
      <path d="M-60 418A60 60 0 0 1 60 418" />
    </g>
  );
}

/** Difference to the league FG% in percentage points; null when the sample is too small. */
export const zoneDiff = (own?: ZoneStat, base?: ZoneStat): number | null => (own && base && own.att >= MIN_ATTEMPTS ? (own.made / own.att - base.made / base.att) * 100 : null);
export const fillFor = (diff: number | null) => (diff == null ? '#232326' : heat(diff / 10));

export function toZoneMap(rows: ZoneRow[]): ZoneMap {
  const map: ZoneMap = new Map();
  for (const row of rows) {
    const entry = map.get(row.zone) ?? { att: 0, made: 0 };
    entry.att += row.attempts; entry.made += row.made;
    map.set(row.zone, entry);
  }
  return map;
}

export function useLeagueZones(): ZoneMap | null {
  const { data } = useApi<ZoneRow[]>('/shots/league-zones');
  return useMemo(() => (data ? toZoneMap(data) : null), [data]);
}

type LayerProps = { zones: ZoneMap; league: ZoneMap | null; hover?: string | null; selected?: string | null; onHover?: (key: string | null) => void; onSelect?: (key: string) => void };

/** The zone under the pointer, from court coordinates: the same rule that counts the shots. */
function zoneAt(event: MouseEvent<SVGElement>): string | null {
  const svg = event.currentTarget.ownerSVGElement, matrix = svg?.getScreenCTM();
  if (!svg || !matrix) return null;
  const { x, y } = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
  if (Math.abs(x) > 250 || y < -52 || y > 418) return null;
  const three = y <= 89.5 ? Math.abs(x) > 220 : x * x + y * y > 237.5 * 237.5;
  return zoneOf(x, y, three);
}

const BACK: [string, ReactNode][] = [['deep', <rect x={-250} y={89.5} width={500} height={330} />]];
const CORNERS: [string, ReactNode][] = [['corner-L', <rect x={-250} y={-52} width={30} height={141.5} />], ['corner-R', <rect x={220} y={-52} width={30} height={141.5} />]];

/** The coloured half court: zone shapes, court lines and labels. */
export function ZoneLayer({ zones, league, hover, selected, onHover, onSelect }: LayerProps) {
  const id = useId().replace(/:/g, '');
  const group = (key: string, shape: ReactNode) => {
    const state = `${hover === key ? 'lit' : ''} ${selected === key ? 'sel' : ''} ${selected && selected !== key && hover !== key ? 'dim' : ''}`;
    return <g key={key} fill={fillFor(zoneDiff(zones.get(key), league?.get(key)))} className={`zone-shape ${state}`}>{shape}</g>;
  };
  /** A bright outline on top, so a chosen zone never looks like a merely hot one. */
  const outline = (key: string | null | undefined, kind: 'sel' | 'lit') => {
    if (!key) return null;
    const three = THREE_SHAPES.find(([k]) => k === key), two = TWO_SHAPES.find(([k]) => k === key);
    const className = `zone-outline ${kind}`;
    if (key === 'rim') return <circle r={40} className={className} />;
    if (key === 'deep') return <path d="M-250 418V126A280 280 0 0 0 250 126V418Z" className={className} />;
    if (key.startsWith('corner')) return <rect x={key.endsWith('L') ? -250 : 220} y={-52} width={30} height={141.5} className={className} />;
    return <g clipPath={`url(#${id}${three ? 'ring' : 'two'})`}>{three && <g mask={`url(#${id}out)`}><path d={three[1]} className={className} /><path d="M-250 126A280 280 0 0 0 250 126" className={`${className} thin`} clipPath={`url(#${id}k${key})`} /><path d="M-220 89.5A237.5 237.5 0 0 0 220 89.5" className={`${className} thin`} clipPath={`url(#${id}k${key})`} /></g>}{two && <><path d={two[1]} className={className} /><path d="M-220 -52V89.5A237.5 237.5 0 0 0 220 89.5V-52" className={`${className} thin`} clipPath={`url(#${id}k${key})`} /></>}</g>;
  };
  return (
    <>
      <defs>
        <clipPath id={`${id}all`}><rect x={-250} y={-52} width={500} height={470} /></clipPath>
        <clipPath id={`${id}ring`}><circle r={280} /></clipPath>
        <clipPath id={`${id}two`}><path d={TWO_POINT} /></clipPath>
        <mask id={`${id}out`} maskUnits="userSpaceOnUse" x={-260} y={-60} width={520} height={490}><rect x={-250} y={-52} width={500} height={470} fill="#fff" /><path d={TWO_POINT} fill="#000" /><rect x={-250} y={-52} width={30} height={141.5} fill="#000" /><rect x={220} y={-52} width={30} height={141.5} fill="#000" /></mask>
        {[...THREE_SHAPES, ...TWO_SHAPES].map(([key, d]) => <clipPath key={key} id={`${id}k${key}`}><path d={d} /></clipPath>)}
      </defs>
      <g className="zone-layer" clipPath={`url(#${id}all)`}>
        {BACK.map(([key, shape]) => group(key, shape))}
        <g clipPath={`url(#${id}ring)`}>{THREE_SHAPES.map(([key, d]) => group(key, <path d={d} />))}</g>
        <path d="M-250 126A280 280 0 0 0 250 126" className="zone-edge" />
        {CORNERS.map(([key, shape]) => group(key, shape))}
        <g clipPath={`url(#${id}two)`}>{TWO_SHAPES.map(([key, d]) => group(key, <path d={d} />))}</g>
        {group('rim', <circle r={40} />)}
      </g>
      <CourtLines />
      <g clipPath={`url(#${id}all)`}>{hover !== selected && outline(hover, 'lit')}{outline(selected, 'sel')}</g>
      {ZONES.map((z) => {
        const stat = zones.get(z.key);
        if (!stat?.att) return null;
        const share = `${Math.round((stat.made / stat.att) * 100)}%`, count = `${stat.made}/${stat.att}`;
        const dim = selected && selected !== z.key && hover !== z.key ? 'faint' : '';
        if (z.size === 'up') return <text key={z.key} transform={`translate(${z.x} ${z.y}) rotate(${z.x < 0 ? -90 : 90})`} className={`zone-label small ${dim}`} textAnchor="middle" y={4}>{share}<tspan className="zone-sub" dx={5}>{count}</tspan></text>;
        if (z.size === 'line') return <text key={z.key} x={z.x} y={z.y} className={`zone-label small ${dim}`} textAnchor="middle">{share}<tspan className="zone-sub" dx={5}>{count}</tspan></text>;
        return (
          <text key={z.key} x={z.x} y={z.y} className={`zone-label ${z.size ? 'small' : ''} ${dim}`} textAnchor="middle">
            {share}<tspan x={z.x} dy={z.size ? 11 : 13} className="zone-sub">{count}</tspan>
          </text>
        );
      })}
      {(onHover || onSelect) && (
        <rect
          x={-250} y={-52} width={500} height={470} className={onSelect ? 'zone-catcher pick' : 'zone-catcher'}
          onMouseMove={(e) => { const key = zoneAt(e); if (key !== hover) onHover?.(key); }}
          onMouseLeave={() => onHover?.(null)}
          // The second click of a double click is ignored, so it cannot undo the first.
          onClick={(e) => { const key = zoneAt(e); if (key && e.detail < 2) onSelect?.(key); }}
        />
      )}
    </>
  );
}

export function ZoneCourt({ label, picker, ...layer }: LayerProps & { label: string; picker?: boolean }) {
  return <svg viewBox="-254 -56 508 400" role="img" aria-label={label} className={picker ? 'court-svg zone-picker' : 'court-svg'}><ZoneLayer {...layer} /></svg>;
}

/** One zone in a list beside the court; hovering it lights the same zone on the court. */
export function ZoneList({ zones, league, hover, onHover, selected, onSelect, other }: { zones: ZoneMap; league: ZoneMap | null; hover: string | null; onHover: (key: string | null) => void; selected?: string | null; onSelect?: (key: string) => void; other?: ZoneMap }) {
  return (
    <div className="zone-list">
      {ZONES.map((z) => {
        const stat = zones.get(z.key), rival = other?.get(z.key), diff = zoneDiff(stat, league?.get(z.key));
        const wins = stat && rival && stat.att >= 10 && rival.att >= 10 && stat.made / stat.att > rival.made / rival.att;
        return (
          <button key={z.key} type="button" tabIndex={onSelect ? 0 : -1} disabled={Boolean(onSelect) && !stat} aria-pressed={onSelect ? selected === z.key : undefined} className={`zone-row ${onSelect ? '' : 'still'} ${selected === z.key ? 'active' : ''} ${hover === z.key ? 'lit' : ''} ${wins ? 'wins' : ''}`} onClick={(e) => { if (e.detail < 2) onSelect?.(z.key); }} onMouseEnter={() => onHover(z.key)} onMouseLeave={() => onHover(null)}>
            <i style={{ background: fillFor(diff) }} />
            <span className="zone-name">{z.label}</span>
            <span className="zone-att">{stat ? `${stat.made}/${stat.att}` : '0'}</span>
            <span className="zone-pct">{stat ? pct(stat.made, stat.att) : '–'}</span>
            <span className={`zone-diff ${diff == null ? '' : diff > 0 ? 'up' : 'down'}`} title={diff == null ? `Fewer than ${MIN_ATTEMPTS} attempts` : 'Percentage points against the league average from this zone'}>{diff == null ? '–' : signed(diff)}</span>
          </button>
        );
      })}
    </div>
  );
}
