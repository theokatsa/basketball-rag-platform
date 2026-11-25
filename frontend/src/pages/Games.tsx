import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, Segmented, TeamLogo } from '../components/Common';
import { Dropdown, TeamSelect, useTeamList } from '../components/Dropdown';
import { GameCourt } from '../components/GameCourt';
import { BackIcon } from '../components/Icons';
import { Pagination, usePaged } from '../components/Pagination';
import { colorVars, matchColors } from '../teamColors';
import type { TeamColor } from '../teamColors';
import type { BoxLine, GameDetail, GameSummary, PlayerBox, TeamBox } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';
import { formatDate } from '../utils';

const month = (date: string) => date.slice(0, 7);
const monthName = (key: string) => new Date(`${key}-01T00:00:00`).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

export function Games() {
  const { byId, openGame } = useApp();
  const teams = useTeamList();
  const names = useMemo(() => new Map(teams.map((t) => [t.id, t])), [teams]);
  const { data, error } = useApi<GameSummary[]>('/games');
  const [team, setTeam] = usePersisted('games-team', '');
  const [when, setWhen] = usePersisted('games-month', '');
  const [kind, setKind] = usePersisted<'all' | 'close' | 'ot' | 'blowout'>('games-kind', 'all');
  const [order, setOrder] = usePersisted('games-order', 'new');
  const months = useMemo(() => [...new Set((data ?? []).map((g) => month(g.game_date)))], [data]);
  const rows = useMemo(() => {
    const list = (data ?? []).filter((g) => {
      const margin = Math.abs(g.home_points - g.away_points);
      return (!team || [g.home_id, g.away_id].includes(Number(team))) && (!when || month(g.game_date) === when) && (kind === 'all' || (kind === 'close' ? margin <= 5 : kind === 'ot' ? g.overtime : margin >= 20));
    });
    if (order === 'old') return list.reverse();
    if (order === 'points') return list.sort((a, b) => b.home_points + b.away_points - a.home_points - a.away_points);
    if (order === 'best') return list.sort((a, b) => (b.best?.game_score ?? 0) - (a.best?.game_score ?? 0));
    return list;
  }, [data, team, when, kind, order]);
  const paged = usePaged(rows, 24, [team, when, kind, order].join('|'));
  if (error) return <LoadError message={error} />;
  const side = (g: GameSummary, home: boolean) => {
    const id = home ? g.home_id : g.away_id, own = home ? g.home_points : g.away_points, other = home ? g.away_points : g.home_points;
    return <span className={`score-line ${own > other ? 'won' : ''}`}><TeamLogo teamId={id} size={34} /><span>{names.get(id)?.name ?? ''}</span><b>{own}</b></span>;
  };
  const cardStyle = (g: GameSummary) => { const [a, h] = matchColors(g.away_id, g.home_id); return { '--away': a.glow, '--home': h.glow } as CSSProperties; };
  return (
    <>
      <PageHead title="Games" intro="Every game of the 2024-25 regular season, with full box scores." />
      <div className="filter-bar">
        <TeamSelect value={team} onChange={setTeam} by="id" />
        <Dropdown label="Month" value={when} options={[{ value: '', label: 'Whole season' }, ...months.map((m) => ({ value: m, label: monthName(m) }))]} onChange={setWhen} />
        <Segmented label="Kind of game" value={kind} options={[['all', 'All'], ['close', 'Within 5 points'], ['ot', 'Overtime'], ['blowout', '20+ points']]} onChange={setKind} />
        <Dropdown label="Order" value={order} options={[{ value: 'new', label: 'Newest first' }, { value: 'old', label: 'Oldest first' }, { value: 'points', label: 'Most points' }, { value: 'best', label: 'Best performance' }]} onChange={setOrder} />
        {data && <span className="count-label">{rows.length} games</span>}
      </div>
      {!data ? <Loading height="30rem" /> : !rows.length ? <div className="empty-state"><p>No games match.</p></div> : (
        <>
          <div className="game-grid">
            {paged.items.map((g) => {
              const star = g.best && byId.get(g.best.player_id);
              return (
                <button type="button" className="game-card" key={g.game_id} style={cardStyle(g)} onClick={() => openGame(g.game_id)}>
                  <span className="game-date">{formatDate(g.game_date)}{g.overtime && <em>OT</em>}</span>
                  {side(g, false)}{side(g, true)}
                  {g.best && star && <span className="game-star"><Avatar key={star.nba_player_id} name={star.full_name} nbaPlayerId={star.nba_player_id} className="player-thumb" /><span>{star.full_name}</span><small>{g.best.points} pts, {g.best.reb} reb, {g.best.ast} ast</small></span>}
                </button>
              );
            })}
          </div>
          <Pagination page={paged.page} pageCount={paged.pageCount} onPage={(p) => { paged.onPage(p); window.scrollTo({ top: 0 }); }} label="Game pages" />
        </>
      )}
    </>
  );
}

