import { useEffect, useState } from 'react';
import { useApp } from '../AppContext';
import { POSITIONS } from '../stats';
import { send } from '../useApi';
import { usePersisted } from '../usePersisted';
import { Loading, PlayerCell, RowActions, Segmented } from './Common';

type Suggestion = { player_id: number; because_of: number | null; similarity: number | null; shared: string[]; also_viewed_with: number | null; archetype: string | null };
type Suggestions = { basis: 'interests' | 'popular'; items: Suggestion[] };

/** Players for this person, from the shortlist, the comparison and recent views. Works without an account. */
export function Suggested({ limit = 6 }: { limit?: number }) {
  const { byId, favoriteIds, compareIds, historyIds } = useApp();
  const [position, setPosition] = usePersisted('suggest-pos', '');
  const [young, setYoung] = usePersisted<'all' | 'young'>('suggest-age', 'all');
  const [data, setData] = useState<Suggestions | null>(null);
  const [error, setError] = useState(false);
  const key = JSON.stringify({ favorites: favoriteIds.slice(0, 200), compared: compareIds.slice(0, 20), viewed: historyIds.slice(0, 50), limit, position: position || null, max_age: young === 'young' ? 23 : null });
  useEffect(() => {
    let cancelled = false;
    setError(false);
    send<Suggestions>('POST', '/suggestions', JSON.parse(key)).then((d) => { if (!cancelled) setData(d); }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [key]);
  if (error) return null; // the page works without this panel
  const reason = (s: Suggestion) => {
    const seed = s.because_of != null ? byId.get(s.because_of) : undefined;
    const seen = s.also_viewed_with != null ? byId.get(s.also_viewed_with) : undefined;
    if (!seed) return seen ? `Opened by people who look at ${seen.full_name}` : s.archetype ?? '';
    return `Like ${seed.full_name}${s.shared.length ? `: ${s.shared.join(', ')}` : ''}${seen ? `. Also viewed with ${seen.full_name}` : ''}`;
  };
  return (
    <>
      <div className="section-head"><div><h2>Suggested players</h2><p className="count-label">{data?.basis === 'popular' ? 'Open or shortlist players to make this list yours' : 'From your shortlist, comparisons and recent views, and what people with the same interests open'}</p></div>
        <div className="panel-tools">
          <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
          <Segmented label="Age" value={young} options={[['all', 'Any age'], ['young', '23 and under']]} onChange={setYoung} />
        </div>
      </div>
      {!data ? <Loading height="9rem" /> : !data.items.length ? <p className="status">No suggestions for these filters.</p> : (
        <div className="ideal-grid">{data.items.map((s) => { const p = byId.get(s.player_id); return p && <article key={s.player_id}><div className="result-head"><PlayerCell player={p} /><RowActions player={p} /></div><p>{reason(s)}</p>{s.similarity != null && <small>{Math.round(s.similarity * 100)}% match{s.archetype ? `, ${s.archetype.toLowerCase()}` : ''}</small>}</article>; })}</div>
      )}
    </>
  );
}
