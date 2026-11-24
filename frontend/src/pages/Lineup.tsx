import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead } from '../components/Common';
import { CloseIcon } from '../components/Icons';
import { PlayerPicker } from '../components/PlayerPicker';
import type { PlayerTotals } from '../types';
import { usePersisted } from '../usePersisted';

type Line = Record<'points' | 'rebounds' | 'assists' | 'steals' | 'blocks' | 'turnovers' | 'threes' | 'threePct' | 'ts' | 'fta', number>;
type RowDef = { key: keyof Line; label: string; higher?: boolean; suffix?: string };
const ROWS: RowDef[] = [
  { key: 'points', label: 'Points', higher: true }, { key: 'ts', label: 'True shooting %', higher: true, suffix: '%' }, { key: 'threes', label: 'Threes made', higher: true },
  { key: 'threePct', label: 'Three-point %', higher: true, suffix: '%' }, { key: 'fta', label: 'Free throw attempts', higher: true }, { key: 'rebounds', label: 'Rebounds', higher: true },
  { key: 'assists', label: 'Assists', higher: true }, { key: 'steals', label: 'Steals', higher: true }, { key: 'blocks', label: 'Blocks', higher: true }, { key: 'turnovers', label: 'Turnovers' },
];
const EMPTY: (number | null)[] = [null, null, null, null, null];

/** Each player's rates stretched to 48 minutes, then added up. */
function project(list: PlayerTotals[]): Line {
  const sum = (pick: (t: PlayerTotals) => number) => list.reduce((s, t) => s + (t.minutes ? (pick(t) / t.minutes) * 48 : 0), 0);
  const points = sum((t) => t.points), fga = sum((t) => t.field_goals_attempted), fta = sum((t) => t.free_throws_attempted);
  const threes = sum((t) => t.three_pointers_made), tpa = sum((t) => t.three_pointers_attempted);
  return { points, rebounds: sum((t) => t.rebounds), assists: sum((t) => t.assists), steals: sum((t) => t.steals), blocks: sum((t) => t.blocks), turnovers: sum((t) => t.turnovers), threes, threePct: tpa ? (threes / tpa) * 100 : 0, ts: fga + fta ? (points / (2 * (fga + 0.44 * fta))) * 100 : 0, fta };
}

/** An average lineup: five copies of the whole league's combined rates. */
function leagueLine(all: PlayerTotals[]): Line {
  const total = { ...all[0] };
  for (const row of all.slice(1)) for (const key of Object.keys(total) as (keyof PlayerTotals)[]) total[key] += row[key];
  return project(new Array<PlayerTotals>(5).fill(total));
}

export function Lineup() {
  const { byId, totals, loading, error, open } = useApp();
  const [slots, setSlots] = usePersisted<(number | null)[]>('lineup', EMPTY);
  const league = useMemo(() => { const all = Object.values(totals); return all.length ? leagueLine(all) : null; }, [totals]);
  if (error) return <LoadError message={error} />;
  const ids = slots.filter((id): id is number => id != null);
  const chosen = ids.map((id) => totals[id]).filter((t) => t != null);
  const line = chosen.length === 5 && league ? project(chosen) : null;
  const rows = line && league ? ROWS.map((r) => {
    const change = (line[r.key] / league[r.key] - 1) * (r.higher ? 1 : -1);
    const limit = r.suffix ? 0.03 : 0.1; // percentages move less than counts
    return { ...r, own: line[r.key], base: league[r.key], change, kind: change > limit ? 'up' : change < -limit ? 'down' : '' };
  }) : [];
  const names = (kind: string) => rows.filter((r) => r.kind === kind).sort((a, b) => Math.abs(b.change) - Math.abs(a.change)).map((r) => r.label.toLowerCase()).join(', ');
  const positions = ids.map((id) => byId.get(id)?.position ?? '');
  const notes = [!positions.some((p) => p.includes('Guard')) && 'There is no guard in this group.', !positions.some((p) => p.includes('Center')) && 'There is no center in this group.', positions.filter((p) => p.includes('Center')).length > 2 && 'Three or more centers may lack speed and spacing.'].filter((n) => n !== false);
  const set = (i: number, id: number | null) => setSlots(slots.map((v, k) => (k === i ? id : v)));
  return (
    <>
      <PageHead title="Lineup Builder" intro="Pick five players and see the group against an average lineup.">{ids.length > 0 && <button type="button" className="ghost-button" onClick={() => setSlots(EMPTY)}>Clear lineup</button>}</PageHead>
      <div className="lineup-slots">
        {slots.map((id, i) => {
          const p = id != null ? byId.get(id) : undefined;
          return (
            <div className={`panel lineup-slot ${p ? 'filled' : ''}`} key={i}>
              {p ? (
                <>
                  <button type="button" className="icon-button small slot-clear" aria-label={`Remove ${p.full_name}`} onClick={() => set(i, null)}><CloseIcon /></button>
                  <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="podium-photo" />
                  <button type="button" className="player-link" onClick={() => open(p.player_id)}>{p.full_name}</button>
                  <small>{p.club}, {p.position}</small>
                  <small>{p.points?.toFixed(1)} pts, {p.rebounds?.toFixed(1)} reb, {p.assists?.toFixed(1)} ast</small>
                </>
              ) : <><span className="slot-no">{i + 1}</span><PlayerPicker label={`Player ${i + 1}`} placeholder="Add a player" exclude={ids} onPick={(pid) => set(i, pid)} /></>}
            </div>
          );
        })}
      </div>
      {loading ? <Loading /> : !line ? <div className="empty-state"><p>{5 - ids.length} more {5 - ids.length === 1 ? 'player' : 'players'} to go.</p><small>The analysis appears once all five places are filled.</small></div> : (
        <>
          <div className="two-col">
            <section className="panel"><h2>Strengths</h2><p className="verdict">{names('up') || 'Nothing clearly above average.'}</p></section>
            <section className="panel"><h2>Gaps</h2><p className="verdict">{names('down') || 'Nothing clearly below average.'}</p>{notes.map((n) => <p key={n}>{n}</p>)}</section>
          </div>
          <section className="panel">
            <div className="panel-header"><div><h2>Per 48 minutes</h2><p>The white line marks an average lineup</p></div></div>
            <div className="lineup-bars">{rows.map((r) => { const max = Math.max(r.own, r.base) * 1.12 || 1; return <div className={`lineup-row ${r.kind}`} key={r.key}><span>{r.label}</span><i><em style={{ width: `${(r.own / max) * 100}%` }} /><u style={{ left: `${(r.base / max) * 100}%` }} /></i><b>{r.own.toFixed(1)}{r.suffix}</b><small>avg {r.base.toFixed(1)}{r.suffix}</small></div>; })}</div>
            <p className="radar-note">Each player's own rates are stretched to 48 minutes. Fit, fatigue and sharing one ball are not modelled, so totals run high for groups of stars.</p>
          </section>
        </>
      )}
    </>
  );
}
