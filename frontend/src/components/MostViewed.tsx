import { useApp } from '../AppContext';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';
import { teamVars } from '../teamColors';
import { Avatar } from './Avatar';
import { Loading, TeamLogo } from './Common';

type Item = { player_id: number; viewers: number; previous: number | null; detail: string | null };
type Ranking = { items: Item[]; users: number; simulated: number };
type Mode = 'most' | 'trending' | 'gems';
const TABS: [Mode, string, string, JSX.Element][] = [
  ['trending', 'Trending', 'Rising fast', <path key="t" d="M3 17l6-6 4 4 8-8M15 7h6v6" />],
  ['most', 'This week', 'Most opened', <path key="m" d="M4 20V10M10 20V4M16 20v-7M22 20H2" />],
  ['gems', 'Hidden gems', 'Good, overlooked', <path key="g" d="M6 3h12l4 6-10 12L2 9zM2 9h20M12 21 8 9l4-6 4 6z" />],
];
const INTRO: Record<Mode, string> = {
  most: 'Opened by the most different people this week',
  trending: 'Viewed more in the last five days than usual',
  gems: 'Strong overall score, few people looking',
};

export const simulatedNote = (a: { users: number; simulated: number }) => (a.simulated ? `Based on ${a.users} accounts, ${a.simulated} of them simulated for testing.` : `Based on ${a.users} accounts.`);

/** Where the audience looks: this week, rising, or overlooked. Five cards. */
export function MostViewed() {
  const { byId, open } = useApp();
  const [mode, setMode] = usePersisted<Mode>('viewed-mode', 'trending');
  const { data, error } = useApi<Ranking>(`/audience/players?view=${mode}&limit=5${mode === 'most' ? '&days=7' : ''}`);
  if (error) return null; // the page works without this panel
  const move = (item: Item, place: number) => {
    if (mode !== 'most') return null;
    if (item.previous == null) return <span className="watch-move new">New</span>;
    const change = item.previous - place;
    return change > 0 ? <span className="watch-move up">▲ {change}</span> : change < 0 ? <span className="watch-move down">▼ {-change}</span> : <span className="watch-move">–</span>;
  };
  return (
    <section className="watch">
      <div className="section-head"><div><h2>What scouts are watching</h2><p className="count-label">{INTRO[mode]}</p></div>
        <div className="watch-tabs" role="tablist" aria-label="List">
          {TABS.map(([key, title, line, icon]) => (
            <button type="button" key={key} role="tab" aria-selected={mode === key} className={`watch-tab ${key} ${mode === key ? 'on' : ''}`} onClick={() => setMode(key)}>
              <svg viewBox="0 0 24 24" aria-hidden="true">{icon}</svg>
              <span><b>{title}</b><small>{line}</small></span>
            </button>
          ))}
        </div>
      </div>
      {!data ? <Loading height="12rem" /> : !data.items.length ? <p className="status">Nobody stands out at the moment.</p> : (
        <ol className="watch-grid" key={mode}>
          {data.items.map((item, i) => {
            const p = byId.get(item.player_id);
            return p && (
              <li key={item.player_id}>
                <button type="button" className="watch-card" style={teamVars(p.club_team_id)} onClick={() => open(p.player_id)}>
                  <span className="watch-rank">{i + 1}</span>
                  <span className="watch-logo"><TeamLogo teamId={p.club_team_id} size={90} /></span>
                  <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="watch-photo" />
                  <b>{p.full_name}</b>
                  <small>{p.club}, {p.position}</small>
                  <span className="watch-foot">{mode === 'most' ? <><span><b>{item.viewers}</b> scouts</span>{move(item, i + 1)}</> : <span className="watch-detail">{item.detail ?? `${item.viewers} scouts`}</span>}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
      {data && <p className="radar-note">{simulatedNote(data)}</p>}
    </section>
  );
}
