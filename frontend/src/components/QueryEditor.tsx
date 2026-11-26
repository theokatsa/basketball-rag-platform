import { useEffect, useState } from 'react';
import { useApi } from '../useApi';
import { CloseIcon } from './Icons';

type Basis = 'per_game' | 'total' | 'in_game';
type Op = '>=' | '>' | '<=' | '<' | '==';
export type Condition = { stat: string; basis: Basis; op: Op; value: number };
export type Measure = { stat: string; basis: 'per_game' | 'total' | 'per_36'; plus: string[]; divide_by: string | null; multiply: number };
export type StatQuery = {
  answerable: boolean; reason: string | null; restated: string; topic: 'season' | 'single_game' | 'game_count' | 'other'; entity: 'player' | 'team';
  players: string[]; teams: string[]; on_teams: string[]; opponents: string[]; positions: string[]; conference: 'East' | 'West' | null; rookies: boolean;
  home: boolean | null; won: boolean | null; months: number[]; last_games: number | null; conditions: Condition[]; measure: Measure | null;
  operation: 'rank' | 'value' | 'count' | 'average' | 'sum' | 'list' | 'compare'; order: 'highest' | 'lowest'; limit: number;
};
type Catalog = { player: [string, string][]; team: [string, string][] };

const TOPICS: [StatQuery['topic'], string][] = [['season', 'Season numbers'], ['single_game', 'Single games'], ['game_count', 'Count games']];
const OPERATIONS: [StatQuery['operation'], string][] = [['rank', 'Rank'], ['value', 'Value for the named'], ['compare', 'Compare the named'], ['count', 'Count'], ['average', 'Average'], ['sum', 'Total'], ['list', 'List everyone']];
const BASES: [Basis, string][] = [['per_game', 'per game'], ['total', 'season total'], ['in_game', 'in one game']];
const OPS: Op[] = ['>=', '>', '<=', '<', '=='];
const POSITIONS = ['Guard', 'Forward', 'Center'];
const triple = (v: boolean | null) => (v == null ? 'any' : v ? 'yes' : 'no');
const fromTriple = (v: string) => (v === 'any' ? null : v === 'yes');

