import { useMemo, useState } from 'react';
import type { GameLog } from '../types';
import { formatDate } from '../utils';

const STEP = 25;
const pct = (made: number, att: number) => (att ? `${Math.round((made / att) * 100)}%` : '–');
const avg = (logs: GameLog[], pick: (l: GameLog) => number) => (logs.length ? logs.reduce((s, l) => s + pick(l), 0) / logs.length : 0);

function Shooting({ made, att }: { made: number; att: number }) {
  return <span className="shooting"><b>{made}/{att}</b><small>{pct(made, att)}</small></span>;
}

export function GameLogs({ logs }: { logs: GameLog[] }) {
  const [season, setSeason] = useState('all');
  const [count, setCount] = useState(STEP);
  const seasons = useMemo(() => [...new Set(logs.map((l) => l.season))].sort().reverse(), [logs]);
  const rows = useMemo(() => logs.filter((l) => season === 'all' || l.season === season), [logs, season]);

  const summary = useMemo(() => {
    const fgm = rows.reduce((s, l) => s + l.field_goals_made, 0);
    const fga = rows.reduce((s, l) => s + l.field_goals_attempted, 0);
    const best = rows.reduce<GameLog | null>((top, l) => (!top || l.points > top.points ? l : top), null);
    return { ppg: avg(rows, (l) => l.points), rpg: avg(rows, (l) => l.rebounds), apg: avg(rows, (l) => l.assists), fg: fga ? (fgm / fga) * 100 : 0, best };
  }, [rows]);
  const maxPoints = Math.max(1, ...rows.map((l) => l.points));
  const best = summary.best;
  const timeline = useMemo(() => [...rows].reverse(), [rows]);

  return (
    <section className="panel wide game-logs">
      <div className="panel-header">
        <div><h2>Game logs</h2></div>
        <div className="panel-tools">
          {seasons.length > 1 && <select className="control-input compact-select" value={season} onChange={(e) => { setSeason(e.target.value); setCount(STEP); }} aria-label="Game log season"><option value="all">All seasons</option>{seasons.map((s) => <option key={s} value={s}>{s}</option>)}</select>}
          <span className="count-label">{rows.length} games</span>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="log-summary">
          <div><strong>{summary.ppg.toFixed(1)}</strong><span>PPG</span></div>
          <div><strong>{summary.rpg.toFixed(1)}</strong><span>RPG</span></div>
          <div><strong>{summary.apg.toFixed(1)}</strong><span>APG</span></div>
          <div><strong>{summary.fg.toFixed(1)}%</strong><span>FG</span></div>
          <div className="best"><strong>{summary.best?.points}</strong><span>Best game{best?.opponent ? ` ${best.is_home ? 'vs' : '@'} ${best.opponent}` : ''}</span></div>
        </div>
      )}

      {timeline.length > 1 && (
        <div className="trend" role="img" aria-label="Points per game across the season">
          <span className="trend-avg" style={{ bottom: `${(summary.ppg / maxPoints) * 100}%` }}><b>{summary.ppg.toFixed(1)} avg</b></span>
          {timeline.map((log) => <i key={log.game_id} className={log.points >= summary.ppg ? 'above' : ''} style={{ height: `${Math.max(2, (log.points / maxPoints) * 100)}%` }} title={`${formatDate(log.game_date)}${log.opponent ? ` ${log.is_home ? 'vs' : '@'} ${log.opponent}` : ''}: ${log.points} pts`} />)}
        </div>
      )}

      <div className="detail-records-scroll game-log-scroll">
        <table className="detail-records-table game-log-table">
          <thead><tr><th scope="col">Date</th><th scope="col">Opponent</th><th scope="col">MIN</th><th scope="col" className="pts-col">PTS</th><th scope="col">REB</th><th scope="col">AST</th><th scope="col">STL</th><th scope="col">BLK</th><th scope="col">TOV</th><th scope="col">FG</th><th scope="col">3P</th><th scope="col">FT</th><th scope="col">+/-</th></tr></thead>
          <tbody>
            {rows.slice(0, count).map((log) => {
              const pm = log.plus_minus;
              return (
                <tr key={log.game_id}>
                  <th scope="row">{formatDate(log.game_date)}</th>
                  <td>{log.opponent ? <span className="opp"><em className={log.is_home ? 'home' : 'away'}>{log.is_home ? 'vs' : '@'}</em>{log.opponent}</span> : '–'}</td>
                  <td>{log.minutes}</td>
                  <td className="pts-col"><span className="pts-bar"><i style={{ width: `${(log.points / maxPoints) * 100}%` }} /><b>{log.points}</b></span></td>
                  <td>{log.rebounds}</td><td>{log.assists}</td><td>{log.steals}</td><td>{log.blocks}</td><td>{log.turnovers}</td>
                  <td><Shooting made={log.field_goals_made} att={log.field_goals_attempted} /></td>
                  <td><Shooting made={log.three_pointers_made} att={log.three_pointers_attempted} /></td>
                  <td><Shooting made={log.free_throws_made} att={log.free_throws_attempted} /></td>
                  <td>{pm == null ? '–' : <span className={`pm ${pm > 0 ? 'pos' : pm < 0 ? 'neg' : ''}`}>{pm > 0 ? `+${pm}` : pm}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {count < rows.length && <button type="button" className="ghost-button show-more" onClick={() => setCount((c) => c + STEP)}>Show more games ({rows.length - count} left)</button>}
    </section>
  );
}
