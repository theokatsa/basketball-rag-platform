import { useState } from 'react';
import type { FormEvent } from 'react';
import { useApp } from '../AppContext';
import { PageHead, PlayerCell, RowActions, Segmented } from '../components/Common';
import { CloseIcon } from '../components/Icons';
import { PlayerPicker } from '../components/PlayerPicker';
import { POSITIONS } from '../stats';
import type { SimilarPlayerResult } from '../types';
import { usePersisted } from '../usePersisted';

type Source = { player_id: number; full_name: string; season: string; source_text: string; similarity: number };
type Answer = { answer: string; provider: string; model: string; sources: Source[] };
const EXAMPLES = ['Which young players have a playing style similar to Giannis?', 'Who are the best rim protectors?', 'Find high-volume three-point shooters who pass well', 'Compare Jokic and Embiid'];

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) {
    const detail = ((await response.json().catch(() => null)) as { detail?: unknown } | null)?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'The request failed. Check the values and try again.');
  }
  return (await response.json()) as T;
}

function Ask() {
  const { byId } = useApp();
  const [question, setQuestion] = usePersisted('ask-q', '');
  const [result, setResult] = usePersisted<Answer | null>('ask-a', null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ask = async (q: string) => {
    if (q.trim().length < 3 || busy) return;
    setBusy(true); setError(null); setResult(null);
    try { setResult(await post<Answer>('/ask', { question: q.trim(), season: null, limit: 6 })); }
    catch (err) { setError(err instanceof Error ? err.message : 'The question could not be answered.'); }
    finally { setBusy(false); }
  };
  return (
    <section className="panel">
      <form className="ask-form" onSubmit={(e: FormEvent) => { e.preventDefault(); void ask(question); }}>
        <textarea className="control-input rag-question" aria-label="Your question" rows={3} maxLength={1000} value={question} onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void ask(question); } }} placeholder="Ask about styles, strengths or comparisons" />
        <button type="submit" className="submit-button" disabled={busy || question.trim().length < 3}>{busy ? 'Searching…' : 'Ask'}</button>
      </form>
      <div className="preset-row examples">{EXAMPLES.map((q) => <button type="button" className="chip" key={q} disabled={busy} onClick={() => { setQuestion(q); void ask(q); }}>{q}</button>)}</div>
      {busy && <div className="skeleton-block" aria-busy="true"><span className="skeleton" style={{ height: '9rem' }} /></div>}
      {error && <p className="status error" role="alert">{error}</p>}
      {result && (
        <div className="rag-output" aria-live="polite">
          {result.answer ? <p className="rag-answer">{result.answer}</p> : <p className="rag-note">No language model is connected, so there is no written answer. These are the players the search found. Set OPENROUTER_API_KEY in backend/.env to turn written answers on.</p>}
          <div className="section-head"><h2>Evidence</h2>{result.model && <span className="provider-badge">{result.model}</span>}</div>
          <div className="evidence-grid">
            {result.sources.map((s) => {
              const p = byId.get(s.player_id);
              return <article className="evidence-card" key={s.player_id}><div className="result-head">{p ? <><PlayerCell player={p} /><RowActions player={p} /></> : <b>{s.full_name}</b>}</div><p>{s.source_text}</p></article>;
            })}
            {!result.sources.length && <p className="status">Nothing in the database matched this question.</p>}
          </div>
        </div>
      )}
    </section>
  );
}

