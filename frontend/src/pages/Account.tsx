import { useState } from 'react';
import type { FormEvent } from 'react';
import { useApp } from '../AppContext';
import { Loading, PageHead, PlayerCell, Segmented } from '../components/Common';
import type { User } from '../types';
import { forget, send, useApi } from '../useApi';
import { formatDate } from '../utils';

export function Login() {
  const { user, signedIn, go } = useApp();
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (user && !busy) return <div className="empty-state"><p>You are signed in as {user.display_name}.</p><small><button type="button" className="link-button" onClick={() => go('account')}>Go to your account</button></small></div>;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true); setError(null);
    try {
      const account = await send<User>('POST', mode === 'login' ? '/auth/login' : '/auth/signup', mode === 'login' ? { email, password } : { email, password, display_name: name });
      await signedIn(account, true);
      go('account');
    } catch (err) { setError(err instanceof Error ? err.message : 'Something went wrong.'); setBusy(false); }
  };
  return (
    <div className="login-page">
      <section className="panel login-card">
        <h1>{mode === 'login' ? 'Sign in' : 'Create account'}</h1>
        <Segmented label="Sign in or create an account" value={mode} options={[['login', 'Sign in'], ['signup', 'Create account']]} onChange={(m) => { setMode(m); setError(null); }} />
        <form onSubmit={submit}>
          {mode === 'signup' && <label>Name<input className="control-input" autoComplete="name" required minLength={2} maxLength={40} value={name} onChange={(e) => setName(e.target.value)} /></label>}
          <label>Email<input className="control-input" type="email" autoComplete="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label>Password<input className="control-input" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required minLength={mode === 'signup' ? 8 : 1} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />{mode === 'signup' && <small>At least 8 characters</small>}</label>
          {error && <p className="status error" role="alert">{error}</p>}
          <button type="submit" className="submit-button" disabled={busy}>{busy ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}</button>
        </form>
      </section>
      <aside className="login-why">
        <h2>With an account</h2>
        <ul><li>Your shortlist, groups and recent players follow you to any device.</li><li>See which players you study most.</li><li>Get suggestions from what other users look at.</li></ul>
        <p>While you are signed in we record which player pages you open, to build the “also viewed” lists. Others only ever see totals. You can erase your history at any time.</p>
      </aside>
    </div>
  );
}

type Activity = { views: { player_id: number; views: number; last_viewed: string }[]; days: { day: string; views: number }[]; visits: number; suggested: { player_id: number; viewers: number }[] };

export function Account() {
  const { user, byId, favoriteIds, signOut, go } = useApp();
  const [version, setVersion] = useState(0);
  const { data, error } = useApi<Activity>(user ? `/me/activity?v=${version}` : null);
  const [password, setPassword] = useState('');
  const [problem, setProblem] = useState<string | null>(null);
  if (!user) return <div className="empty-state"><p>You are not signed in.</p><small><button type="button" className="link-button" onClick={() => go('login')}>Sign in or create an account</button></small></div>;
  const erase = async () => {
    if (!window.confirm('Erase your viewing history? This cannot be undone.')) return;
    try { await send('DELETE', '/me/activity'); forget('/me/'); setVersion((v) => v + 1); } catch (err) { setProblem(err instanceof Error ? err.message : 'Something went wrong.'); }
  };
  const remove = async (e: FormEvent) => {
    e.preventDefault();
    if (!window.confirm('Delete your account and everything saved in it?')) return;
    try { await send('POST', '/me/delete', { password }); await signOut(); go('home'); } catch (err) { setProblem(err instanceof Error ? err.message : 'Something went wrong.'); }
  };
  const total = data?.views.reduce((s, v) => s + v.views, 0) ?? 0;
  const positions = new Map<string, number>(), teams = new Map<string, number>();
  for (const v of data?.views ?? []) {
    const p = byId.get(v.player_id);
    if (!p) continue;
    const main = `${(p.position ?? 'Unknown').split('-')[0]}s`;
    positions.set(main, (positions.get(main) ?? 0) + v.views);
    if (p.club_full_name) teams.set(p.club_full_name, (teams.get(p.club_full_name) ?? 0) + v.views);
  }
  const ranked = (m: Map<string, number>) => [...m].sort((a, b) => b[1] - a[1]).slice(0, 5);
  const bars = (rows: [string, number][]) => <div className="simple-bars">{rows.map(([label, v]) => <div key={label}><span>{label}</span><b>{v}</b><i><em style={{ width: `${(v / Math.max(1, rows[0][1])) * 100}%` }} /></i></div>)}</div>;
  return (
    <>
      <PageHead title={user.display_name} intro={`${user.email}. Member since ${formatDate(user.created_at.slice(0, 10))}.`}><button type="button" className="ghost-button" onClick={() => { void signOut().then(() => go('home')); }}>Sign out</button></PageHead>
      {error ? <p className="status error">{error}</p> : !data ? <Loading /> : (
        <>
          <div className="account-tiles">{([[total, 'player views'], [data.views.length, 'different players'], [data.visits, 'visits'], [favoriteIds.length, 'shortlisted']] as const).map(([v, label]) => <div className="panel" key={label}><strong>{v}</strong><span>{label}</span></div>)}</div>
          {!data.views.length ? <div className="empty-state"><p>No views recorded yet.</p><small>Open a few player pages and come back.</small></div> : (
            <div className="two-col">
              <section className="panel"><div className="panel-header"><h2>Players you study most</h2></div><ol className="rank-list lab-list">{data.views.slice(0, 8).map((v, i) => { const p = byId.get(v.player_id); return p && <li key={v.player_id}><span className="rank-no">{i + 1}</span><PlayerCell player={p} /><span /><b>{v.views}</b></li>; })}</ol></section>
              <section className="panel"><div className="panel-header"><h2>Positions</h2></div>{bars(ranked(positions))}<div className="panel-header second"><h2>Teams</h2></div>{bars(ranked(teams))}</section>
            </div>
          )}
          {data.suggested.length > 0 && <section className="panel"><div className="panel-header"><div><h2>You might look at next</h2><p>Opened by users who study the same players</p></div></div><div className="suggest-grid">{data.suggested.map((s) => { const p = byId.get(s.player_id); return p && <PlayerCell key={s.player_id} player={p} note={`${s.viewers} ${s.viewers === 1 ? 'user' : 'users'}`} />; })}</div></section>}
        </>
      )}
      <details className="panel danger-zone">
        <summary>Privacy and account</summary>
        <button type="button" className="ghost-button" onClick={() => void erase()}>Erase viewing history</button>
        <form onSubmit={remove}><label>Password<input className="control-input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label><button type="submit" className="ghost-button">Delete account</button></form>
        {problem && <p className="status error" role="alert">{problem}</p>}
      </details>
    </>
  );
}
