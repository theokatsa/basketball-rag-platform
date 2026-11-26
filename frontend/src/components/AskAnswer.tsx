import { Fragment, useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { PlayerCell, RowActions } from './Common';
import { AnswerFeedback } from './Feedback';
import { QueryEditor } from './QueryEditor';
import type { StatQuery } from './QueryEditor';

export type Source = { ref: number; kind: string; title: string; player_id: number | null; full_name: string; season: string; source_text: string; similarity: number | null };
type Checks = { numbers: number; unsupported_numbers: string[]; misattributed?: string[]; invalid_citations: number[]; grounded: boolean };
type Table = { columns: string[]; rows: (string | number)[][] };
export type Answer = { options: string[]; understood: string; table: Table | null; answer: string; provider: string; model: string; sources: Source[]; plan: string[]; intent: string; checks: Checks | null; retrieval_ms: number; generation_ms: number; ask_id?: string | null; model_error?: string | null;
  reader?: 'llm' | 'rules' | 'edited'; query?: StatQuery | null; reader_note?: string; reader_model?: string;
  confidence?: number; signals?: { agree?: boolean | null; fallback?: boolean; calculated?: boolean } };

/** Why this answer may be a misreading, or null: the two readers disagree, a fallback answered, or documents did. */
function doubt(result: Answer): string | null {
  if (!result.confidence || result.provider === 'declined' || result.provider === 'clarify') return null;
  if (result.signals?.agree === false) return 'The two ways of reading the question disagree, so this may answer something else than you asked.';
  if (result.signals?.fallback && result.confidence < 0.5) return 'The language model could not use this question, so the word-matching reader answered; it often misses conditions.';
  if (result.confidence <= 0.3) return 'This answer was assembled from documents, not calculated; it may not answer the question exactly.';
  return null;
}

const FOLLOW_UPS = ['And at home?', 'What about Jokic?', 'And against the Celtics?'];
export const SCOPE = 'The 2024-25 regular season: box scores, shots, matchups, two-man lineups and team results.';
export const NOT_COVERED = 'Careers and other seasons, playoffs, awards and the draft, and anything that is not a statistic, such as character, health or contracts.';

function status(result: Answer): { label: string; tone: 'good' | 'plain' | 'warn' | 'accent' } {
  switch (result.provider) {
    case 'calculated': return { label: 'Calculated from the tables', tone: 'good' };
    case 'extractive': return { label: 'Quoted from the sources', tone: 'plain' };
    case 'declined': return { label: 'Not in the database', tone: 'warn' };
    case 'clarify': return { label: 'Which statistic?', tone: 'accent' };
    default: return { label: `Written by ${result.model || 'a language model'}`, tone: 'accent' };
  }
}

/** Answer text with [n] turned into buttons that jump to evidence card n. */
function Cited({ text, refs, onCite }: { text: string; refs: Set<number>; onCite: (n: number) => void }) {
  const parts = text.split(/(\[\d+\])/);
  return <>{parts.map((part, i) => {
    const n = /^\[(\d+)\]$/.exec(part)?.[1];
    return n && refs.has(Number(n))
      ? <button type="button" key={i} className="cite" aria-label={`Show source ${n}`} onClick={() => onCite(Number(n))}>{n}</button>
      : <Fragment key={i}>{part}</Fragment>;
  })}</>;
}

const NUMERIC = /^[+-]?[\d.,]+%?$|^\d+-\d+$/;

function AnswerTable({ table }: { table: Table }) {
  const { players, open } = useApp();
  const byName = useMemo(() => new Map(players.map((p) => [p.full_name, p.player_id])), [players]);
  const numeric = table.columns.map((_, j) => table.rows.every((r) => r[j] === '' || typeof r[j] === 'number' || NUMERIC.test(String(r[j]))));
  return (
    <div className="answer-table-wrap">
      <table className="answer-table">
        <thead><tr>{table.columns.map((c, j) => <th scope="col" key={c} className={numeric[j] ? 'num' : undefined}>{c}</th>)}</tr></thead>
        <tbody>{table.rows.map((row, i) => (
          <tr key={i}>{row.map((v, j) => {
            const id = typeof v === 'string' ? byName.get(v) : undefined;
            return <td key={j} className={numeric[j] ? 'num' : undefined}>{id != null ? <button type="button" className="player-link table-link" onClick={() => open(id)}>{v}</button> : v}</td>;
          })}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function EvidenceCard({ source, lit }: { source: Source; lit: boolean }) {
  const { byId } = useApp();
  const [full, setFull] = useState(false);
  const p = source.player_id != null ? byId.get(source.player_id) : undefined;
  const long = source.source_text.length > 180;
  const kind = p ? (source.title.startsWith(p.full_name) ? source.title.slice(p.full_name.length).trim() : source.title) || source.title : source.kind === 'computed' ? 'Calculated from the tables' : source.kind.replace(/_/g, ' ');
  return (
    <article id={`evidence-${source.ref}`} className={`evidence-card ${lit ? 'lit' : ''}`}>
      <div className="evidence-head">
        <span className="evidence-ref">{source.ref}</span>
        {p ? <PlayerCell player={p} note={kind} /> : <span className="evidence-title"><b>{source.title}</b><small>{kind}</small></span>}
        {p && <RowActions player={p} />}
      </div>
      <p className={full || !long ? '' : 'clamped'}>{source.source_text}</p>
      {long && <button type="button" className="text-button" aria-expanded={full} onClick={() => setFull(!full)}>{full ? 'Show less' : 'Show all'}</button>}
    </article>
  );
}

function readerLine(result: Answer): string {
  if (result.reader === 'edited') return 'Calculated as you changed it';
  if (result.reader === 'llm') return `Read by ${result.reader_model || 'a language model'} into the query below; change it and calculate again`;
  return 'Read by the word-matching reader';
}

export function AskAnswer({ result, question, busy, onAsk, onRecalculate }: { result: Answer; question: string; busy: boolean; onAsk: (q: string, previous?: string | null) => void; onRecalculate: (query: StatQuery) => void }) {
  const [lit, setLit] = useState<number | null>(null);
  const tag = status(result);
  const refs = new Set(result.sources.map((s) => s.ref));
  const seconds = (result.retrieval_ms + result.generation_ms) / 1000;
  const cite = (n: number) => {
    document.getElementById(`evidence-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setLit(n); window.setTimeout(() => setLit((v) => (v === n ? null : v)), 1600);
  };
  const declined = result.provider === 'declined';
  return (
    <div className={`ask-result ${result.query && result.reader !== 'rules' ? 'has-editor' : ''}`} aria-live="polite">
      <article className={`answer-card tone-${tag.tone}`}>
        <header className="answer-meta">
          <span className="answer-status"><i aria-hidden="true" />{tag.label}</span>
          {seconds > 0 && <small>{seconds < 1 ? `${Math.round(seconds * 1000)} ms` : `${seconds.toFixed(1)} s`}</small>}
        </header>
        {result.understood && result.understood !== question.trim() && <p className="answer-understood">Understood as “{result.understood}”</p>}
        <p className="answer-text"><Cited text={result.answer} refs={refs} onCite={cite} /></p>
        {doubt(result) && <p className="check-line warn" role="note">{doubt(result)} {result.query ? 'Check how it was read, and change it if needed.' : ''}</p>}
        {result.options?.length > 0 && (
          <div className="answer-options" aria-label="Possible meanings">
            {result.options.map((q) => <button type="button" className="chip" key={q} disabled={busy} onClick={() => onAsk(q, null)}>{q}</button>)}
          </div>
        )}
        {declined && <div className="scope-note"><p><b>What this covers:</b> {SCOPE}</p><p><b>Not covered:</b> {NOT_COVERED}</p></div>}
        {result.table && result.table.rows.length > 1 && <AnswerTable table={result.table} />}
        {result.checks && result.provider !== 'extractive' && result.provider !== 'calculated' && (result.checks.grounded
          ? <p className="check-line good">All {result.checks.numbers} numbers in the answer appear in the sources.</p>
          : <p className="check-line bad">Check this answer: {[result.checks.unsupported_numbers.length > 0 && `not found in the sources: ${result.checks.unsupported_numbers.join(', ')}`, (result.checks.misattributed?.length ?? 0) > 0 && `the sources give these to someone else: ${result.checks.misattributed!.join(', ')}`, result.checks.invalid_citations.length > 0 && `cites missing sources: ${result.checks.invalid_citations.join(', ')}`].filter(Boolean).join('; ')}.</p>)}
        {result.model_error ? <p className="check-line">The language model did not answer, so this answer was made without it.</p>
          : result.provider === 'extractive' && <p className="check-line">No language model is connected, so the answer quotes its sources.</p>}
        {result.ask_id && <AnswerFeedback key={result.ask_id} askId={result.ask_id} />}
      </article>

      {(result.plan.length > 0 || result.provider === 'calculated' || result.query) && (
        <div className="answer-side">
          <div className="reading">
            <h3>How the question was read</h3>
            <p className="reader-line">{readerLine(result)}</p>
            {result.reader_note && <p className="reader-line warn">{result.reader_note}</p>}
            {result.query && result.reader !== 'rules' && <QueryEditor query={result.query} busy={busy} onRun={onRecalculate} />}
            {result.plan.length > 0 && (result.query && result.reader !== 'rules' ? <details className="plan-details"><summary>What was calculated</summary><ol>{result.plan.map((step) => <li key={step}>{step}</li>)}</ol></details> : <ol>{result.plan.map((step) => <li key={step}>{step}</li>)}</ol>)}
          </div>
          {result.provider === 'calculated' && (
            <div className="reading">
              <h3>Ask next</h3>
              <div className="preset-row">{FOLLOW_UPS.map((q) => <button type="button" className="chip" key={q} disabled={busy} onClick={() => onAsk(q)}>{q}</button>)}</div>
            </div>
          )}
        </div>
      )}

      {result.sources.length > 0 && (
        <section className="evidence" aria-label="Evidence">
          <div className="evidence-bar"><h2>Evidence</h2><small>{result.sources.length} {result.sources.length === 1 ? 'source' : 'sources'}</small></div>
          <div className="evidence-grid">{result.sources.map((s) => <EvidenceCard key={s.ref} source={s} lit={lit === s.ref} />)}</div>
        </section>
      )}
    </div>
  );
}