function Similar() {
  const { byId } = useApp();
  const [ref, setRef] = usePersisted<number | null>('sim-ref', null);
  const [minAge, setMinAge] = usePersisted('sim-min', '');
  const [maxAge, setMaxAge] = usePersisted('sim-max', '');
  const [position, setPosition] = usePersisted('sim-pos', '');
  const [active, setActive] = usePersisted<'any' | 'true' | 'false'>('sim-active', 'any');
  const [limit, setLimit] = usePersisted('sim-limit', '10');
  const [results, setResults] = usePersisted<SimilarPlayerResult[] | null>('sim-results', null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const player = ref != null ? byId.get(ref) : undefined;
  const badAges = Boolean(minAge && maxAge && Number(minAge) > Number(maxAge));
  const choose = (id: number | null) => { setRef(id); setResults(null); setError(null); };
  const run = async (event: FormEvent) => {
    event.preventDefault();
    if (ref == null || busy || badAges) return;
    const payload: Record<string, unknown> = { player_id: ref, limit: Math.min(50, Math.max(1, Math.round(Number(limit)) || 10)) };
    if (minAge) payload.min_age = Number(minAge);
    if (maxAge) payload.max_age = Number(maxAge);
    if (position) payload.position = position;
    if (active !== 'any') payload.is_active = active === 'true';
    setBusy(true); setError(null);
    try { setResults(await post<SimilarPlayerResult[]>('/search/similar-players', payload)); }
    catch (err) { setResults(null); setError(err instanceof Error ? err.message : 'The search failed.'); }
    finally { setBusy(false); }
  };
  return (
    <div className="similar-layout">
      <form className="panel search-form" onSubmit={run}>
        <h2>Find players like</h2>
        {player && <div className="ref-player"><PlayerCell player={player} /><button type="button" className="icon-button small" aria-label="Clear player" onClick={() => choose(null)}><CloseIcon /></button></div>}
        <PlayerPicker label="Reference player" placeholder={player ? 'Change player' : 'Choose a player'} onPick={choose} />
        <div className="grid-2">
          <label>Minimum age<input className="control-input" type="number" min={18} max={50} value={minAge} placeholder="Any" onChange={(e) => setMinAge(e.target.value)} /></label>
          <label>Maximum age<input className="control-input" type="number" min={18} max={50} value={maxAge} placeholder="Any" onChange={(e) => setMaxAge(e.target.value)} /></label>
        </div>
        {badAges && <p className="status error">Minimum age is above maximum age.</p>}
        <label>Position<select className="control-input" value={position} onChange={(e) => setPosition(e.target.value)}><option value="">Any</option>{POSITIONS.map((p) => <option key={p}>{p}</option>)}</select></label>
        <label>Status<select className="control-input" value={active} onChange={(e) => setActive(e.target.value as typeof active)}><option value="any">Any</option><option value="true">Active only</option><option value="false">Inactive only</option></select></label>
        <label>Results<input className="control-input" type="number" min={1} max={50} value={limit} onChange={(e) => setLimit(e.target.value)} /></label>
        <button type="submit" className="submit-button" disabled={ref == null || busy || badAges}>{busy ? 'Searching…' : 'Find similar players'}</button>
      </form>
      <section className="panel">
        {error && <p className="status error" role="alert">{error}</p>}
        {results && results.length > 0 && (
          <ol className="rank-list similar-results">
            {results.map((r, i) => {
              const p = byId.get(r.player_id);
              return p && (
                <li key={r.player_id}>
                  <span className="rank-no">{i + 1}</span>
                  <PlayerCell player={p} note={[p.club, p.position, r.age != null && `age ${r.age}`].filter(Boolean).join(', ')} />
                  <span className="trait-list">{r.shared_traits.map((t) => <span key={t}>{t}</span>)}</span>
                  <span className="match"><b>{Math.round(r.similarity * 100)}%</b><i className="rank-bar"><em style={{ width: `${r.similarity * 100}%` }} /></i></span>
                  <RowActions player={p} />
                </li>
              );
            })}
          </ol>
        )}
        {results && !results.length && <div className="empty-state"><p>No players match these filters.</p><small>Widen the age range or position.</small></div>}
        {!results && !error && <div className="empty-state"><p>Choose a player to start.</p><small>Matches compare twelve stats covering volume, shooting and defence, each scaled against the league.</small></div>}
      </section>
    </div>
  );
}

export function Scout() {
  const [tab, setTab] = usePersisted<'ask' | 'similar'>('scout-tab', 'ask');
  return (
    <>
      <PageHead title="Scout" intro={tab === 'ask' ? 'Ask in plain language and see the evidence behind it.' : 'Find players with the same statistical profile.'}><Segmented label="Tool" value={tab} options={[['ask', 'Ask a question'], ['similar', 'Find similar']]} onChange={setTab} /></PageHead>
      {tab === 'ask' ? <Ask /> : <Similar />}
    </>
  );
}
