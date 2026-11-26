import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useApp } from '../AppContext';
import { send } from '../useApi';
import { usePersisted } from '../usePersisted';
import { loadStored, saveStored } from '../utils';
import { keepsQuestions, randomId, setKeepsQuestions, visitorId } from '../visitor';
import { AskAnswer, NOT_COVERED, SCOPE } from './AskAnswer';
import type { Answer } from './AskAnswer';
import { CloseIcon } from './Icons';
import type { StatQuery } from './QueryEditor';

type Turn = { question: string; answer: Answer | null; error?: string };
type ChatItem = { id: string; title: string; updated_at: string; turns: number };

const ACTIVE_KEY = 'basketball-scouting-chat';
const EXAMPLES: [string, string[]][] = [
  ['Players', ['How many 30-point games did LeBron have?', 'Who made the most dunks?']],
  ['Leaders', ['Best corner three shooters', 'Who had the most double-doubles?']],
  ['Teams', ['Which team had the best defense?', "What is the Knicks' record on the road?", 'Which team scores the most in the fourth quarter?']],
  ['Matchups', ['Who guards Stephen Curry best?', 'Net rating of Tatum and Brown together']],
  ['Scouting', ['Players like Giannis under 25', 'Who should the Lakers sign?']],
];
const when = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

/** One question and its answer. The latest answer is open; earlier ones open on a click. */
function TurnView({ turn, latest, busy, onAsk, onRecalculate }: { turn: Turn; latest: boolean; busy: boolean; onAsk: (q: string, previous?: string | null) => void; onRecalculate: (q: StatQuery) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="chat-turn">
      <p className="chat-question"><span>{turn.question}</span></p>
      {turn.error && <p className="status error" role="alert">{turn.error}</p>}
      {!turn.answer && !turn.error && (
        <div className="ask-loading" aria-busy="true"><p>Reading the question and searching the season…</p><span className="skeleton" style={{ height: '4.5rem' }} /></div>
      )}
      {turn.answer && (latest || open
        ? <>
            <AskAnswer result={turn.answer} question={turn.question} busy={busy} onAsk={onAsk} onRecalculate={onRecalculate} />
            {!latest && <button type="button" className="text-button" onClick={() => setOpen(false)}>Fold</button>}
          </>
        : <button type="button" className="chat-folded" onClick={() => setOpen(true)}><span>{turn.answer.answer}</span><small>Show the sources and how it was read</small></button>)}
    </div>
  );
}

