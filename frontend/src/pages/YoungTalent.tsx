import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { LoadError, Loading, PageHead, PlayerCell, RowActions, Segmented } from '../components/Common';
import { TeamSelect } from '../components/Dropdown';
import { Pagination, usePaged } from '../components/Pagination';
import { formatStat, playsPosition, POSITIONS, production, statByKey } from '../stats';
import { usePersisted } from '../usePersisted';

const COLS = ['minutes', 'points', 'rebounds', 'assists', 'ts', 'usage', 'net_rating'];

export function YoungTalent() {
  const { players, totals, loading, error } = useApp();
  const [maxAge, setMaxAge] = usePersisted('young-age', '22');
  const [position, setPosition] = usePersisted('young-pos', '');
  const [club, setClub] = usePersisted('young-club', '');
  const rows = useMemo(() => players
    .map((p) => ({ p, age: statByKey('age').get(p, totals[p.player_id]), v: production(totals[p.player_id]) }))
    .filter((r): r is { p: typeof r.p; age: number; v: number } => r.v != null && r.age != null && r.age <= Number(maxAge) && (r.p.games_played ?? 0) >= 20 && playsPosition(r.p, position) && (!club || r.p.club_full_name === club))
    .sort((a, b) => b.v - a.v), [players, totals, maxAge, position, club]);
  const paged = usePaged(rows, 20, [maxAge, position, club].join('|'));
  if (error) return <LoadError message={error} />;
  const top = rows[0]?.v ?? 1;
  return (
    <>
      <PageHead title="Young talent" intro="Ranked by Game Score per game, at least 20 games played. Ages are for the 2024-25 season." />
      <div className="filter-bar">
        <Segmented label="Maximum age" value={maxAge} options={[['20', '20 and under'], ['21', '21'], ['22', '22'], ['23', '23'], ['24', '24']]} onChange={setMaxAge} />
        <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        <TeamSelect value={club} onChange={setClub} />
        <span className="count-label">{rows.length} players</span>
      </div>
      {loading ? <Loading /> : (
        <section className="panel">
          <div className="detail-records-scroll open">
            <table className="detail-records-table roster-table">
              <thead><tr>{['Player', 'Age', ...COLS.map((c) => statByKey(c).short), 'Game Score', ''].map((h, i) => <th scope="col" key={i}>{h}</th>)}</tr></thead>
              <tbody>{paged.items.map(({ p, age, v }, i) => <tr key={p.player_id}><th scope="row"><div className="ranked-cell"><span className="rank-no">{paged.offset + i + 1}</span><PlayerCell player={p} /></div></th><td>{age}</td>{COLS.map((k) => <td key={k}>{formatStat(statByKey(k), statByKey(k).get(p, totals[p.player_id]))}</td>)}<td><div className="score-cell"><b>{v.toFixed(1)}</b><i className="rank-bar"><em style={{ width: `${Math.max(0, (v / top) * 100)}%` }} /></i></div></td><td><RowActions player={p} /></td></tr>)}</tbody>
            </table>
          </div>
          <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Young talent pages" />
        </section>
      )}
      {/* TODO(projections): needs several seasons in player_box_scores and player_advanced_stats; only 2024-25 is loaded. */}
      <section className="panel planned">
        <div className="panel-header"><div><h2>Planned: potential projections</h2><p>Not built yet. Needs earlier seasons in the database.</p></div></div>
        <ul>
          <li>Load each player’s previous seasons of box scores and advanced stats.</li>
          <li>Build an improvement curve per statistic and age.</li>
          <li>Project the next three seasons with a likely range, not one number.</li>
          <li>Show which past players developed along the same path.</li>
        </ul>
      </section>
    </>
  );
}