/** The question as the language model read it, as chips a person can change and calculate again. */
export function QueryEditor({ query, busy, onRun }: { query: StatQuery; busy: boolean; onRun: (q: StatQuery) => void }) {
  const catalog = useApi<Catalog>('/ask/catalog');
  const [draft, setDraft] = useState(query);
  useEffect(() => { setDraft(query); }, [query]);
  const changed = JSON.stringify(draft) !== JSON.stringify(query);
  const stats = catalog.data?.[draft.entity] ?? [];
  const set = (patch: Partial<StatQuery>) => setDraft((d) => ({ ...d, ...patch, restated: '' }));
  const setCondition = (i: number, patch: Partial<Condition>) => set({ conditions: draft.conditions.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
  const names = draft.entity === 'player' ? draft.players : draft.teams;
  const statSelect = (value: string, onChange: (v: string) => void, label: string) => (
    <select className="control-input" aria-label={label} value={value} onChange={(e) => onChange(e.target.value)}>
      {!stats.some(([k]) => k === value) && <option value={value}>{value}</option>}
      {stats.map(([key, text]) => <option key={key} value={key}>{text}</option>)}
    </select>
  );
  if (!draft.answerable) {
    return (
      <div className="query-editor">
        <p className="qe-note">The model read this as a question the database cannot answer{draft.reason ? ` (${draft.reason.replace(/_/g, ' ')})` : ''}.</p>
        <button type="button" className="ghost-button" disabled={busy} onClick={() => onRun({ ...draft, answerable: true, reason: null, topic: draft.topic === 'other' ? 'season' : draft.topic })}>Try to calculate anyway</button>
      </div>
    );
  }
  return (
    <form className="query-editor" onSubmit={(e) => { e.preventDefault(); onRun(draft); }}>
      <div className="qe-row">
        <span className="qe-label">Kind</span>
        <select className="control-input" aria-label="Kind of question" value={draft.topic} onChange={(e) => set({ topic: e.target.value as StatQuery['topic'] })}>
          {TOPICS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}
        </select>
        <select className="control-input" aria-label="Players or teams" value={draft.entity} onChange={(e) => set({ entity: e.target.value as StatQuery['entity'], measure: null, conditions: [] })}>
          <option value="player">Players</option><option value="team">Teams</option>
        </select>
      </div>
      {names.length > 0 && (
        <div className="qe-row">
          <span className="qe-label">Named</span>
          <span className="qe-chips">{names.map((n) => <button type="button" key={n} className="chip qe-chip" aria-label={`Remove ${n}`} onClick={() => set(draft.entity === 'player' ? { players: draft.players.filter((p) => p !== n) } : { teams: draft.teams.filter((t) => t !== n) })}>{n}<CloseIcon /></button>)}</span>
        </div>
      )}
      {draft.entity === 'player' && (
        <div className="qe-row">
          <span className="qe-label">Who</span>
          <span className="qe-chips">
            {POSITIONS.map((p) => <button type="button" key={p} className="chip" aria-pressed={draft.positions.includes(p)} onClick={() => set({ positions: draft.positions.includes(p) ? draft.positions.filter((x) => x !== p) : [...draft.positions, p] })}>{p}s</button>)}
            <button type="button" className="chip" aria-pressed={draft.rookies} onClick={() => set({ rookies: !draft.rookies })}>Rookies</button>
            {draft.on_teams.map((t) => <button type="button" key={t} className="chip qe-chip" aria-label={`Remove ${t}`} onClick={() => set({ on_teams: draft.on_teams.filter((x) => x !== t) })}>{t}<CloseIcon /></button>)}
          </span>
        </div>
      )}
      <div className="qe-row">
        <span className="qe-label">Games</span>
        <select className="control-input" aria-label="Home or away" value={triple(draft.home)} onChange={(e) => set({ home: fromTriple(e.target.value) })}><option value="any">Home and away</option><option value="yes">At home</option><option value="no">On the road</option></select>
        <select className="control-input" aria-label="Wins or losses" value={triple(draft.won)} onChange={(e) => set({ won: fromTriple(e.target.value) })}><option value="any">Wins and losses</option><option value="yes">In wins</option><option value="no">In losses</option></select>
        {draft.opponents.map((t) => <button type="button" key={t} className="chip qe-chip" aria-label={`Remove ${t}`} onClick={() => set({ opponents: draft.opponents.filter((x) => x !== t) })}>vs {t}<CloseIcon /></button>)}
      </div>
      <div className="qe-block">
        <span className="qe-label">Conditions</span>
        {draft.conditions.map((c, i) => (
          <div className="qe-condition" key={i}>
            {statSelect(c.stat, (stat) => setCondition(i, { stat }), `Condition ${i + 1}: statistic`)}
            <select className="control-input qe-basis" aria-label={`Condition ${i + 1}: counted`} value={c.basis} onChange={(e) => setCondition(i, { basis: e.target.value as Basis })}>{BASES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
            <select className="control-input qe-op" aria-label={`Condition ${i + 1}: comparison`} value={c.op} onChange={(e) => setCondition(i, { op: e.target.value as Op })}>{OPS.map((o) => <option key={o} value={o}>{o.replace('>=', '≥').replace('<=', '≤')}</option>)}</select>
            <input className="control-input qe-value" type="number" step="any" aria-label={`Condition ${i + 1}: value`} value={c.value} onChange={(e) => setCondition(i, { value: Number(e.target.value) })} />
            <button type="button" className="icon-button small" aria-label={`Remove condition ${i + 1}`} onClick={() => set({ conditions: draft.conditions.filter((_, j) => j !== i) })}><CloseIcon /></button>
          </div>
        ))}
        <button type="button" className="text-button" disabled={!stats.length} onClick={() => set({ conditions: [...draft.conditions, { stat: draft.entity === 'player' ? 'games' : 'wins', basis: 'total', op: '>=', value: 1 }] })}>+ Add a condition</button>
      </div>
      <div className="qe-row">
        <span className="qe-label">Measure</span>
        {draft.measure ? (
          <>
            {statSelect(draft.measure.stat, (stat) => set({ measure: { ...draft.measure!, stat } }), 'Measured statistic')}
            {draft.topic === 'season' && !draft.measure.divide_by && (
              <select className="control-input qe-basis" aria-label="Counted per game or in total" value={draft.measure.basis} onChange={(e) => set({ measure: { ...draft.measure!, basis: e.target.value as Measure['basis'] } })}>
                <option value="per_game">per game</option><option value="total">season total</option><option value="per_36">per 36 minutes</option>
              </select>
            )}
            {draft.measure.plus.length > 0 && <button type="button" className="chip qe-chip" aria-label="Remove the added statistics" onClick={() => set({ measure: { ...draft.measure!, plus: [] } })}>+ {draft.measure.plus.join(' + ')}<CloseIcon /></button>}
            {draft.measure.divide_by && <button type="button" className="chip qe-chip" aria-label="Remove the division" onClick={() => set({ measure: { ...draft.measure!, divide_by: null, multiply: 1 } })}>÷ {draft.measure.divide_by}<CloseIcon /></button>}
          </>
        ) : <button type="button" className="text-button" disabled={!stats.length} onClick={() => set({ measure: { stat: draft.entity === 'player' ? 'points' : 'wins', basis: 'per_game', plus: [], divide_by: null, multiply: 1 } })}>+ Choose a statistic</button>}
      </div>
      <div className="qe-row">
        <span className="qe-label">Answer</span>
        <select className="control-input" aria-label="What to calculate" value={draft.operation} onChange={(e) => set({ operation: e.target.value as StatQuery['operation'] })}>{OPERATIONS.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</select>
        <select className="control-input qe-op" aria-label="Highest or lowest first" value={draft.order} onChange={(e) => set({ order: e.target.value as StatQuery['order'] })}><option value="highest">Highest</option><option value="lowest">Lowest</option></select>
        <input className="control-input qe-value" type="number" min={1} max={25} aria-label="How many" value={draft.limit} onChange={(e) => set({ limit: Math.min(25, Math.max(1, Number(e.target.value) || 1)) })} />
      </div>
      <div className="qe-actions">
        <button type="submit" className="ghost-button accent" disabled={!changed || busy}>{busy ? 'Calculating…' : 'Recalculate'}</button>
        {changed && <button type="button" className="text-button" onClick={() => setDraft(query)}>Undo changes</button>}
      </div>
    </form>
  );
}
