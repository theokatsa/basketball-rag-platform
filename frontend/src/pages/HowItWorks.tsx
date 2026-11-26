import { useState } from 'react';
import type { FormEvent } from 'react';
import { LoadError, Loading, PageHead } from '../components/Common';
import { send, useApi } from '../useApi';

type Reader = { answer: string; provider: string; reader: string; understood: string; plan: string[]; confidence: number; reader_note: string; reader_model: string };
type Compared = { readers: { rules: Reader; llm?: Reader }; methods: Record<'keyword' | 'vector' | 'hybrid' | 'planned', { title: string; kind: string }[]> };
type Summary = {
  retrieval: { method: string; ndcg: number; questions: number }[];
  facts: { correct: number; total: number } | null;
  outside: { label: string; answerable: number; correct: number; should_decline: number; declined: number; model: string }[];
  similarity: { method: string; own_half_first: number; later_half_first: number }[];
};

const STEPS: [string, string][] = [
  ['Question', 'In English, or with Greek basketball words. A follow-up such as “and at home?” is made complete first.'],
  ['Reader', 'A language model turns the question into a small query: who, which games, which statistic, which calculation. It never writes a number. Without a model, a reader that matches words does this.'],
  ['Calculation', 'The query runs over every box score of 2024-25, held in memory, with the NBA.com qualifying minimums. What the query cannot say goes to the word-matching reader.'],
  ['Retrieval', 'Descriptions, such as a player’s style or who guards him, come from 3,127 documents: SQL filters, pgvector and full-text search.'],
  ['Answer', 'Written from numbered sources with citations, or the calculated sentence as it is.'],
  ['Checks', 'Every number must appear in a source and belong to the same player or team; citations must exist; an answer the system doubts says so.'],
];
const TRY = ['Which rookies averaged the most assists?', 'Best three-point shooters at home', 'Who plays like Jalen Brunson?', 'How many 30-point games did Devin Booker have?'];
const METHODS: [keyof Compared['methods'], string, string][] = [
  ['keyword', 'Keyword', 'Full-text search'], ['vector', 'Vector', 'Nearest embeddings'], ['hybrid', 'Hybrid', 'Both, merged by rank'], ['planned', 'Planned', 'Filters and rankings first'],
];
const pct = (a: number, b: number) => (b ? `${Math.round((100 * a) / b)}%` : '-');

function ReaderCard({ title, reader }: { title: string; reader?: Reader }) {
  if (!reader) return <article className="hw-reader muted"><h3>{title}</h3><p>Not available here: no language model key is set.</p></article>;
  return (
    <article className="hw-reader">
      <h3>{title}</h3>
      {reader.understood && <p className="answer-understood">Understood as “{reader.understood}”</p>}
      <p className="hw-answer">{reader.answer}</p>
      {reader.plan.length > 0 && <ol className="hw-plan">{reader.plan.map((s) => <li key={s}>{s}</li>)}</ol>}
      {reader.reader_note && <p className="reader-line warn">{reader.reader_note}</p>}
      <small className="hw-meta">{reader.provider}{reader.confidence ? ` · confidence ${reader.confidence.toFixed(2)}` : ''}</small>
    </article>
  );
}

