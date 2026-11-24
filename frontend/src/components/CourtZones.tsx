import { useMemo } from 'react';
import type { LeagueShotZone } from '../types';
import { useApi } from '../useApi';

export type Zone = { key: string; label: string; x: number; y: number };
export type ZoneStat = { att: number; made: number };
export type ZoneMap = Map<string, ZoneStat>;

/** The twelve half-court zones, with the spot where each label sits on the court. */
export const ZONES: Zone[] = [
  { key: 'rim', label: 'At the rim', x: 0, y: 16 },
  { key: 'paint', label: 'Paint', x: 0, y: 86 },
  { key: 'mid-L', label: 'Left baseline', x: -148, y: 22 },
  { key: 'mid-LC', label: 'Left elbow', x: -116, y: 158 },
  { key: 'mid-C', label: 'Top of the key', x: 0, y: 186 },
  { key: 'mid-RC', label: 'Right elbow', x: 116, y: 158 },
  { key: 'mid-R', label: 'Right baseline', x: 148, y: 22 },
  { key: 'corner-L', label: 'Left corner 3', x: -235, y: 12 },
  { key: 'three-LC', label: 'Left wing 3', x: -186, y: 208 },
  { key: 'three-C', label: 'Top of the arc 3', x: 0, y: 276 },
  { key: 'three-RC', label: 'Right wing 3', x: 186, y: 208 },
  { key: 'corner-R', label: 'Right corner 3', x: 235, y: 12 },
];
export const MIN_ATTEMPTS = 5;

export function zoneKey(basic: string, area: string): string {
  const side = area.match(/\((\w+)\)/)?.[1] ?? '';
  if (basic === 'Restricted Area') return 'rim';
  if (basic.startsWith('In The Paint')) return 'paint';
  if (basic === 'Mid-Range') return `mid-${side}`;
  if (basic === 'Left Corner 3') return 'corner-L';
  if (basic === 'Right Corner 3') return 'corner-R';
  if (basic === 'Above the Break 3' && side !== 'BC') return `three-${side}`;
  return 'backcourt';
}

/** Pie slice from the hoop between two angles (degrees, clockwise on screen from the right baseline). */
function wedge(from: number, to: number, r = 900): string {
  const p = (deg: number) => `${(Math.cos((deg * Math.PI) / 180) * r).toFixed(1)} ${(Math.sin((deg * Math.PI) / 180) * r).toFixed(1)}`;
  return `M0 0L${p(from)}A${r} ${r} 0 0 1 ${p(to)}Z`;
}
/** Painted back to front: later shapes cover earlier ones. */
const THREE_SHAPES: [string, string][] = [['three-RC', wedge(-20, 72)], ['three-C', wedge(72, 108)], ['three-LC', wedge(108, 200)]];
const MID_SHAPES: [string, string][] = [
  ['mid-R', wedge(-90, 36)], ['mid-RC', wedge(36, 72)], ['mid-C', wedge(72, 108)], ['mid-LC', wedge(108, 144)], ['mid-L', wedge(144, 270)],
  ['mid-R', wedge(-90, 60, 160)], ['mid-C', wedge(60, 120, 160)], ['mid-L', wedge(120, 270, 160)],
];

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

export function toZoneMap(rows: LeagueShotZone[]): ZoneMap {
  const map: ZoneMap = new Map();
  for (const row of rows) {
    const key = zoneKey(row.shot_zone_basic, row.shot_zone_area);
    const entry = map.get(key) ?? { att: 0, made: 0 };
    entry.att += row.attempts; entry.made += row.made;
    map.set(key, entry);
  }
  return map;
}

export function useLeagueZones(): ZoneMap | null {
  const { data } = useApi<LeagueShotZone[]>('/players/league-shot-zones');
  return useMemo(() => (data ? toZoneMap(data) : null), [data]);
}

type LayerProps = { zones: ZoneMap; league: ZoneMap | null; hover?: string | null; selected?: string | null; onHover?: (key: string | null) => void; onSelect?: (key: string) => void };

/** The coloured half court: zone shapes, court lines and labels. */
export function ZoneLayer({ zones, league, hover, selected, onHover, onSelect }: LayerProps) {
  const props = (key: string) => ({
    fill: fillFor(zoneDiff(zones.get(key), league?.get(key))),
    className: `zone-shape ${hover === key || selected === key ? 'lit' : ''} ${selected === key ? 'sel' : ''} ${selected && selected !== key ? 'dim' : ''}`,
    onMouseEnter: () => onHover?.(key),
    onMouseLeave: () => onHover?.(null),
    onClick: () => onSelect?.(key),
  });
  const shape = ([key, d]: [string, string], i: number) => <path key={`${key}${i}`} d={d} {...props(key)} />;
  return (
    <>
      <defs>
        <clipPath id="court-all"><rect x={-250} y={-52} width={500} height={470} /></clipPath>
        <clipPath id="court-deep"><circle r={330} /></clipPath>
        <clipPath id="court-two"><path d="M-220 -52V89.5A237.5 237.5 0 0 0 220 89.5V-52Z" /></clipPath>
      </defs>
      <g className="zone-layer" clipPath="url(#court-all)">
        <g clipPath="url(#court-deep)">{THREE_SHAPES.map(shape)}</g>
        <rect x={-250} y={-52} width={30} height={141.5} {...props('corner-L')} />
        <rect x={220} y={-52} width={30} height={141.5} {...props('corner-R')} />
        <g clipPath="url(#court-two)">{MID_SHAPES.map(shape)}</g>
        <rect x={-80} y={-52} width={160} height={190} {...props('paint')} />
        <circle r={40} {...props('rim')} />
      </g>
      <CourtLines />
      {ZONES.map((z) => {
        const stat = zones.get(z.key);
        if (!stat) return null;
        const corner = z.key.startsWith('corner');
        return (
          <text key={z.key} x={z.x} y={z.y} className={corner ? 'zone-label small' : 'zone-label'} textAnchor="middle">
            {Math.round((stat.made / stat.att) * 100)}%
            {!corner && <tspan x={z.x} dy="14" className="zone-sub">{stat.made}/{stat.att}</tspan>}
          </text>
        );
      })}
    </>
  );
}

export function ZoneCourt({ label, picker, ...layer }: LayerProps & { label: string; picker?: boolean }) {
  return <svg viewBox="-254 -56 508 400" role="img" aria-label={label} className={picker ? 'court-svg zone-picker' : 'court-svg'}><ZoneLayer {...layer} /></svg>;
}