/** The Scout chat: conversations kept on the server, so they come back after a refresh. */
export function Chat() {
  const { user } = useApp();
  const [chats, setChats] = useState<ChatItem[]>([]);
  const [active, setActive] = useState<string | null>(() => loadStored<string | null>(ACTIVE_KEY, null));
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [keep, setKeep] = useState(keepsQuestions);
  const fresh = useRef(new Set<string>()); // started here and not stored yet: nothing to fetch
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const owner = `visitor=${visitorId()}`;

  const refresh = useCallback(async () => {
    try { setChats(await send<ChatItem[]>('GET', `/chats?${owner}`)); } catch { /* the list is a convenience */ }
  }, [owner, user?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { saveStored(ACTIVE_KEY, active); }, [active]);
  useEffect(() => {
    if (!active) { setTurns([]); return; }
    if (fresh.current.has(active)) return;
    let cancelled = false;
    send<{ question: string; answer: Answer }[]>('GET', `/chats/${active}?${owner}`)
      .then((found) => { if (!cancelled) setTurns(found.map((t) => ({ question: t.question, answer: t.answer }))); })
      .catch(() => { if (!cancelled) { setActive(null); setTurns([]); } });
    return () => { cancelled = true; };
  }, [active, owner]);
  useLayoutEffect(() => { const el = input.current; if (el) { el.style.height = 'auto'; el.style.height = `${el.scrollHeight}px`; } }, [question]);
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }); }, [turns.length]);

  const post = async (text: string, body: Record<string, unknown>) => {
    const id = active ?? randomId();
    if (!active) { fresh.current.add(id); setActive(id); }
    setTurns((all) => [...all, { question: text, answer: null }]);
    setBusy(true);
    try {
      const answer = await send<Answer>('POST', '/ask', { question: text, season: null, limit: 6, log: keep, visitor: visitorId(), chat_id: id, ...body });
      setTurns((all) => all.map((t, i) => (i === all.length - 1 ? { ...t, answer } : t)));
      window.setTimeout(() => void refresh(), 900); // the turn is kept after the answer is sent
    } catch (err) {
      setTurns((all) => all.map((t, i) => (i === all.length - 1 ? { ...t, error: err instanceof Error ? err.message : 'The question could not be answered.' } : t)));
    } finally { setBusy(false); }
  };
  const last = [...turns].reverse().find((t) => t.answer)?.answer;
  const ask = (q: string, previous: string | null = last?.understood || null) => {
    const text = q.trim();
    if (text.length < 3 || busy) return;
    setQuestion('');
    void post(text, { previous });
  };
  const recalculate = (query: StatQuery) => {
    const asked = turns[turns.length - 1]?.question;
    if (asked && !busy) void post(asked, { query });
  };
  const startNew = () => { setActive(null); setTurns([]); setQuestion(''); input.current?.focus(); };
  const remove = async (id: string) => {
    if (!window.confirm('Delete this conversation?')) return;
    try { await send('DELETE', `/chats/${id}?${owner}`); } catch { /* already gone */ }
    if (id === active) startNew();
    void refresh();
  };

  /** A question sent from another page is asked once, in a new conversation. */
  const [pending, setPending] = usePersisted('ask-pending', '');
  const sent = useRef(false);
  useEffect(() => { if (pending && !sent.current) { sent.current = true; setPending(''); setActive(null); window.setTimeout(() => ask(pending, null), 0); } }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="chat-layout">
      <aside className="chat-list" aria-label="Your conversations">
        <button type="button" className="ghost-button accent" onClick={startNew}>+ New chat</button>
        {chats.length > 0 ? (
          <ul>{chats.map((c) => (
            <li key={c.id} className={c.id === active ? 'active' : ''}>
              <button type="button" className="chat-open" aria-current={c.id === active ? 'true' : undefined} onClick={() => { fresh.current.delete(c.id); setActive(c.id); }}>
                <b>{c.title || 'Untitled'}</b><small>{when(c.updated_at)} · {c.turns} {c.turns === 1 ? 'question' : 'questions'}</small>
              </button>
              <button type="button" className="icon-button small" aria-label={`Delete “${c.title}”`} onClick={() => void remove(c.id)}><CloseIcon /></button>
            </li>
          ))}</ul>
        ) : <p className="chat-empty">Your conversations appear here and stay after a refresh.</p>}
      </aside>
      <section className="panel ask-panel chat-main">
        {turns.length === 0 && (
          <div className="ask-guide">
            <div className="example-groups">
              {EXAMPLES.map(([group, questions]) => (
                <div className="example-group" key={group}><h3>{group}</h3>{questions.map((q) => <button type="button" key={q} disabled={busy} onClick={() => ask(q, null)}>{q}</button>)}</div>
              ))}
            </div>
            <div className="scope-note"><p><b>What this covers:</b> {SCOPE}</p><p><b>Not covered:</b> {NOT_COVERED}</p></div>
          </div>
        )}
        {turns.map((t, i) => <TurnView key={`${active}-${i}`} turn={t} latest={i === turns.length - 1} busy={busy} onAsk={(q, previous) => ask(q, previous)} onRecalculate={recalculate} />)}
        <div ref={end} />
        <form className="ask-bar" onSubmit={(e: FormEvent) => { e.preventDefault(); ask(question); }}>
          <textarea ref={input} className="ask-input" aria-label="Your question" rows={1} maxLength={1000} value={question} onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(question); } }}
            placeholder={turns.length ? 'Ask a follow-up: “and at home?”, “what about Jokić?”' : 'Ask about a player, a team, a matchup or a type of shot'} />
          {question && <button type="button" className="icon-button small" aria-label="Clear the question" onClick={() => setQuestion('')}><CloseIcon /></button>}
          <button type="submit" className="submit-button" disabled={busy || question.trim().length < 3}>{busy ? 'Answering…' : 'Ask'}</button>
        </form>
        <p className="keep-note">
          Conversations are kept for you{user ? ' in your account' : ' in this browser'}; delete any of them on the left.{' '}
          {keep ? 'Questions are also kept, without your name, to test how well the system understands people.' : 'Your questions are not kept for testing.'}{' '}
          <button type="button" className="text-button" onClick={() => { setKeep(!keep); setKeepsQuestions(!keep); }}>{keep ? 'Don’t keep them for testing' : 'Keep them again'}</button>
        </p>
      </section>
    </div>
  );
}
