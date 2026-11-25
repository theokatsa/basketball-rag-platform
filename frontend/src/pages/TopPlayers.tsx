import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, RowActions, Segmented, TeamLogo } from '../components/Common';
import { TeamSelect } from '../components/Dropdown';
import { Pagination, usePaged } from '../components/Pagination';
import { formatStat, playsPosition, POSITIONS, qualifies, STAT_GROUPS, statByKey, STATS } from '../stats';
import type { StatDef } from '../stats';
import { teamVars } from '../teamColors';
import type { PlayerDirectoryRow } from '../types';
import { usePersisted } from '../usePersisted';

const SIZE = 25;
/** What to read next to a statistic: volume beside efficiency, risk beside reward. */
const BESIDE: Record<string, string[]> = {
  Scoring: ['ts', 'usage', 'assists'], Shooting: ['points', 'three', 'ft', 'usage'], Playmaking: ['ast_to', 'turnovers', 'usage', 'points'],
  Rebounding: ['oreb', 'dreb', 'dreb_pct', 'blocks'], Defense: ['steals', 'blocks', 'dfg_diff', 'def_rating'], Impact: ['points', 'ts', 'net_rating', 'plus_minus'], Other: ['points', 'rebounds', 'assists'],
};
const mainPosition = (p: PlayerDirectoryRow) => (p.position ?? '').split('-')[0];
const mean = (values: number[]) => (values.length ? values.reduce((s, v) => s + v, 0) / values.length : null);

