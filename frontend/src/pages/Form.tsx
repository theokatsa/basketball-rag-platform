import { useMemo } from 'react';
import { useApp } from '../AppContext';
import { LoadError, Loading, PageHead, PlayerCell, Segmented } from '../components/Common';
import type { PlayerForm } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';

type Key = 'points' | 'rebounds' | 'assists';

export function Form() {
  const { byId, loading, error } = useApp();
  const { data, error: formError } = useApi<PlayerForm[]>('/players/form?games=10');
  const [key, setKey] = usePersisted<Key>('form-stat', 'points');
  const rows = useMemo(() => (data ?? [])
    .filter((f) => f.earlier_minutes >= 15 || f.recent_minutes >= 15)
    .map((f) => ({ f, p: byId.get(f.player_id), recent: f[`recent_${key}`], earlier: f[`earlier_${key}`], change: f[`recent_${key}`] - f[`earlier_${key}`] }))
    .filter((r) => r.p != null)
    .sort((a, b) => b.change - a.change), [data, byId, key]);
  if (error || formError) return <LoadError message={(error ?? formError)!} />;
  const list = (items: typeof rows, hot: boolean) => (
    <section className="panel">
      <div className="panel-header"><h2>{hot ? 'Heating up' : 'Cooling off'}</h2></div>
      <ol className="form-list">
        {items.map(({ f, p, recent, earlier, change }) => {
          const max = Math.max(...f.recent_games, 1);
          return (
            <li key={f.player_id}>
              <PlayerCell player={p!} note={`${f.recent_minutes.toFixed(0)} min, was ${f.earlier_minutes.toFixed(0)}`} />
              <span className="spark" role="img" aria-label={`Points in the last 10 games: ${f.recent_games.join(', ')}`}>{f.recent_games.map((v, i) => <i key={i} style={{ height: `${Math.max(6, (v / max) * 100)}%` }} title={`${v} pts`} />)}</span>
              <span className="form-numbers"><b>{recent.toFixed(1)}</b><small>was {earlier.toFixed(1)}</small></span>
              <b className={`form-change ${hot ? 'up' : 'down'}`}>{change > 0 ? '+' : ''}{change.toFixed(1)}</b>
            </li>
          );
        })}
      </ol>
    </section>
  );
  return (
    <>
      <PageHead title="Hot and cold" intro="Each player's last 10 games of 2024-25 against the rest of the player's season." />
      <div className="filter-bar"><Segmented label="Statistic" value={key} options={[['points', 'Points'], ['rebounds', 'Rebounds'], ['assists', 'Assists']]} onChange={setKey} /><span className="count-label">Small bars show points in the last 10 games</span></div>
      {!data || loading ? <Loading /> : <div className="two-col">{list(rows.slice(0, 12), true)}{list(rows.slice(-12).reverse(), false)}</div>}
    </>
  );
}
