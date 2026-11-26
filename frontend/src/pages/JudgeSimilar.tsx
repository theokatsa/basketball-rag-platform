import { useCallback, useEffect, useState } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { PageHead, TeamLogo } from '../components/Common';
import type { PlayerDirectoryRow } from '../types';
import { send } from '../useApi';
import { visitorId } from '../visitor';

type Trial = { trial: string; player_id: number; left: number[]; right: number[]; judged: number };
type Choice = 'left' | 'right' | 'same';

function line(p: PlayerDirectoryRow) {
  return [p.club, p.position, p.points != null && `${p.points.toFixed(1)} pts`, p.rebounds != null && `${p.rebounds.toFixed(1)} reb`, p.assists != null && `${p.assists.toFixed(1)} ast`].filter(Boolean).join(' · ');
}

function List({ name, ids, onPick, busy }: { name: string; ids: number[]; onPick: () => void; busy: boolean }) {
  const { byId } = useApp();
  return (
    <div className="judge-list">
      <h3>List {name}</h3>
      <ol>{ids.map((id) => { const p = byId.get(id); return p && <li key={id}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" /><span><b>{p.full_name}</b><small>{line(p)}</small></span></li>; })}</ol>
      <button type="button" className="submit-button" disabled={busy} onClick={onPick}>List {name} is more alike</button>
    </div>
  );
}

/** The blind test: two lists of similar players from two methods, in random order. Which is more alike? */
export function JudgeSimilar() {
  const { byId } = useApp();
  const [trial, setTrial] = useState<Trial | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'done' | 'error'>('loading');
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const next = useCallback(async () => {
    setState('loading');
    try {
      const t = await send<Trial | null>('GET', `/judge/next?visitor=${visitorId()}`);
      setTrial(t); setState(t ? 'ready' : 'done');
      if (t) setCount(t.judged);
    } catch { setState('error'); }
  }, []);
  useEffect(() => { void next(); }, [next]);
  const answer = async (choice: Choice) => {
    if (!trial || busy) return;
    setBusy(true);
    try { await send('POST', '/judge', { trial: trial.trial, visitor: visitorId(), choice }); } catch { /* an expired pair: the next one follows */ }
    setBusy(false);
    void next();
  };
  const player = trial ? byId.get(trial.player_id) : undefined;
  return (
    <>
      <PageHead title="Judge similar players" intro="Two methods suggest players who play like the one on top. You see their lists in random order, without knowing which is which. Pick the list that is more alike." />
      <section className="panel wide judge">
        {state === 'loading' && <span className="skeleton" style={{ height: '22rem' }} />}
        {state === 'error' && <p className="status error" role="alert">The next pair could not be loaded. Check that the backend is running.</p>}
        {state === 'done' && <div className="empty-state"><p>You have judged every player in the test. Thank you.</p></div>}
        {state === 'ready' && trial && player && (
          <>
            <div className="judge-player">
              <Avatar key={player.nba_player_id} name={player.full_name} nbaPlayerId={player.nba_player_id} className="judge-photo" />
              <div><small>Players most like</small><h2>{player.full_name}</h2><p>{line(player)}</p></div>
              <TeamLogo teamId={player.club_team_id} size={56} />
            </div>
            <div className="judge-lists">
              <List name="A" ids={trial.left} busy={busy} onPick={() => void answer('left')} />
              <List name="B" ids={trial.right} busy={busy} onPick={() => void answer('right')} />
            </div>
            <div className="judge-actions">
              <button type="button" className="ghost-button" disabled={busy} onClick={() => void answer('same')}>About the same</button>
              <button type="button" className="text-button" disabled={busy} onClick={() => void next()}>I don’t know these players, skip</button>
              <small>{count} judged in this browser. Saved without your name; a random number keeps one person’s answers together.</small>
            </div>
          </>
        )}
      </section>
    </>
  );
}
