import { useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { CourtLines, pct, useLeagueZones, ZoneLayer, ZoneList, zoneLabel, zoneOf } from './CourtZones';
import { HEAT_BOX, heatImage } from './heatMap';
import type { HeatKind } from './heatMap';
import type { ZoneStat } from './CourtZones';
import type { ShotRecord } from '../types';
import { formatDate, formatMatchup } from '../utils';
import { Segmented } from './Common';

type Mode = 'shots' | 'zones' | 'heat';
type Result = 'all' | 'made' | 'missed';
type Tip = { x: number; y: number; flipX: boolean; flipY: boolean; index: number };
type Spot = Omit<Tip, 'index'> & { cx: number; cy: number };

/** Hovering the heat map reads every shot within three feet. */
const REACH = 30;

const isThree = (shot: ShotRecord) => shot.shot_type.startsWith('3');
const points = (shot: ShotRecord) => (shot.shot_made ? (isThree(shot) ? 3 : 2) : 0);
export function ShotChart({ shots }: { shots: ShotRecord[] }) {
  const [mode, setMode] = useState<Mode>('shots');
  const [result, setResult] = useState<Result>('all');
  const [zone, setZone] = useState<string | null>(null);
  const [tip, setTip] = useState<Tip | null>(null);
  const [kind, setKind] = useState<HeatKind>('volume');
  const [spot, setSpot] = useState<Spot | null>(null);
  const [hoverZone, setHoverZone] = useState<string | null>(null);
  const league = useLeagueZones();
  const stage = useRef<HTMLDivElement>(null);

  const keyed = useMemo(() => shots.map((shot) => ({ shot, key: zoneOf(shot.loc_x, shot.loc_y, isThree(shot)) })), [shots]);
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

  const picture = useMemo(() => (mode === 'heat' ? heatImage(inZone, kind, league) : null), [mode, inZone, kind, league]);

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
    return null;
  }, [mode, visible]);

  useEffect(() => { setTip(null); setSpot(null); }, [mode, visible]);

  const onMove = (event: MouseEvent) => {
    const rect = stage.current?.getBoundingClientRect();
    if (!rect) return;
    const x = event.clientX - rect.left, y = event.clientY - rect.top;
    const place = { x, y, flipX: x > rect.width * 0.55, flipY: y > rect.height * 0.6 };
    if (mode === 'heat') { setSpot({ ...place, cx: (x / rect.width) * 508 - 254, cy: (y / rect.height) * 478 - 56 }); return; }
    const index = (event.target as Element).closest('[data-i]')?.getAttribute('data-i');
    if (index == null) { if (tip) setTip(null); return; }
    setTip({ ...place, index: Number(index) });
  };

  if (!shots.length) return <p className="status">No shot data for this selection.</p>;

  const toggleZone = (key: string) => setZone((current) => (current === key ? null : key));
  const tipShot = tip && mode === 'shots' ? visible[tip.index] : undefined;
  const near = spot && mode === 'heat' ? inZone.filter((s) => Math.hypot(s.loc_x - spot.cx, s.loc_y - spot.cy) <= REACH) : null;
  const nearMade = near?.filter((s) => s.shot_made).length ?? 0;

  return (
    <div className="shot-chart">
      <div className="court-column">
        <div className="shot-controls">
          <div className="segmented" role="group" aria-label="Chart view">
            {([['shots', 'Shots'], ['zones', 'Hot zones'], ['heat', 'Heat map']] as [Mode, string][]).map(([key, label]) => <button key={key} type="button" aria-pressed={mode === key} className={mode === key ? 'segment active' : 'segment'} onClick={() => setMode(key)}>{label}</button>)}
          </div>
          {mode === 'heat' && <Segmented label="What the heat map shows" value={kind} options={[['volume', 'Where they shoot'], ['accuracy', 'How well']]} onChange={setKind} />}
          {mode === 'shots' && (
            <div className="segmented" role="group" aria-label="Filter shots by result">
              {(['all', 'made', 'missed'] as Result[]).map((key) => <button key={key} type="button" aria-pressed={result === key} className={result === key ? 'segment active' : 'segment'} onClick={() => setResult(key)}>{key === 'all' ? 'All' : key === 'made' ? 'Made' : 'Missed'}</button>)}
            </div>
          )}
        </div>
        <div className="court-stage" ref={stage} onMouseMove={onMove} onMouseLeave={() => { setTip(null); setSpot(null); }}>
          <svg viewBox="-254 -56 508 478" role="img" aria-label={`${mode === 'zones' ? 'Hot zone map' : mode === 'heat' ? 'Heat map' : 'Shot chart'} of ${mode === 'shots' ? visible.length : inZone.length} shots`} className="court-svg">
            {mode === 'zones' ? <ZoneLayer zones={zones} league={league} hover={hoverZone} selected={zone} onHover={setHoverZone} onSelect={toggleZone} /> : (
              <>
                <rect x={-250} y={-52} width={500} height={470} className="court-wood" />
                <rect x={-80} y={-52} width={160} height={190} className="court-paint" />
                {picture && <><clipPath id="heat-clip"><rect x={-250} y={-52} width={500} height={470} /></clipPath><image key={kind} href={picture} {...HEAT_BOX} preserveAspectRatio="none" clipPath="url(#heat-clip)" className="heat-image" /></>}
                <CourtLines />
              </>
            )}
            {markers}
            {spot && mode === 'heat' && <circle cx={spot.cx} cy={spot.cy} r={REACH} className="heat-cursor" />}
          </svg>
          {tip && tipShot && (
            <div className={`shot-tip ${tip.flipX ? 'flip-x' : ''} ${tip.flipY ? 'flip-y' : ''}`} style={{ left: tip.x, top: tip.y }} role="tooltip">
              {tipShot && (
                <>
                  <div className="tip-head"><span className={`shot-result ${tipShot.shot_made ? 'made' : 'missed'}`}>{tipShot.shot_made ? 'Made' : 'Missed'}</span><strong>{tipShot.shot_distance} ft {isThree(tipShot) ? 'three' : 'two'}</strong></div>
                  <dl>
                    <dt>Type</dt><dd>{tipShot.action_type}</dd>
                    <dt>Zone</dt><dd>{zoneLabel(zoneOf(tipShot.loc_x, tipShot.loc_y, isThree(tipShot))) || 'Backcourt'}</dd>
                    <dt>Game</dt><dd>{formatMatchup(tipShot.matchup)}</dd>
                    <dt>Date</dt><dd>{formatDate(tipShot.game_date)}</dd>
                    <dt>Clock</dt><dd>{tipShot.period > 4 ? `OT${tipShot.period - 4}` : `Q${tipShot.period}`} {tipShot.minutes_remaining}:{String(tipShot.seconds_remaining).padStart(2, '0')}</dd>
                  </dl>
                </>
              )}
            </div>
          )}
          {spot && near && (
            <div className={`shot-tip ${spot.flipX ? 'flip-x' : ''} ${spot.flipY ? 'flip-y' : ''}`} style={{ left: spot.x, top: spot.y }} role="tooltip">
              <div className="tip-head"><strong>{near.length ? `${near.length} shots within 3 feet` : 'No shots from here'}</strong></div>
              {near.length > 0 && <dl><dt>Made</dt><dd>{nearMade}/{near.length} ({pct(nearMade, near.length)})</dd><dt>Points per shot</dt><dd>{(near.reduce((sum, s) => sum + points(s), 0) / near.length).toFixed(2)}</dd><dt>Share of shots</dt><dd>{pct(near.length, inZone.length)}</dd></dl>}
            </div>
          )}
        </div>
        {mode === 'shots'
          ? <div className="shot-legend"><span><i className="dot made" />Made</span><span><i className="dot missed">×</i>Missed</span><span>Hover a shot for details</span></div>
          : mode === 'heat' && kind === 'volume'
            ? <div className="shot-legend"><span>Fewer shots</span><i className="heat-scale fire" /><span>More shots</span></div>
            : <div className="shot-legend"><span>Worse than the league</span><i className="heat-scale" /><span>Better</span><span>{mode === 'zones' ? 'FG% in each zone. Click a zone to focus it.' : 'Points per shot, fainter with few shots'}</span></div>}
      </div>

      <div className="shot-side">
        <div className="shot-summary">
          <div><strong>{pct(summary.made, summary.total)}</strong><span>FG {summary.made}/{summary.total}</span></div>
          <div><strong>{pct(summary.threesMade, summary.threes)}</strong><span>3PT {summary.threesMade}/{summary.threes}</span></div>
          <div><strong>{summary.pps.toFixed(2)}</strong><span>Points per shot</span></div>
          <div><strong>{summary.distance.toFixed(1)}</strong><span>Avg feet</span></div>
        </div>
        <div className="zone-list-head"><span>Filter by zone</span>{zone ? <button type="button" className="link-button" onClick={() => setZone(null)}>Show all</button> : <span>vs league</span>}</div>
        <ZoneList zones={zones} league={league} hover={hoverZone} onHover={setHoverZone} selected={zone} onSelect={toggleZone} />
      </div>
    </div>
  );
}
