import { useEffect, useState } from 'react';
import type { PlayerDirectoryRow, SeasonStat } from '../types';
import { fractionPct, radarMetrics } from '../utils';
import { Avatar } from './Avatar';
import { BackIcon, CloseIcon, CompareIcon } from './Icons';
import { RadarChart } from './RadarChart';

const COLORS = ['#ff7a1f', '#ffc247', '#f4efe8'];

type Props = {
  ids: number[];
  players: PlayerDirectoryRow[];
  onRemove: (playerId: number) => void;
  onOpen: (playerId: number) => void;
  onBack: () => void;
};

type Row = { label: string; value: (s: SeasonStat) => number | null; format: (v: number | null) => string; lowerIsBetter?: boolean };
const num = (v: number | null) => (v == null ? '-' : v.toFixed(1));
const ROWS: Row[] = [
  { label: 'Games played', value: (s) => s.games_played, format: (v) => (v == null ? '-' : String(v)) },
  { label: 'Minutes', value: (s) => s.minutes, format: num },
  { label: 'Points', value: (s) => s.points, format: num },
  { label: 'Rebounds', value: (s) => s.rebounds, format: num },
  { label: 'Assists', value: (s) => s.assists, format: num },
  { label: 'Steals', value: (s) => s.steals, format: num },
  { label: 'Blocks', value: (s) => s.blocks, format: num },
  { label: 'Turnovers', value: (s) => s.turnovers, format: num, lowerIsBetter: true },
  { label: 'FG%', value: (s) => s.field_goal_pct, format: fractionPct },
  { label: '3P%', value: (s) => s.three_point_pct, format: fractionPct },
  { label: 'FT%', value: (s) => s.free_throw_pct, format: fractionPct },
];

export function Compare({ ids, players, onRemove, onOpen, onBack }: Props) {
  const [stats, setStats] = useState<Record<number, SeasonStat | null>>({});
  const [loading, setLoading] = useState(true);
  const key = ids.join(',');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      const entries = await Promise.all(ids.map(async (id) => {
        try {
          const response = await fetch(`/api/players/${id}/season-stats`);
          const list = response.ok ? ((await response.json()) as SeasonStat[]) : [];
          return [id, list[0] ?? null] as const;
        } catch {
          return [id, null] as const;
        }
      }));
      if (!cancelled) { setStats(Object.fromEntries(entries)); setLoading(false); }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const selected = ids.map((id, i) => ({ id, color: COLORS[i % COLORS.length], player: players.find((p) => p.player_id === id), stat: stats[id] ?? null })).filter((entry) => entry.player);

  if (!selected.length) {
    return <section className="panel"><button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button><div className="empty-state"><span className="empty-mark"><CompareIcon /></span><p>Nothing to compare yet.</p><small>Use the compare button on players in the directory or shortlist.</small></div></section>;
  }

  const withStats = selected.filter((s) => s.stat);

  return (
    <section className="panel compare-page">
      <div className="panel-header">
        <div><h2>Compare players</h2></div>
        <button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button>
      </div>
      <div className="compare-chips">
        {selected.map((s) => (
          <div className="compare-chip" key={s.id} style={{ borderColor: s.color }}>
            <Avatar name={s.player!.full_name} nbaPlayerId={s.player!.nba_player_id} className="player-thumb" />
            <button type="button" className="player-link" onClick={() => onOpen(s.id)}>{s.player!.full_name}</button>
            <button type="button" className="icon-button small" aria-label={`Remove ${s.player!.full_name} from comparison`} onClick={() => onRemove(s.id)}><CloseIcon /></button>
          </div>
        ))}
      </div>
      {loading ? <div className="skeleton-block" aria-busy="true"><span className="skeleton" style={{ width: '100%', height: '16rem' }} /></div> : (
        <div className="compare-body">
          <div className="radar-wrap compare-radar">
            {withStats.length ? <RadarChart label="Percentile comparison radar" series={withStats.map((s) => ({ name: s.player!.full_name, color: s.color, metrics: radarMetrics(s.stat!, 'all') }))} /> : <p className="status">No percentile data available.</p>}
          </div>
          <div className="detail-records-scroll">
            <table className="detail-records-table compare-table">
              <thead>
                <tr><th scope="col">Latest season</th>{selected.map((s) => <th scope="col" key={s.id} style={{ borderBottom: `3px solid ${s.color}` }}>{s.player!.full_name}<small className="rank">{s.stat?.season ?? 'no data'}</small></th>)}</tr>
              </thead>
              <tbody>
                {ROWS.map((row) => {
                  const values = selected.map((s) => (s.stat ? row.value(s.stat) : null));
                  const valid = values.filter((v): v is number => v != null);
                  const best = valid.length > 1 ? (row.lowerIsBetter ? Math.min(...valid) : Math.max(...valid)) : null;
                  return <tr key={row.label}><th scope="row">{row.label}</th>{values.map((v, i) => <td key={selected[i].id} className={best != null && v === best ? 'best' : ''}>{row.format(v)}<i className="cmp-bar"><em style={{ width: `${v != null ? (v / Math.max(...valid, 0.0001)) * 100 : 0}%`, background: selected[i].color }} /></i></td>)}</tr>;
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="radar-note">Radar shows each player's percentile against the whole pool for their latest season. Highlighted cells are the best value in each row.</p>
    </section>
  );
}
