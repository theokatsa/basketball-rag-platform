import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { CourtLines, fillFor, heat, MIN_ATTEMPTS, pct, signed, useLeagueZones, ZoneLayer, zoneDiff, zoneKey, ZONES } from './CourtZones';
import type { ZoneStat } from './CourtZones';
import type { ShotRecord } from '../types';
import { formatDate, formatMatchup } from '../utils';

type Mode = 'shots' | 'zones' | 'heat';
type Result = 'all' | 'made' | 'missed';
type Tip = { x: number; y: number; flipX: boolean; flipY: boolean; index: number };

const CELL = 25;

const isThree = (shot: ShotRecord) => shot.shot_type.startsWith('3');
const points = (shot: ShotRecord) => (shot.shot_made ? (isThree(shot) ? 3 : 2) : 0);
export function ShotChart({ shots }: { shots: ShotRecord[] }) {
  const [mode, setMode] = useState<Mode>('shots');
  const [result, setResult] = useState<Result>('all');
  const [zone, setZone] = useState<string | null>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  const [hoverZone, setHoverZone] = useState<string | null>(null);
  const league = useLeagueZones();
  const stage = useRef<HTMLDivElement>(null);

  const keyed = useMemo(() => shots.map((shot) => ({ shot, key: zoneKey(shot.shot_zone_basic, shot.shot_zone_area) })), [shots]);
  const zones = useMemo(() => {
    const map = new Map<string, ZoneStat>();
    for (const { shot, key } of keyed) {
      const entry = map.get(key) ?? { att: 0, made: 0 };
      entry.att += 1; entry.made += shot.shot_made ? 1 : 0;
      map.set(key, entry);
    }
    return map;
  }, [keyed]);
  const inZone = useMemo(() => keyed.filter((k) => !zone || k.key === zone).map((k) => k.shot), [keyed, zone]);
  const visible = useMemo(() => inZone.filter((s) => result === 'all' || (result === 'made') === s.shot_made), [inZone, result]);

  const diffOf = (key: string) => zoneDiff(zones.get(key), league?.get(key));
  const zoneFill = (key: string) => fillFor(diffOf(key));

  const summary = useMemo(() => {
    const threes = inZone.filter(isThree);
    const total = inZone.length;
    return {
      made: inZone.filter((s) => s.shot_made).length,
      total,
      threes: threes.length,
      threesMade: threes.filter((s) => s.shot_made).length,
      distance: total ? inZone.reduce((sum, s) => sum + s.shot_distance, 0) / total : 0,
      pps: total ? inZone.reduce((sum, s) => sum + points(s), 0) / total : 0,
    };
  }, [inZone]);

  const cells = useMemo(() => {
    const map = new Map<string, { x: number; y: number; att: number; pts: number; made: number }>();
    for (const shot of inZone) {
      const x = (Math.floor(shot.loc_x / CELL) + 0.5) * CELL;
      const y = (Math.floor(shot.loc_y / CELL) + 0.5) * CELL;
      const entry = map.get(`${x},${y}`) ?? { x, y, att: 0, pts: 0, made: 0 };
      entry.att += 1; entry.pts += points(shot); entry.made += shot.shot_made ? 1 : 0;
      map.set(`${x},${y}`, entry);
    }
    // One or two lucky shots should not paint a spot hot.
    const min = inZone.length > 300 ? 3 : 2;
    return [...map.values()].filter((c) => c.att >= min);
  }, [inZone]);

  // Memoised so moving the tooltip never re-renders a thousand markers.
  const markers = useMemo(() => {
    if (mode === 'shots') {
      // Misses first so makes are drawn on top.
      return visible.map((_, i) => i).sort((a, b) => Number(visible[a].shot_made) - Number(visible[b].shot_made)).map((i) => {
        const shot = visible[i];
        return (
          <g key={i} data-i={i} className={shot.shot_made ? 'shot-dot made' : 'shot-dot missed'} transform={`translate(${shot.loc_x} ${shot.loc_y})`}>
            <circle r={7} className="hit" />
            {shot.shot_made ? <circle r={4} className="mark" /> : <path d="M-3 -3L3 3M-3 3L3 -3" className="mark" />}
          </g>
        );
      });
    }
    if (mode === 'heat') return cells.map((c, i) => <circle key={`${c.x},${c.y}`} data-i={i} cx={c.x} cy={c.y} r={Math.min(CELL / 2, 3.5 + Math.sqrt(c.att) * 1.8)} className="heat-cell" fill={heat((c.pts / c.att - 1.1) / 0.5)} />);
    return null;
  }, [mode, visible, cells]);

  useEffect(() => { setTip(null); }, [mode, visible]);

  const onMove = (event: MouseEvent) => {
    const index = (event.target as Element).closest('[data-i]')?.getAttribute('data-i');
    const rect = stage.current?.getBoundingClientRect();
    if (index == null || !rect) { if (tip) setTip(null); return; }
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setTip({ x, y, flipX: x > rect.width * 0.55, flipY: y > rect.height * 0.6, index: Number(index) });
  };

  if (!shots.length) return <p className="status">No shot data for this selection.</p>;

  const toggleZone = (key: string) => setZone((current) => (current === key ? null : key));
  const tipShot = tip && mode === 'shots' ? visible[tip.index] : undefined;
  const tipCell = tip && mode === 'heat' ? cells[tip.index] : undefined;

  return (
    <div className="shot-chart">
      <div className="court-column">
        <div className="shot-controls">
          <div className="segmented" role="group" aria-label="Chart view">
            {([['shots', 'Shots'], ['zones', 'Hot zones'], ['heat', 'Heat map']] as [Mode, string][]).map(([key, label]) => <button key={key} type="button" aria-pressed={mode === key} className={mode === key ? 'segment active' : 'segment'} onClick={() => setMode(key)}>{label}</button>)}
          </div>
          {mode === 'shots' && (
            <div className="segmented" role="group" aria-label="Filter shots by result">
              {(['all', 'made', 'missed'] as Result[]).map((key) => <button key={key} type="button" aria-pressed={result === key} className={result === key ? 'segment active' : 'segment'} onClick={() => setResult(key)}>{key === 'all' ? 'All' : key === 'made' ? 'Made' : 'Missed'}</button>)}
            </div>
          )}
        </div>
        <div className="court-stage" ref={stage} onMouseMove={onMove} onMouseLeave={() => setTip(null)}>
          <svg viewBox="-254 -56 508 478" role="img" aria-label={`${mode === 'zones' ? 'Hot zone map' : mode === 'heat' ? 'Heat map' : 'Shot chart'} of ${mode === 'shots' ? visible.length : inZone.length} shots`} className="court-svg">
            {mode === 'zones' ? <ZoneLayer zones={zones} league={league} hover={hoverZone} selected={zone} onHover={setHoverZone} onSelect={toggleZone} /> : <CourtLines />}
            {markers}
          </svg>
          {tip && (tipShot || tipCell) && (
            <div className={`shot-tip ${tip.flipX ? 'flip-x' : ''} ${tip.flipY ? 'flip-y' : ''}`} style={{ left: tip.x, top: tip.y }} role="tooltip">
              {tipShot && (
                <>
                  <div className="tip-head"><span className={`shot-result ${tipShot.shot_made ? 'made' : 'missed'}`}>{tipShot.shot_made ? 'Made' : 'Missed'}</span><strong>{tipShot.shot_distance} ft {isThree(tipShot) ? 'three' : 'two'}</strong></div>
                  <dl>
                    <dt>Type</dt><dd>{tipShot.action_type}</dd>
                    <dt>Zone</dt><dd>{tipShot.shot_zone_basic}</dd>
                    <dt>Game</dt><dd>{formatMatchup(tipShot.matchup)}</dd>
                    <dt>Date</dt><dd>{formatDate(tipShot.game_date)}</dd>
                    <dt>Clock</dt><dd>{tipShot.period > 4 ? `OT${tipShot.period - 4}` : `Q${tipShot.period}`} {tipShot.minutes_remaining}:{String(tipShot.seconds_remaining).padStart(2, '0')}</dd>
                  </dl>
                </>
              )}
              {tipCell && (
                <>
                  <div className="tip-head"><strong>{tipCell.att} shots from here</strong></div>
                  <dl><dt>Made</dt><dd>{tipCell.made}/{tipCell.att} ({pct(tipCell.made, tipCell.att)})</dd><dt>Points per shot</dt><dd>{(tipCell.pts / tipCell.att).toFixed(2)}</dd></dl>
                </>
              )}
            </div>
          )}
        </div>
        {mode === 'shots'
          ? <div className="shot-legend"><span><i className="dot made" />Made</span><span><i className="dot missed">×</i>Missed</span><span>Hover a shot for details</span></div>
          : <div className="shot-legend"><span>Cold</span><i className="heat-scale" /><span>Hot</span><span>{mode === 'zones' ? 'FG% vs league average' : 'Points per shot; size = attempts'}</span></div>}
      </div>

      <div className="shot-side">
        <div className="shot-summary">
          <div><strong>{pct(summary.made, summary.total)}</strong><span>FG {summary.made}/{summary.total}</span></div>
          <div><strong>{pct(summary.threesMade, summary.threes)}</strong><span>3PT {summary.threesMade}/{summary.threes}</span></div>
          <div><strong>{summary.pps.toFixed(2)}</strong><span>Points per shot</span></div>
          <div><strong>{summary.distance.toFixed(1)}</strong><span>Avg feet</span></div>
        </div>
        <div className="zone-list-head"><span>Filter by zone</span>{zone ? <button type="button" className="link-button" onClick={() => setZone(null)}>Show all</button> : <span>vs league</span>}</div>
        <div className="zone-list" role="group" aria-label="Filter by court zone">
          {ZONES.map((z) => {
            const stat = zones.get(z.key);
            const diff = diffOf(z.key);
            return (
              <button key={z.key} type="button" disabled={!stat} aria-pressed={zone === z.key} className={`zone-row ${zone === z.key ? 'active' : ''} ${hoverZone === z.key ? 'lit' : ''}`} onClick={() => toggleZone(z.key)} onMouseEnter={() => setHoverZone(z.key)} onMouseLeave={() => setHoverZone(null)}>
                <i style={{ background: zoneFill(z.key) }} />
                <span className="zone-name">{z.label}</span>
                <span className="zone-att">{stat ? `${stat.made}/${stat.att}` : '0'}</span>
                <span className="zone-pct">{stat ? pct(stat.made, stat.att) : '–'}</span>
                <span className={`zone-diff ${diff == null ? '' : diff > 0 ? 'up' : 'down'}`} title={diff == null ? `Fewer than ${MIN_ATTEMPTS} attempts` : 'Percentage points against the league average from this zone'}>{diff == null ? '–' : signed(diff)}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