export function TopPlayers() {
  const { players, totals, loading, error, open } = useApp();
  const [key, setKey] = usePersisted('top-stat', 'points');
  const [position, setPosition] = usePersisted('top-position', '');
  const [club, setClub] = usePersisted('top-club', '');
  const [minGames, setMinGames] = usePersisted('top-games', 40);
  const stat = statByKey(key);
  /** Everyone who qualifies, before the team and position filters: the yardstick for the comparison. */
  const pool = useMemo(() => players
    .filter((p) => (p.games_played ?? 0) >= minGames && qualifies(stat, totals[p.player_id]))
    .map((p) => ({ p, v: stat.get(p, totals[p.player_id]) }))
    .filter((r): r is { p: typeof r.p; v: number } => r.v != null), [players, totals, stat, minGames]);
  const ranked = useMemo(() => pool.filter(({ p }) => playsPosition(p, position) && (!club || p.club_full_name === club)).sort((a, b) => (stat.lowerIsBetter ? a.v - b.v : b.v - a.v)), [pool, stat, position, club]);
  const base = useMemo(() => {
    const values = pool.map((r) => r.v), average = mean(values);
    const spread = average == null ? 0 : Math.sqrt(mean(values.map((v) => (v - average) ** 2)) ?? 0);
    const byPosition = Object.fromEntries(POSITIONS.map((name) => [name, mean(pool.filter((r) => mainPosition(r.p) === name).map((r) => r.v))]));
    return { average, spread, byPosition: byPosition as Record<string, number | null> };
  }, [pool]);
  const paged = usePaged(ranked, SIZE, [key, position, club, minGames].join('|'));
  if (error) return <LoadError message={error} />;
  const rows = paged.items.filter((_, i) => paged.offset + i >= 3);
  const beside = (BESIDE[stat.group] ?? []).filter((k) => k !== key).map(statByKey).filter((s, i, all) => s.key !== key && all.findIndex((x) => x.key === s.key) === i).slice(0, 3);
  const better = (gap: number) => (stat.lowerIsBetter ? gap < 0 : gap > 0);
  const gapText = (v: number, from: number | null) => { if (from == null) return null; const gap = v - from; return { gap, text: `${gap > 0 ? '+' : ''}${gap.toFixed(stat.digits || 1)}` }; };
  const standing = (v: number) => { const beaten = pool.filter((r) => (stat.lowerIsBetter ? r.v > v : r.v < v)).length; return Math.max(1, Math.round((1 - beaten / Math.max(1, pool.length)) * 100)); };
  const shown = (s: StatDef, p: PlayerDirectoryRow) => formatStat(s, s.get(p, totals[p.player_id]));
  const gapCell = (v: number, from: number | null) => { const g = gapText(v, from); return g ? <span className={`gap ${Math.abs(g.gap) < 0.05 ? '' : better(g.gap) ? 'good' : 'bad'}`}>{g.text}</span> : <span className="gap">–</span>; };
  return (
    <>
      <PageHead title={`Top players: ${stat.label}`} intro={stat.lowerIsBetter ? 'Lower is better for this statistic.' : 'The league’s best in every category.'} />
      <div className="stat-board">
        <Segmented label="Category" value={stat.group} options={STAT_GROUPS.map((g) => [g, g])} onChange={(g) => setKey(STATS.find((s) => s.group === g)!.key)} />
        <div className="stat-tabs" role="group" aria-label="Statistic">{STATS.filter((s) => s.group === stat.group).map((s) => <button key={s.key} type="button" aria-pressed={s.key === key} onClick={() => setKey(s.key)}>{s.label}</button>)}</div>
      </div>
      <div className="filter-bar">
        <TeamSelect value={club} onChange={setClub} />
        <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        <label className="inline-range">At least {minGames} games<input type="range" min={1} max={82} value={minGames} onChange={(e) => setMinGames(Number(e.target.value))} /></label>
        <span className="count-label">{ranked.length} qualified{stat.attempts ? `, minimum ${stat.attempts[1]} ${stat.unit ?? 'attempts'}` : ''}</span>
      </div>
      {loading ? <Loading /> : !ranked.length ? <div className="empty-state"><p>Nobody qualifies.</p><small>Lower the minimum games or widen the filters.</small></div> : (
        <>
          {paged.page === 1 && (
            <div className="podium">
              {ranked.slice(0, 3).map(({ p, v }, i) => {
                const g = gapText(v, base.average);
                return (
                  <button type="button" key={p.player_id} className={`podium-card team-tint place-${i + 1}`} style={teamVars(p.club_team_id)} onClick={() => open(p.player_id)}>
                    <span className="podium-rank">{i + 1}</span>
                    <span className="podium-team"><TeamLogo teamId={p.club_team_id} size={44} /></span>
                    <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="podium-photo" />
                    <span className="podium-info"><b>{p.full_name}</b><small>{p.club_full_name}</small><strong>{formatStat(stat, v)}</strong>{g && <small className="podium-gap">{g.text} against the league average</small>}</span>
                  </button>
                );
              })}
            </div>
          )}
          {base.average != null && (
            <p className="league-line"><span>League average <b>{formatStat(stat, base.average)}</b></span>{POSITIONS.map((name) => base.byPosition[name] != null && <span key={name}>{name}s <b>{formatStat(stat, base.byPosition[name])}</b></span>)}<span>{pool.length} players with at least {minGames} games</span></p>
          )}
          {rows.length > 0 && (
            <section className="panel">
              <div className="detail-records-scroll open">
                <table className="detail-records-table top-table">
                  <thead><tr><th scope="col">Player</th><th scope="col" className="main">{stat.short}</th><th scope="col">vs league</th><th scope="col">vs position</th><th scope="col">Standing</th>{beside.map((s) => <th scope="col" key={s.key} title={s.label}>{s.short}</th>)}<th scope="col" title="Games played">GP</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
                  <tbody>
                    {rows.map(({ p, v }, i) => {
                      const top = standing(v);
                      return (
                        <tr key={p.player_id} style={teamVars(p.club_team_id)} className="team-row">
                          <th scope="row"><div className="ranked-cell"><span className="rank-no">{paged.offset + i + (paged.page === 1 ? 4 : 1)}</span><TeamLogo teamId={p.club_team_id} size={30} /><PlayerCell player={p} /></div></th>
                          <td className="main">{formatStat(stat, v)}</td>
                          <td>{gapCell(v, base.average)}</td><td>{gapCell(v, base.byPosition[mainPosition(p)] ?? null)}</td>
                          <td><span className={`standing ${top <= 10 ? 'elite' : top <= 33 ? 'good' : ''}`}>{top <= 50 ? `Top ${top}%` : `Bottom ${Math.max(1, 101 - top)}%`}</span></td>
                          {beside.map((s) => <td key={s.key}>{shown(s, p)}</td>)}
                          <td>{p.games_played}</td>
                          <td><RowActions player={p} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="radar-note">Averages count every qualified player once. {base.spread > 0 && `About two thirds of them are within ${base.spread.toFixed(stat.digits || 1)}${stat.suffix ?? ''} of the league average.`}{stat.key === 'production' && ' Game Score sums scoring, rebounds, assists and defense, minus misses, turnovers and fouls.'}{stat.key === 'dfg_diff' && ' This is how much worse (minus) or better (plus) opponents shoot than usual when this player guards them.'}</p>
            </section>
          )}
          <Pagination page={paged.page} pageCount={paged.pageCount} onPage={(p) => { paged.onPage(p); window.scrollTo({ top: 0 }); }} label="Ranking pages" />
        </>
      )}
    </>
  );
}