const share = (made: number, att: number) => (att ? (made / att) * 100 : 0);
type Extra = { paint: number };
const COMPARISON: [string, (t: BoxLine, x: Extra) => number, (t: BoxLine, x: Extra) => string, boolean?][] = [
  ['Field goals', (t) => share(t.fgm, t.fga), (t) => `${t.fgm}/${t.fga}, ${share(t.fgm, t.fga).toFixed(1)}%`],
  ['Threes', (t) => share(t.tpm, t.tpa), (t) => `${t.tpm}/${t.tpa}, ${share(t.tpm, t.tpa).toFixed(1)}%`],
  ['Free throws', (t) => share(t.ftm, t.fta), (t) => `${t.ftm}/${t.fta}, ${share(t.ftm, t.fta).toFixed(1)}%`],
  ['Points in the paint', (_, x) => x.paint, (_, x) => String(x.paint)], ['Points from three', (t) => t.tpm * 3, (t) => String(t.tpm * 3)],
  ['Rebounds', (t) => t.reb, (t) => String(t.reb)], ['Offensive rebounds', (t) => t.oreb, (t) => String(t.oreb)], ['Assists', (t) => t.ast, (t) => String(t.ast)],
  ['Steals', (t) => t.stl, (t) => String(t.stl)], ['Blocks', (t) => t.blk, (t) => String(t.blk)], ['Turnovers', (t) => t.tov, (t) => String(t.tov), true], ['Fouls', (t) => t.pf, (t) => String(t.pf), true],
];
const BOX: [string, (p: PlayerBox) => number | string, (p: PlayerBox) => number][] = [
  ['MIN', (p) => p.minutes, (p) => p.minutes], ['PTS', (p) => p.points, (p) => p.points], ['REB', (p) => p.reb, (p) => p.reb], ['AST', (p) => p.ast, (p) => p.ast], ['STL', (p) => p.stl, (p) => p.stl], ['BLK', (p) => p.blk, (p) => p.blk], ['TOV', (p) => p.tov, (p) => p.tov],
  ['FG', (p) => `${p.fgm}/${p.fga}`, (p) => p.fgm], ['3P', (p) => `${p.tpm}/${p.tpa}`, (p) => p.tpm], ['FT', (p) => `${p.ftm}/${p.fta}`, (p) => p.ftm], ['OREB', (p) => p.oreb, (p) => p.oreb], ['DREB', (p) => p.dreb, (p) => p.dreb], ['PF', (p) => p.pf, (p) => p.pf],
  ['+/−', (p) => (p.plus_minus > 0 ? `+${p.plus_minus}` : p.plus_minus), (p) => p.plus_minus], ['GmSc', (p) => p.game_score.toFixed(1), (p) => p.game_score],
];
/** Columns whose best value in the game is marked. */
const LEADERS = ['PTS', 'REB', 'AST', 'STL', 'BLK'];
/** Made, taken, and the rates that count as a good and a bad night. */
const SHOOTING: Record<string, (p: PlayerBox) => [number, number, number, number]> = { FG: (p) => [p.fgm, p.fga, 0.55, 0.35], '3P': (p) => [p.tpm, p.tpa, 0.42, 0.25], FT: (p) => [p.ftm, p.fta, 0.85, 0.6] };

