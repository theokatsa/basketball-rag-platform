import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, RowActions } from '../components/Common';
import { formatStat, playsPosition, POSITIONS, statByKey, STATS } from '../stats';
import { usePersisted } from '../usePersisted';

const CHOICES = STATS.filter((s) => s.key !== 'age' && s.key !== 'turnovers');
const SHOWN = 50;

export function TopPlayers() {
  const { players, totals, loading, error, open } = useApp();
  const [key, setKey] = usePersisted('top-stat', 'points');
  const [position, setPosition] = usePersisted('top-position', '');
  const [club, setClub] = usePersisted('top-club', '');
  const [minGames, setMinGames] = usePersisted('top-games', 40);
  const stat = statByKey(key);
  const clubs = useMemo(() => [...new Set(players.map((p) => p.club_full_name).filter((c) => c != null))].sort(), [players]);
  const ranked = useMemo(() => players
    .filter((p) => (p.games_played ?? 0) >= minGames && playsPosition(p, position) && (!club || p.club_full_name === club))
    .filter((p) => { const t = totals[p.player_id]; return !stat.attempts || (t != null && stat.attempts[0](t) >= stat.attempts[1]); })
    .map((p) => ({ p, v: stat.get(p, totals[p.player_id]) }))
    .filter((r): r is { p: typeof r.p; v: number } => r.v != null)
    .sort((a, b) => b.v - a.v), [players, totals, stat, position, club, minGames]);
  if (error) return <LoadError message={error} />;
  const top = ranked[0]?.v ?? 0;
  const floor = Math.min(0, ranked[Math.min(SHOWN, ranked.length) - 1]?.v ?? 0);
  return (
    <>
      <PageHead title="Top players" intro="The league's best in every category." />
      <div className="stat-tabs" role="group" aria-label="Statistic">{CHOICES.map((s) => <button key={s.key} type="button" aria-pressed={s.key === key} onClick={() => setKey(s.key)}>{s.label}</button>)}</div>
      <div className="filter-bar">
        <select className="control-input" aria-label="Position" value={position} onChange={(e) => setPosition(e.target.value)}><option value="">All positions</option>{POSITIONS.map((p) => <option key={p} value={p}>{p}s</option>)}</select>
        <select className="control-input" aria-label="Team" value={club} onChange={(e) => setClub(e.target.value)}><option value="">All teams</option>{clubs.map((c) => <option key={c} value={c}>{c}</option>)}</select>
        <label className="inline-range">At least {minGames} games<input type="range" min={1} max={82} value={minGames} onChange={(e) => setMinGames(Number(e.target.value))} /></label>
        {stat.attempts && <span className="count-label">Minimum {stat.attempts[1]} attempts</span>}
      </div>
      {loading ? <Loading /> : !ranked.length ? <div className="empty-state"><p>Nobody qualifies.</p><small>Lower the minimum games or widen the filters.</small></div> : (
        <>
          <div className="podium">
            {ranked.slice(0, 3).map(({ p, v }, i) => (
              <button type="button" key={p.player_id} className={`podium-card place-${i + 1}`} onClick={() => open(p.player_id)}>
                <span className="podium-rank">{i + 1}</span>
                <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="podium-photo" />
                <span className="podium-info"><b>{p.full_name}</b><small>{p.club_full_name}</small><strong>{formatStat(stat, v)}</strong></span>
              </button>
            ))}
          </div>
          <section className="panel">
            <ol className="rank-list" start={4}>
              {ranked.slice(3, SHOWN).map(({ p, v }, i) => (
                <li key={p.player_id}><span className="rank-no">{i + 4}</span><PlayerCell player={p} /><i className="rank-bar"><em style={{ width: `${top > floor ? Math.max(0, ((v - floor) / (top - floor)) * 100) : 0}%` }} /></i><b>{formatStat(stat, v)}</b><RowActions player={p} /></li>
              ))}
            </ol>
            <p className="radar-note">Showing {Math.min(SHOWN, ranked.length)} of {ranked.length} qualified players.{stat.key === 'production' && ' Game Score sums scoring, rebounds, assists and defence, minus misses and turnovers.'}</p>
          </section>
        </>
      )}
    </>
  );
}
