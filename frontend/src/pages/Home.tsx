import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PlayerCell, TeamLogo } from '../components/Common';
import { PlayerPicker } from '../components/PlayerPicker';
import { formatStat, statByKey } from '../stats';
import type { BestGame, View } from '../types';
import { useApi } from '../useApi';
import { teamVars } from '../teamColors';
import { formatDate } from '../utils';

const BOARDS = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'threes'];
const LINKS: [View, string, string][] = [
  ['scout', 'Ask the scout', 'Questions and similar players'],
  ['explorer', 'Stat Explorer', 'Plot any two stats'],
  ['shotlab', 'Shot Lab', 'Best shooters by zone'],
  ['lineup', 'Lineup Builder', 'Test a five-man group'],
];

export function Home() {
  const { players, totals, byId, loading, error, historyIds, open, openGame, go } = useApp();
  const showBoard = (key: string) => { try { sessionStorage.setItem('top-stat', JSON.stringify(key)); } catch { /* storage unavailable */ } go('top'); };
  const best = useApi<BestGame[]>('/players/best-games?limit=6');
  if (error) return <LoadError message={error} />;
  const recent = historyIds.map((id) => byId.get(id)).filter((p) => p != null);
  return (
    <>
      <section className="home-hero">
        <h1>Find your next player</h1>
        <p>{players.length || ''} players from the 2024-25 season, with shots, box scores and defender matchups.</p>
        <PlayerPicker label="Search for a player" placeholder="Search for a player" onPick={open} />
        {recent.length > 0 && <div className="home-recent"><span>Recently viewed</span><div>{recent.slice(0, 6).map((p) => <button type="button" className="recent-card" style={teamVars(p.club_team_id)} key={p.player_id} onClick={() => open(p.player_id)}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="recent-photo" /><b>{p.full_name}</b><small>{p.club}</small></button>)}</div></div>}
      </section>
      <nav className="home-links" aria-label="Tools">
        {LINKS.map(([view, title, text]) => <button key={view} type="button" onClick={() => go(view)}><b>{title}</b><span>{text}</span></button>)}
      </nav>
      <div className="section-head"><h2>League leaders</h2><button type="button" className="link-button" onClick={() => go('top')}>All leaderboards</button></div>
      {loading ? <Loading /> : (
        <div className="leader-grid">
          {BOARDS.map((key) => {
            const stat = statByKey(key);
            const rows = players.filter((p) => (p.games_played ?? 0) >= 40).map((p) => ({ p, v: stat.get(p, totals[p.player_id]) })).filter((r) => r.v != null).sort((a, b) => b.v! - a.v!).slice(0, 5);
            return (
              <section className="panel leader-card" key={key}>
                <h3><button type="button" onClick={() => showBoard(key)}>{stat.label}<span aria-hidden="true">→</span><span className="visually-hidden">, full ranking</span></button></h3>
                <ol>{rows.map(({ p, v }, i) => <li key={p.player_id} className={i < 3 ? `medal place-${i + 1}` : ''} style={teamVars(p.club_team_id)}><span className="medal-no">{i + 1}</span><PlayerCell player={p} note={p.club_full_name ?? ''} />{i === 0 && <span className="medal-logo"><TeamLogo teamId={p.club_team_id} size={120} /></span>}<b>{formatStat(stat, v)}</b></li>)}</ol>
              </section>
            );
          })}
        </div>
      )}
      <div className="section-head"><h2>Best games of the season</h2><span className="count-label">By Game Score</span></div>
      {best.error ? <LoadError message={best.error} /> : !best.data || loading ? <Loading height="12rem" /> : (
        <div className="best-grid">
          {best.data.map((g) => {
            const p = byId.get(g.player_id);
            return p && (
              <button type="button" className="panel best-card team-tint" style={teamVars(g.team_id)} key={`${g.player_id}${g.game_id}`} onClick={() => openGame(g.game_id)}>
                <span className="best-top"><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="recent-photo" /><span><b>{p.full_name}</b><small>{formatDate(g.game_date)}</small></span></span>
                <span className="best-line"><strong>{g.points}<small>pts</small></strong><span><b>{g.rebounds}</b> reb</span><span><b>{g.assists}</b> ast</span><span><b>{g.field_goals_made}/{g.field_goals_attempted}</b> FG</span><span><b>{g.game_score.toFixed(1)}</b> Game Score</span></span>
                <span className="best-foot"><TeamLogo teamId={g.team_id} size={26} /><b>{g.team_points}–{g.opponent_points}</b><TeamLogo teamId={g.opponent_id} size={26} /><small>{g.won ? 'Won' : 'Lost'} {g.is_home ? 'vs' : '@'} {g.opponent}</small><em>Box score →</em></span>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}
