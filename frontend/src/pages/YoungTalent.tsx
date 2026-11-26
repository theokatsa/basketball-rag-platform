import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, PlayerCell, RowActions, Segmented, TeamLogo } from '../components/Common';
import { TeamSelect } from '../components/Dropdown';
import { Pagination, usePaged } from '../components/Pagination';
import { formatStat, playsPosition, POSITIONS, qualifies, statByKey } from '../stats';
import { teamVars } from '../teamColors';
import type { PlayerDirectoryRow } from '../types';
import { usePersisted } from '../usePersisted';

const COLS = ['minutes', 'points', 'rebounds', 'assists', 'ts', 'usage', 'net_rating'];
const RANK_BY: [string, string][] = [['production', 'Game Score'], ['points', 'Points'], ['rebounds', 'Rebounds'], ['assists', 'Assists'], ['ts', 'TS%'], ['net_rating', 'Net rating']];
const AGES = [19, 20, 21, 22, 23, 24];

type Row = { p: PlayerDirectoryRow; age: number; v: number };

export function YoungTalent() {
  const { players, totals, loading, error, open } = useApp();
  const [maxAge, setMaxAge] = usePersisted('young-age', '22');
  const [position, setPosition] = usePersisted('young-pos', '');
  const [club, setClub] = usePersisted('young-club', '');
  const [rankKey, setRankKey] = usePersisted('young-rank', 'production');
  const stat = statByKey(rankKey);
  /** Everyone 24 or younger who passes the filters, best first by the chosen statistic. */
  const pool = useMemo(() => players.flatMap((p): Row[] => {
    const t = totals[p.player_id];
    const age = statByKey('age').get(p, t), v = stat.get(p, t);
    if (age == null || v == null || age > 24 || (p.games_played ?? 0) < 20 || !qualifies(stat, t) || !playsPosition(p, position) || (club && p.club_full_name !== club)) return [];
    return [{ p, age, v }];
  }).sort((a, b) => (stat.lowerIsBetter ? a.v - b.v : b.v - a.v)), [players, totals, stat, position, club]);
  const rows = useMemo(() => pool.filter((r) => r.age <= Number(maxAge)), [pool, maxAge]);
  const bestByAge = useMemo(() => AGES.map((age) => ({ age, best: pool.find((r) => (age === 19 ? r.age <= 19 : r.age === age)) })), [pool]);
  const paged = usePaged(rows, 20, [maxAge, position, club, rankKey].join('|'));
  if (error) return <LoadError message={error} />;
  const values = rows.map((r) => r.v);
  const lo = Math.min(0, ...values), hi = Math.max(...values, 1e-9);
  const width = (v: number) => Math.max(2, ((v - lo) / (hi - lo || 1)) * 100);
  return (
    <>
      <PageHead title="Young talent" intro={`The best players by age in 2024-25, ranked by ${stat.label.toLowerCase()}. At least 20 games played.`} />
      {!loading && (
        <section className="age-strip" aria-label="Best player at each age">
          {bestByAge.map(({ age, best }) => (
            <button type="button" key={age} className={`age-card ${Number(maxAge) >= age ? 'in' : ''}`} style={best ? teamVars(best.p.club_team_id) : undefined} disabled={!best} onClick={() => best && open(best.p.player_id)}>
              <span className="age-num">{age === 19 ? '≤19' : age}</span>
              {best ? <>
                <Avatar key={best.p.nba_player_id} name={best.p.full_name} nbaPlayerId={best.p.nba_player_id} className="age-photo" />
                <span className="age-name"><b>{best.p.full_name}</b><small><TeamLogo teamId={best.p.club_team_id} size={14} />{best.p.club}, {best.p.position}</small></span>
                <span className="age-value"><strong>{formatStat(stat, best.v)}</strong><small>{stat.short}</small></span>
              </> : <span className="age-name"><small>Nobody matches</small></span>}
            </button>
          ))}
        </section>
      )}
      <div className="filter-bar">
        <Segmented label="Maximum age" value={maxAge} options={[['20', '20 and under'], ['21', '21'], ['22', '22'], ['23', '23'], ['24', '24']]} onChange={setMaxAge} />
        <Segmented label="Rank by" value={rankKey} options={RANK_BY} onChange={setRankKey} />
        <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        <TeamSelect value={club} onChange={setClub} />
        <span className="count-label">{rows.length} players</span>
      </div>
      {loading ? <Loading /> : (
        <section className="panel">
          <div className="detail-records-scroll open">
            <table className="detail-records-table roster-table young-table">
              <thead><tr>{['Player', 'Age', ...COLS.filter((c) => c !== rankKey).map((c) => statByKey(c).short), stat.label, ''].map((h, i) => <th scope="col" key={i}>{h}</th>)}</tr></thead>
              <tbody>{paged.items.map(({ p, age, v }, i) => (
                <tr key={p.player_id}>
                  <th scope="row"><div className="ranked-cell"><span className="rank-no">{paged.offset + i + 1}</span><PlayerCell player={p} /></div></th>
                  <td><span className="age-pill">{age}</span></td>
                  {COLS.filter((c) => c !== rankKey).map((k) => <td key={k}>{formatStat(statByKey(k), statByKey(k).get(p, totals[p.player_id]))}</td>)}
                  <td><div className="score-cell"><b>{formatStat(stat, v)}</b><i className="rank-bar"><em style={{ width: `${width(v)}%` }} /></i></div></td>
                  <td><RowActions player={p} /></td>
                </tr>
              ))}</tbody>
            </table>
            {!rows.length && <p className="status">Nobody matches these filters.</p>}
          </div>
          <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Young talent pages" />
        </section>
      )}
      {/* TODO(projections): needs several seasons in player_box_scores and player_advanced_stats; only 2024-25 is loaded. */}
      <p className="radar-note">Planned: projections of how each player could develop. That needs earlier seasons in the database; only 2024-25 is loaded.</p>
    </>
  );
}
