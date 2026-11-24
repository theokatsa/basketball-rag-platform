import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { LoadError, Loading, PageHead, PlayerCell, RowActions, Segmented } from '../components/Common';
import { formatStat, playsPosition, POSITIONS, production, statByKey } from '../stats';
import { usePersisted } from '../usePersisted';

const COLS = ['minutes', 'points', 'rebounds', 'assists', 'ts'];

export function YoungTalent() {
  const { players, totals, loading, error } = useApp();
  const [maxAge, setMaxAge] = usePersisted('young-age', '23');
  const [position, setPosition] = usePersisted('young-pos', '');
  const rows = useMemo(() => players
    .filter((p) => p.age != null && p.age <= Number(maxAge) && (p.games_played ?? 0) >= 20 && playsPosition(p, position))
    .map((p) => ({ p, v: production(totals[p.player_id]) }))
    .filter((r): r is { p: typeof r.p; v: number } => r.v != null)
    .sort((a, b) => b.v - a.v), [players, totals, maxAge, position]);
  if (error) return <LoadError message={error} />;
  const top = rows[0]?.v ?? 1;
  return (
    <>
      <PageHead title="Young talent" intro="Ranked by Game Score per game, at least 20 games played." />
      <div className="filter-bar">
        <Segmented label="Maximum age" value={maxAge} options={[['21', '21 and under'], ['22', '22'], ['23', '23'], ['25', '25']]} onChange={setMaxAge} />
        <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        <span className="count-label">{rows.length} players</span>
      </div>
      {loading ? <Loading /> : (
        <section className="panel">
          <div className="detail-records-scroll open">
            <table className="detail-records-table roster-table">
              <thead><tr>{['Player', 'Age', ...COLS.map((c) => statByKey(c).short), 'Game Score', ''].map((h, i) => <th scope="col" key={i}>{h}</th>)}</tr></thead>
              <tbody>{rows.slice(0, 60).map(({ p, v }, i) => <tr key={p.player_id}><th scope="row"><div className="ranked-cell"><span className="rank-no">{i + 1}</span><PlayerCell player={p} /></div></th><td>{p.age}</td>{COLS.map((k) => <td key={k}>{formatStat(statByKey(k), statByKey(k).get(p, totals[p.player_id]))}</td>)}<td><div className="score-cell"><b>{v.toFixed(1)}</b><i className="rank-bar"><em style={{ width: `${Math.max(0, (v / top) * 100)}%` }} /></i></div></td><td><RowActions player={p} /></td></tr>)}</tbody>
            </table>
          </div>
          <p className="radar-note">Ages are the ones on record (collected in 2026), so players were about a year or more younger during the 2024-25 season.</p>
        </section>
      )}
    </>
  );
}