function BoxTable({ team, players, everyone, color }: { team: TeamBox; players: PlayerBox[]; everyone: PlayerBox[]; color: TeamColor }) {
  const { byId, open } = useApp();
  const [sort, setSort] = useState('MIN');
  const value = BOX.find(([label]) => label === sort)![2];
  const rows = [...players].sort((a, b) => value(b) - value(a));
  const margin = team.points - team.opponent_points;
  const best = new Map(LEADERS.map((label) => [label, Math.max(1, ...everyone.map(BOX.find(([l]) => l === label)![2]))]));
  const topScore = Math.max(1, ...everyone.map((p) => p.game_score)), topPoints = best.get('PTS')!;
  const cell = (label: string, p: PlayerBox, text: number | string, v: number) => {
    if (label === 'PTS') return <span className={`box-points ${v === topPoints ? 'top' : ''}`}><i style={{ width: `${(v / topPoints) * 100}%` }} /><b>{text}</b></span>;
    if (label === 'GmSc') return <span className="box-score" style={{ '--share': Math.max(0, v / topScore) } as CSSProperties}>{text}</span>;
    if (label === '+/−') return <span className={`pm ${v > 0 ? 'pos' : v < 0 ? 'neg' : ''}`}>{text}</span>;
    if (SHOOTING[label]) {
      const [made, att, high, low] = SHOOTING[label](p), rate = att ? made / att : 0;
      return <span className={att < 3 ? '' : rate >= high ? 'shot-hot' : rate <= low ? 'shot-cold' : ''}>{text}{att > 0 && <small>{(rate * 100).toFixed(0)}%</small>}</span>;
    }
    if (label === 'TOV' && v >= 4) return <span className="shot-cold">{text}</span>;
    if (LEADERS.includes(label) && v > 0 && v === best.get(label)) return <span className="box-best" title="Most in the game">{text}</span>;
    return v === 0 && typeof text === 'number' ? <span className="nil">0</span> : text;
  };
  return (
    <section className="panel box-panel" style={colorVars(color)}>
      <div className="panel-header"><h2 className="side-title"><TeamLogo teamId={team.nba_team_id} size={44} />{team.full_name}<b className="side-points">{team.points}</b></h2><span className="count-label">Click a heading to sort. Gold marks the most in the game.</span></div>
      <div className="detail-records-scroll open">
        <table className="detail-records-table roster-table box-table">
          <thead><tr><th scope="col">Player</th>{BOX.map(([label]) => <th scope="col" key={label} aria-sort={sort === label ? 'descending' : 'none'} className={sort === label ? 'sorted' : ''}><button type="button" className="sort-heading" onClick={() => setSort(label)}>{label}</button></th>)}</tr></thead>
          <tbody>
            {rows.map((p) => <tr key={p.player_id}><th scope="row"><button type="button" className="player-link" onClick={() => open(p.player_id)} disabled={!byId.has(p.player_id)}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" /><span className="player-name">{p.full_name}</span></button></th>{BOX.map(([label, text, number]) => <td key={label} className={sort === label ? 'sorted-cell' : ''}>{cell(label, p, text(p), number(p))}</td>)}</tr>)}
            <tr className="total-row"><th scope="row">Team</th>{[team.minutes, team.points, team.reb, team.ast, team.stl, team.blk, team.tov, `${team.fgm}/${team.fga}`, `${team.tpm}/${team.tpa}`, `${team.ftm}/${team.fta}`, team.oreb, team.dreb, team.pf, `${margin > 0 ? '+' : ''}${margin}`, ''].map((v, i) => <td key={i}>{v}</td>)}</tr>
          </tbody>
        </table>
      </div>
    </section>
  );
}

const periodName = (p: number) => (p > 4 ? (p === 5 ? 'OT' : `OT${p - 4}`) : `Q${p}`);

/** Points per period, away above the line and home below it, like a live score app. */
function Periods({ game, away, home, colors }: { game: GameDetail; away: TeamBox; home: TeamBox; colors: [TeamColor, TeamColor] }) {
  const numbers = [...new Set(game.periods.map((p) => p.period))].sort((a, b) => a - b);
  if (!numbers.length) return null;
  const points = (team: TeamBox, period: number) => game.periods.find((p) => p.nba_team_id === team.nba_team_id && p.period === period)?.points ?? 0;
  const peak = Math.max(1, ...game.periods.map((p) => p.points));
  let lead = 0;
  const columns = numbers.map((p) => { const a = points(away, p), h = points(home, p); lead += a - h; return { p, a, h, after: lead }; });
  const label = (t: TeamBox, i: number) => <span className="period-team" style={colorVars(colors[i])}><i />{t.abbreviation}</span>;
  return (
    <section className="periods" aria-label="Points per period" style={{ gridTemplateColumns: `minmax(44px, .55fr) repeat(${numbers.length}, minmax(0, 1fr)) minmax(44px, .55fr)` }}>
      <div className="period-names">{label(away, 0)}<small>Lead</small>{label(home, 1)}</div>
      {columns.map(({ p, a, h, after }) => (
        <div key={p} className="period-col">
          <small>{periodName(p)}</small>
          <div className="period-half up" style={colorVars(colors[0])}><b className={a > h ? 'won' : ''}>{a}</b><i style={{ height: `${(a / peak) * 58}px` }} /></div>
          <em className="period-lead">{after === 0 ? 'Tied' : `${after > 0 ? away.abbreviation : home.abbreviation} +${Math.abs(after)}`}</em>
          <div className="period-half" style={colorVars(colors[1])}><i style={{ height: `${(h / peak) * 58}px` }} /><b className={h > a ? 'won' : ''}>{h}</b></div>
        </div>
      ))}
      <div className="period-col total"><small>Total</small><div className="period-half up"><b className={away.won ? 'won' : ''}>{away.points}</b></div><em className="period-lead" /><div className="period-half"><b className={home.won ? 'won' : ''}>{home.points}</b></div></div>
    </section>
  );
}

export function Game({ id }: { id: string }) {
  const { open, go } = useApp();
  const { data, error } = useApi<GameDetail>(`/games/${id}`);
  if (error) return <LoadError message={error} />;
  if (!data) return <Loading height="40rem" />;
  const [away, home] = data.teams;
  const colors = matchColors(away.nba_team_id, home.nba_team_id);
  const sideOf = (teamId: number) => (teamId === home.nba_team_id ? 1 : 0);
  const stars = [...data.players].sort((a, b) => b.game_score - a.game_score).slice(0, 3);
  const extra = [away, home].map((t) => ({ paint: 2 * data.shots.filter((s) => s.nba_team_id === t.nba_team_id && s.shot_made && s.shot_type.startsWith('2') && Math.abs(s.loc_x) <= 80 && s.loc_y <= 138).length }));
  const teamHead = (t: TeamBox) => <button type="button" className={`game-side ${t.won ? 'won' : ''}`} onClick={() => go('team', t.nba_team_id)}><TeamLogo teamId={t.nba_team_id} size={110} /><span><b>{t.full_name}</b><small>{t.is_home ? 'Home' : 'Away'}{t.won ? ', winner' : ''}</small></span></button>;
  return (
    <div className="game-page" style={{ '--away': colors[0].glow, '--home': colors[1].glow } as CSSProperties}>
      <div className="detail-topbar team-back"><button type="button" className="back-button" onClick={() => (window.history.state ? window.history.back() : go('games'))}><BackIcon />Back</button></div>
      <header className="game-hero">
        {teamHead(away)}
        <div className="game-score"><p><strong className={away.won ? 'won' : ''}>{away.points}</strong><span>–</span><strong className={home.won ? 'won' : ''}>{home.points}</strong></p><small>{formatDate(home.game_date)}{home.minutes > 245 ? ', overtime' : ''}</small></div>
        {teamHead(home)}
        <Periods game={data} away={away} home={home} colors={colors} />
      </header>

      <section className="match-podium" aria-label="Best players of the game">
        <h2>Best players of the game</h2>
        <div className="podium-steps">
          {stars.map((p, i) => (
            <button type="button" key={p.player_id} className={`step place-${i + 1}`} style={colorVars(colors[sideOf(p.nba_team_id)])} onClick={() => open(p.player_id)}>
              <span className="step-photo"><TeamLogo teamId={p.nba_team_id} size={150} /><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="podium-photo" /></span>
              <span className="step-block"><em>{i + 1}</em><b>{p.full_name}</b><span className="step-line"><span><strong>{p.points}</strong>pts</span><span><strong>{p.reb}</strong>reb</span><span><strong>{p.ast}</strong>ast</span></span><small>{p.fgm}/{p.fga} FG, {p.stl} stl, {p.blk} blk</small><small>Game Score {p.game_score.toFixed(1)}</small></span>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-header"><div><h2>Team comparison</h2><p>The better side of each line is bold</p></div></div>
        <div className="versus-bars">
          <div className="versus-head"><span className="period-team" style={colorVars(colors[0])}><i />{away.full_name}</span><span /><span className="period-team" style={colorVars(colors[1])}>{home.full_name}<i /></span></div>
          {COMPARISON.map(([label, value, text, lower]) => {
            const a = value(away, extra[0]), h = value(home, extra[1]), total = a + h || 1;
            const better = a === h ? -1 : (a > h) !== Boolean(lower) ? 0 : 1;
            return <div key={label}><span className={better === 0 ? 'better' : ''}>{text(away, extra[0])}</span><small>{label}</small><span className={better === 1 ? 'better' : ''}>{text(home, extra[1])}</span><i><em className="fill" style={{ ...colorVars(colors[0]), width: `${(a / total) * 100}%` }} /><em className="fill" style={{ ...colorVars(colors[1]), width: `${(h / total) * 100}%` }} /></i></div>;
          })}
        </div>
      </section>

      <GameCourt game={data} away={away} home={home} colors={colors} />

      {[away, home].map((t, i) => <BoxTable key={t.nba_team_id} team={t} players={data.players.filter((p) => p.nba_team_id === t.nba_team_id)} everyone={data.players} color={colors[i]} />)}
    </div>
  );
}