function Compare() {
  const [question, setQuestion] = useState(TRY[0]);
  const [result, setResult] = useState<Compared | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async (q: string) => {
    if (q.trim().length < 3 || busy) return;
    setQuestion(q); setBusy(true); setError(null);
    try { setResult(await send<Compared>('POST', '/ask/compare', { question: q.trim() })); }
    catch (err) { setError(err instanceof Error ? err.message : 'The comparison failed.'); }
    finally { setBusy(false); }
  };
  return (
    <section className="panel wide hw-compare">
      <div className="panel-header"><div><h2>One question, every method</h2><p>The same question through both readers and the four ways of finding documents. Documents are what retrieval returns before an answer is written.</p></div></div>
      <form className="ask-bar" onSubmit={(e: FormEvent) => { e.preventDefault(); void run(question); }}>
        <input className="ask-input" aria-label="Question to compare" value={question} maxLength={500} onChange={(e) => setQuestion(e.target.value)} />
        <button type="submit" className="submit-button" disabled={busy || question.trim().length < 3}>{busy ? 'Comparing…' : 'Compare'}</button>
      </form>
      <div className="preset-row">{TRY.map((q) => <button type="button" key={q} className="chip" disabled={busy} onClick={() => void run(q)}>{q}</button>)}</div>
      {error && <p className="status error" role="alert">{error}</p>}
      {busy && <Loading height="14rem" />}
      {result && !busy && (
        <>
          <div className="hw-readers"><ReaderCard title="Word-matching reader" reader={result.readers.rules} /><ReaderCard title={`Language model reader${result.readers.llm?.reader_model ? ` (${result.readers.llm.reader_model})` : ''}`} reader={result.readers.llm} /></div>
          <div className="hw-methods">
            {METHODS.map(([key, name, note]) => (
              <div key={key} className="hw-method">
                <h3>{name}<small>{note}</small></h3>
                {result.methods[key].length ? <ol>{result.methods[key].map((d, i) => <li key={`${d.title}-${i}`}><span>{d.title}</span><em>{d.kind.replace(/_/g, ' ')}</em></li>)}</ol> : <p className="status">Nothing found.</p>}
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function Results() {
  const { data, error } = useApi<Summary>('/evaluation/summary');
  if (error) return <LoadError message={error} />;
  if (!data) return <Loading height="16rem" />;
  const top = Math.max(...data.retrieval.map((r) => r.ndcg), 1);
  return (
    <section className="panel wide hw-results">
      <div className="panel-header"><div><h2>What the tests found</h2><p>Read from backend/evaluation/results; docs/vector-and-rag.md explains every number and its limits.</p></div></div>
      <div className="hw-grid">
        <div>
          <h3>Finding the right documents</h3>
          <p className="hw-note">nDCG@6 on {data.retrieval[0]?.questions ?? 0} test questions written with answers computed by SQL. 1 is a perfect order.</p>
          <div className="simple-bars">{data.retrieval.map((r) => <div key={r.method}><span>{r.method}</span><b>{r.ndcg.toFixed(2)}</b><i><em style={{ width: `${(100 * r.ndcg) / top}%` }} /></i></div>)}</div>
        </div>
        <div>
          <h3>Answering questions written by others</h3>
          <p className="hw-note">{data.facts ? `On its own test questions the calculation was right ${data.facts.correct} of ${data.facts.total} times. ` : ''}Questions from the web are much harder.</p>
          <div className="answer-table-wrap">
            <table className="answer-table hw-table">
              <thead><tr><th scope="col">Test set and reader</th><th scope="col" className="num">Right</th><th scope="col" className="num">Declined when it should</th></tr></thead>
              <tbody>{data.outside.map((o) => <tr key={o.label}><td>{o.label}{o.model ? ` (${o.model})` : ''}</td><td className="num">{o.correct}/{o.answerable}<br /><small>{pct(o.correct, o.answerable)}</small></td><td className="num">{o.declined}/{o.should_decline}<br /><small>{pct(o.declined, o.should_decline)}</small></td></tr>)}</tbody>
            </table>
          </div>
        </div>
        <div>
          <h3>Similar players</h3>
          <p className="hw-note">A player’s statistics from odd games should find his own even games first, and his first half of the season his second half.</p>
          <div className="answer-table-wrap">
            <table className="answer-table hw-table">
              <thead><tr><th scope="col">Measure</th><th scope="col" className="num">Odd/even</th><th scope="col" className="num">Halves</th></tr></thead>
              <tbody>{data.similarity.map((s) => <tr key={s.method}><td>{s.method}</td><td className="num">{pct(s.own_half_first, 1)}</td><td className="num">{pct(s.later_half_first, 1)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

export function HowItWorks() {
  return (
    <>
      <PageHead title="How it works" intro="From a question to a checked answer, and how well each step did in the tests." />
      <section className="panel wide">
        <div className="panel-header"><div><h2>The pipeline</h2><p>Numbers are calculated from the database, never written by a language model.</p></div></div>
        <ol className="pipeline">{STEPS.map(([name, text], i) => <li key={name}><span className="pipeline-no">{i + 1}</span><b>{name}</b><p>{text}</p></li>)}</ol>
      </section>
      <Compare />
      <Results />
    </>
  );
}
