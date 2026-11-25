import { useApp } from '../AppContext';
import { POSITIONS } from '../stats';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';
import { Loading, PlayerCell, RowActions, Segmented } from './Common';

type Item = { player_id: number; viewers: number; previous: number | null; detail: string | null };
type Ranking = { items: Item[]; users: number; simulated: number };
type Mode = 'most' | 'trending' | 'gems';
const INTRO: Record<Mode, string> = {
  most: 'Counted in different users, so reloading a page changes nothing',
  trending: 'Viewed more in the last five days than their usual share explains',
  gems: 'Strong overall score, few people looking',
};

export const simulatedNote = (a: { users: number; simulated: number }) => (a.simulated ? `Based on ${a.users} accounts, ${a.simulated} of them simulated for testing.` : `Based on ${a.users} accounts.`);

export function MostViewed() {
  const { byId } = useApp();
  const [mode, setMode] = usePersisted<Mode>('viewed-mode', 'most');
  const [days, setDays] = usePersisted<'7' | '30' | '0'>('viewed-days', '7');
  const [position, setPosition] = usePersisted('viewed-pos', '');
  const { data, error } = useApi<Ranking>(`/audience/players?view=${mode}&limit=10${mode === 'most' ? `&days=${days}` : ''}${position ? `&position=${position}` : ''}`);
  if (error) return null; // the page works without this panel
  const top = data?.items[0]?.viewers || 1;
  const move = (item: Item, place: number) => {
    if (mode !== 'most' || days === '0') return '';
    if (item.previous == null) return 'new';
    const change = item.previous - place;
    return change > 0 ? `up ${change}` : change < 0 ? `down ${-change}` : 'same place';
  };
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>{mode === 'most' ? 'Most viewed players' : mode === 'trending' ? 'Trending players' : 'Hidden gems'}</h2><p>{INTRO[mode]}</p></div>
        <div className="panel-tools">
          <Segmented label="List" value={mode} options={[['most', 'Most viewed'], ['trending', 'Trending'], ['gems', 'Hidden gems']]} onChange={setMode} />
          {mode === 'most' && <Segmented label="Period" value={days} options={[['7', '7 days'], ['30', '30 days'], ['0', 'All time']]} onChange={setDays} />}
          <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
        </div>
      </div>
      {!data ? <Loading height="16rem" /> : !data.items.length ? <p className="status">Nobody stands out at the moment.</p> : (
        <ol className="rank-list similar-results">
          {data.items.map((item, i) => {
            const p = byId.get(item.player_id);
            return p && (
              <li key={item.player_id}>
                <span className="rank-no">{i + 1}</span>
                <PlayerCell player={p} />
                <span className="trait-list"><span>{item.detail ?? move(item, i + 1)}</span></span>
                <span className="match"><b>{item.viewers}</b><i className="rank-bar"><em style={{ width: `${(item.viewers / top) * 100}%` }} /></i></span>
                <RowActions player={p} />
              </li>
            );
          })}
        </ol>
      )}
      {data && <p className="radar-note">{simulatedNote(data)}</p>}
    </section>
  );
}
