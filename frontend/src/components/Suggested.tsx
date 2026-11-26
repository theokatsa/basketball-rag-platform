import { useEffect, useState } from 'react';
import { useApp } from '../AppContext';
import { send } from '../useApi';
import { teamVars } from '../teamColors';
import { Avatar } from './Avatar';
import { Loading, RowActions, TeamLogo } from './Common';
import { ChevronIcon } from './Icons';

type Suggestion = { player_id: number; because_of: number | null; similarity: number | null; shared: string[]; also_viewed_with: number | null; archetype: string | null; role: string | null; traits: string[] };
type Suggestions = { basis: 'interests' | 'popular'; items: Suggestion[] };

const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
/** What each role means, for players whose numbers clear no single strength. Names from ROLE_NAMES in similarity_service.py. */
const ROLE_LINES: Record<string, string> = {
  'Shot creator': 'Creates his own shot and finishes many of the team’s plays.',
  Playmaker: 'Runs the offense and sets up teammates before scoring himself.',
  Slasher: 'Attacks the rim off the dribble and pressures the ball on defense.',
  'Rim runner': 'Scores around the basket on cuts, lobs and putbacks.',
  'Stretch big': 'A big who finishes inside and spaces the floor from the corners.',
  'Spot-up wing': 'Plays heavy minutes and waits for catch-and-shoot threes.',
  'Floor spacer': 'Takes most of his shots from three, often from deep.',
  'Interior force': 'Draws fouls, controls the defensive glass and scores in the post.',
};

/** The people this person follows: their shortlist, newest first. */
function Shortlist() {
  const { byId, favoriteIds, open, go } = useApp();
  const list = favoriteIds.map((id) => byId.get(id)).filter((p) => p != null);
  return (
    <aside className="foryou-list" aria-label="Your shortlist">
      <header><h3>Your shortlist</h3>{list.length > 0 && <button type="button" className="more-link" onClick={() => go('shortlist')}>All {list.length}<ChevronIcon /></button>}</header>
      {!list.length ? <p className="foryou-empty">Tap the heart on any player to follow them here. Suggestions learn from it too.</p> : (
        <ol>
          {list.slice(0, 6).map((p) => (
            <li key={p.player_id}>
              <button type="button" style={teamVars(p.club_team_id)} onClick={() => open(p.player_id)}>
                <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" />
                <span className="foryou-name"><b>{p.full_name}</b><small>{p.club}, {p.position}</small></span>
                <span className="foryou-line"><b>{p.points?.toFixed(1)}</b><small>pts</small></span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </aside>
  );
}

/** Players for this person, from the shortlist, the comparison and recent views. withShortlist: the shortlist beside them. */
export function Suggested({ limit = 4, withShortlist = false }: { limit?: number; withShortlist?: boolean }) {
  const { byId, favoriteIds, compareIds, historyIds, open } = useApp();
  const [data, setData] = useState<Suggestions | null>(null);
  const [error, setError] = useState(false);
  const count = withShortlist ? 3 : limit;
  const key = JSON.stringify({ favorites: favoriteIds.slice(0, 200), compared: compareIds.slice(0, 20), viewed: historyIds.slice(0, 50), limit: count });
  useEffect(() => {
    let cancelled = false;
    setError(false);
    send<Suggestions>('POST', '/suggestions', JSON.parse(key)).then((d) => { if (!cancelled) setData(d); }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [key]);
  if (error && !withShortlist) return null; // the page works without this panel
  const tidy = (t: string) => capital(t.replace(' (adjusted)', '').replace(/ per 36$/, ' per 36 min'));
  const reason = (s: Suggestion) => {
    const seed = s.because_of != null ? byId.get(s.because_of) : undefined;
    const seen = s.also_viewed_with != null ? byId.get(s.also_viewed_with) : undefined;
    const who = seed ?? seen;
    if (!who) return <div className="why-box plain"><span className="why-kind">Popular starter</span><p>Opened often by scouts this month</p></div>;
    const alike = s.similarity != null ? Math.round(s.similarity * 100) : null;
    return (
      <div className={`why-box ${seed ? 'style' : 'crowd'}`} style={teamVars(who.club_team_id)}>
        <div className="why-head">
          <span className="why-kind">{seed ? 'Plays like' : 'Also opened with'}</span>
          {alike != null && <span className="why-meter" title={`${alike}% alike in how they play`}><i><em style={{ width: `${alike}%` }} /></i><b>{alike}%</b></span>}
        </div>
        <span className="why-who"><Avatar key={who.nba_player_id} name={who.full_name} nbaPlayerId={who.nba_player_id} className="player-thumb" /><b>{who.full_name}</b></span>
        {seed && s.shared.length > 0 && <span className="why-tags">{s.shared.slice(0, 2).map((t) => <span key={t}>{tidy(t)}</span>)}</span>}
        {!seed && <p>Scouts who open him often open this player too</p>}
      </div>
    );
  };
  const items = (data?.items ?? []).filter((s) => !favoriteIds.includes(s.player_id)); // never one already followed
  const cards = !data ? <Loading height="14rem" /> : !items.length ? <p className="status">No suggestions yet.</p> : (
    <div className={`suggest-grid ${withShortlist ? 'three' : ''}`}>
      {items.map((s) => { const p = byId.get(s.player_id); return p && (
        <article key={s.player_id} className="suggest-card" style={teamVars(p.club_team_id)}>
          <div className="suggest-top">
            <button type="button" className="suggest-who" onClick={() => open(p.player_id)}>
              <Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="suggest-photo" />
              <span><b>{p.full_name}</b><small><TeamLogo teamId={p.club_team_id} size={14} />{p.club}, {p.position}</small></span>
            </button>
            <RowActions player={p} />
          </div>
          {s.role && <span className="suggest-role">{s.role}</span>}
          {s.traits.length ? <ul className="suggest-traits">{s.traits.slice(0, 3).map((t) => <li key={t}>{capital(t)}</li>)}</ul> : <p className="suggest-traits role-line">{(s.role && ROLE_LINES[s.role]) ?? 'An all-round player with no single standout number.'}</p>}
          <div className="suggest-line"><span><b>{p.points?.toFixed(1)}</b> pts</span><span><b>{p.rebounds?.toFixed(1)}</b> reb</span><span><b>{p.assists?.toFixed(1)}</b> ast</span></div>
          {reason(s)}
        </article>
      ); })}
    </div>
  );
  const note = data?.basis === 'interests' ? 'Players you do not follow yet, from your shortlist, comparisons and recent views' : 'Open or shortlist players and these learn what you like';
  if (withShortlist) return (
    <section className="foryou" aria-label="For you">
      <Shortlist />
      <section className="suggest-box" aria-label="Suggested for you">
        <header><div><h3>Suggested for you</h3><small>{note}</small></div></header>
        {cards}
      </section>
    </section>
  );
  return (
    <section className="suggest">
      <div className="section-head"><div><h2>Suggested for you</h2><p className="count-label">{note}</p></div></div>
      {cards}
    </section>
  );
}
