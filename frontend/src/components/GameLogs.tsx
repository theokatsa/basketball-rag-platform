import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import type { GameLog } from '../types';
import { usePersisted } from '../usePersisted';
import { formatDate } from '../utils';
import { BarTrend } from './BarTrend';
import { Segmented, TeamLogo } from './Common';
import { TeamSelect } from './Dropdown';
import { LOG_STATS, logStat } from './logStats';
import { Pagination, usePaged } from './Pagination';

const pct = (made: number, att: number) => (att ? `${Math.round((made / att) * 100)}%` : '–');

function Shooting({ made, att }: { made: number; att: number }) {
  return <span className="shooting"><b>{made}/{att}</b><small>{pct(made, att)}</small></span>;
}

export function GameLogs({ logs }: { logs: GameLog[] }) {
  const { openGame } = useApp();
  const [key, setKey] = usePersisted('log-stat', 'points');
  const [place, setPlace] = useState<'all' | 'home' | 'away'>('all');
  const [result, setResult] = useState<'all' | 'won' | 'lost'>('all');
  const [span, setSpan] = useState<'all' | '20' | '10'>('all');
  const [opponent, setOpponent] = useState('');
  const [rolling, setRolling] = usePersisted<'5' | '10' | '0'>('log-rolling', '5');
  const stat = logStat(key);
  const rows = useMemo(() => {
    const list = logs.filter((l) => (place === 'all' || l.is_home === (place === 'home')) && (result === 'all' || l.won === (result === 'won')) && (!opponent || l.opponent === opponent));
    return span === 'all' ? list : list.slice(0, Number(span));
  }, [logs, place, result, span, opponent]);
  const paged = usePaged(rows, 15, [place, result, span, opponent].join('|'));
  const chron = useMemo(() => [...rows].reverse(), [rows]);
  const timeline = useMemo(() => chron.map((l) => ({ key: l.nba_game_id ?? '', value: stat.value(l), won: l.won, title: `${l.is_home ? 'vs' : '@'} ${l.opponent}, ${formatDate(l.game_date)}`, note: `${l.won ? 'Won' : 'Lost'} ${l.team_points}–${l.opponent_points}` })), [chron, stat]);
  const lower = stat.key === 'turnovers' || stat.key === 'pf';
  // Percentages from a handful of attempts are not a season high.
  const ranked = useMemo(() => {
    const enough = (l: GameLog) => stat.suffix !== '%' || (stat.key === 'three' ? l.three_pointers_attempted >= 4 : stat.key === 'ft' ? l.free_throws_attempted >= 4 : l.field_goals_attempted >= 8);
    return rows.flatMap((l) => { const v = stat.value(l); return v == null || !enough(l) ? [] : [{ l, v }]; }).sort((p, q) => q.v - p.v || (q.l.game_date ?? '').localeCompare(p.l.game_date ?? ''));
  }, [rows, stat]);
  const season = stat.average(logs), now = stat.average(rows);
  const filtered = rows.length !== logs.length;
  const gap = now != null && season != null ? now - season : 0;
  const better = lower ? gap < 0 : gap > 0;
  const parts = [span !== 'all' && `last ${span}`, place !== 'all' && (place === 'home' ? 'at home' : 'away'), result !== 'all' && (result === 'won' ? 'in wins' : 'in losses'), opponent && `against ${opponent}`].filter(Boolean).join(', ');
  const cell = (v: number) => (stat.suffix ? `${v.toFixed(0)}%` : v.toFixed(stat.digits));
  const maxPoints = Math.max(1, ...rows.map((l) => l.points));
  if (!logs.length) return <section className="panel wide"><p className="status">No games recorded.</p></section>;

  return (
    <section className="panel wide game-logs">
      <div className="panel-header">
        <div><h2>Game log</h2><p>Click a bar or a row for the full box score</p></div>
        <span className="count-label">{rows.length} games</span>
      </div>
      <div className="stat-tabs wrap" role="group" aria-label="Statistic shown">{LOG_STATS.map((s) => <button type="button" key={s.key} aria-pressed={s.key === key} onClick={() => setKey(s.key)}>{s.label}</button>)}</div>
      <div className="filter-bar">
        <Segmented label="Place" value={place} options={[['all', 'All'], ['home', 'Home'], ['away', 'Away']]} onChange={setPlace} />
        <Segmented label="Result" value={result} options={[['all', 'All'], ['won', 'Won'], ['lost', 'Lost']]} onChange={setResult} />
        <Segmented label="Games" value={span} options={[['all', 'Season'], ['20', 'Last 20'], ['10', 'Last 10']]} onChange={setSpan} />
        <TeamSelect value={opponent} onChange={setOpponent} by="abbr" all="Any opponent" label="Opponent" />
      </div>
      <div className="log-head">
        <div className="log-now"><strong>{now == null ? '–' : stat.text(now)}</strong><span>{stat.label} per game{stat.suffix ? ', by attempts' : ''}<small>{parts ? `${parts[0].toUpperCase()}${parts.slice(1)}` : 'Whole season'}, {rows.length} games</small></span></div>
        {filtered && now != null && season != null && <p className="log-vs"><b className={Math.abs(gap) < 0.05 ? '' : better ? 'up' : 'down'}>{stat.signed || gap >= 0 ? `${gap >= 0 ? '+' : ''}${gap.toFixed(1)}` : gap.toFixed(1)}</b>against the season’s {stat.text(season)}</p>}
        {ranked.length > 1 && <p className="log-vs"><b>{cell(ranked[0].v)}</b>highest<b>{cell(ranked[ranked.length - 1].v)}</b>lowest</p>}
        <div className="log-line-pick"><span>Average line</span><Segmented label="Average line" value={rolling} options={[['5', 'Last 5'], ['10', 'Last 10'], ['0', 'Season so far']]} onChange={setRolling} /></div>
      </div>
      <BarTrend label={stat.label} points={timeline} digits={stat.digits} suffix={stat.suffix} signed={stat.signed} rolling={Number(rolling)} averageOf={(from, to) => stat.average(chron.slice(from, to + 1))} onPick={openGame} />
      {ranked.length > 0 && (
        <div className="top-games"><h3>{lower ? 'Most' : 'Best games:'} {stat.label.toLowerCase()}</h3>
          <ol>{ranked.slice(0, 5).map(({ l, v }, i) => <li key={l.nba_game_id}><button type="button" className={i === 0 ? 'first' : ''} onClick={() => l.nba_game_id && openGame(l.nba_game_id)}><strong>{cell(v)}</strong><span><TeamLogo teamId={l.opponent_id} size={22} />{l.is_home ? 'vs' : '@'} {l.opponent}<small>{formatDate(l.game_date)}, {l.won ? 'won' : 'lost'} {l.team_points}–{l.opponent_points}</small></span></button></li>)}</ol>
        </div>
      )}

      <div className="detail-records-scroll open">
        <table className="detail-records-table game-log-table">
          <thead><tr><th scope="col">Date</th><th scope="col">Opponent</th><th scope="col">Result</th><th scope="col">MIN</th><th scope="col" className="pts-col">PTS</th><th scope="col">REB</th><th scope="col">AST</th><th scope="col">STL</th><th scope="col">BLK</th><th scope="col">TOV</th><th scope="col">FG</th><th scope="col">3P</th><th scope="col">FT</th><th scope="col">PF</th><th scope="col">+/−</th></tr></thead>
          <tbody>
            {paged.items.map((log) => {
              const pm = log.plus_minus;
              return (
                <tr key={log.nba_game_id} className="click-row" onClick={() => log.nba_game_id && openGame(log.nba_game_id)}>
                  <th scope="row"><button type="button" className="player-link">{formatDate(log.game_date)}</button></th>
                  <td><span className="opp"><em className={log.is_home ? 'home' : 'away'}>{log.is_home ? 'vs' : '@'}</em><TeamLogo teamId={log.opponent_id} size={24} />{log.opponent}</span></td>
                  <td><span className={`result-mark ${log.won ? 'w' : 'l'}`}>{log.won ? 'W' : 'L'}</span> {log.team_points}–{log.opponent_points}</td>
                  <td>{log.minutes}</td>
                  <td className="pts-col"><span className="pts-bar"><i style={{ width: `${(log.points / maxPoints) * 100}%` }} /><b>{log.points}</b></span></td>
                  <td title={`${log.oreb} offensive, ${log.dreb} defensive`}>{log.rebounds}</td><td>{log.assists}</td><td>{log.steals}</td><td>{log.blocks}</td><td>{log.turnovers}</td>
                  <td><Shooting made={log.field_goals_made} att={log.field_goals_attempted} /></td>
                  <td><Shooting made={log.three_pointers_made} att={log.three_pointers_attempted} /></td>
                  <td><Shooting made={log.free_throws_made} att={log.free_throws_attempted} /></td>
                  <td>{log.pf}</td>
                  <td>{pm == null ? '–' : <span className={`pm ${pm > 0 ? 'pos' : pm < 0 ? 'neg' : ''}`}>{pm > 0 ? `+${pm}` : pm}</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Game log pages" />
    </section>
  );
}
