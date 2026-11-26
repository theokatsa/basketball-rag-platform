import { useState } from 'react';
import { send } from '../useApi';
import { visitorId } from '../visitor';

const REASONS: [string, string][] = [
  ['wrong_stat', 'Wrong statistic'],
  ['wrong_player', 'Wrong player or team'],
  ['wrong_number', 'A number is wrong'],
  ['should_decline', 'It should have said it can’t answer'],
  ['other', 'Something else'],
];

type Stage = 'ask' | 'why' | 'sending' | 'done' | 'error';

/** "Was this right?" under an answer. A no asks what went wrong; both are saved with the logged question. */
export function AnswerFeedback({ askId }: { askId: string }) {
  const [stage, setStage] = useState<Stage>('ask');
  const [reason, setReason] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [error, setError] = useState('');
  const save = async (helpful: boolean) => {
    setStage('sending');
    try {
      await send('POST', '/feedback/answer', { ask_id: askId, helpful, reason: helpful ? null : reason, comment: helpful ? null : comment || null });
      setStage('done');
    } catch (err) { setError(err instanceof Error ? err.message : 'Not saved.'); setStage('error'); }
  };
  if (stage === 'done') return <p className="feedback-line done" role="status">Thanks. This goes into the evaluation of the system.</p>;
  if (stage === 'error') return <p className="feedback-line bad" role="alert">{error}</p>;
  if (stage === 'why' || (stage === 'sending' && reason !== null)) {
    return (
      <form className="feedback-why" onSubmit={(e) => { e.preventDefault(); void save(false); }}>
        <p>What went wrong?</p>
        <div className="preset-row" role="group" aria-label="What went wrong">
          {REASONS.map(([key, label]) => <button type="button" key={key} className="chip" aria-pressed={reason === key} onClick={() => setReason(key)}>{label}</button>)}
        </div>
        <label className="visually-hidden" htmlFor={`fb-${askId}`}>What the answer should have said (optional)</label>
        <textarea id={`fb-${askId}`} className="control-input feedback-comment" rows={2} maxLength={600} value={comment} placeholder="What should it have said? (optional)" onChange={(e) => setComment(e.target.value)} />
        <div className="feedback-actions">
          <button type="submit" className="ghost-button accent" disabled={reason === null || stage === 'sending'}>{stage === 'sending' ? 'Saving…' : 'Send'}</button>
          <button type="button" className="text-button" onClick={() => { setStage('ask'); setReason(null); }}>Cancel</button>
        </div>
      </form>
    );
  }
  return (
    <div className="feedback-line" role="group" aria-label="Was this answer right?">
      <span>Was this answer right?</span>
      <button type="button" className="chip" disabled={stage === 'sending'} onClick={() => void save(true)}>Yes</button>
      <button type="button" className="chip" disabled={stage === 'sending'} onClick={() => { setReason(null); setStage('why'); }}>No</button>
    </div>
  );
}

export type Verdict = { good: boolean } | 'sending' | 'error';

/** "Is X a good match?" beside a similar player. One verdict per person, list and player; a second click replaces it. */
export function MatchFeedback({ playerId, otherId, otherName, kind, variant, rank, similarity, votes, onVote }: {
  playerId: number; otherId: number; otherName: string; kind: string; variant: string; rank: number; similarity: number;
  votes: Record<string, Verdict>; onVote: (key: string, verdict: Verdict) => void;
}) {
  const key = `${kind}:${variant}:${otherId}`;
  const verdict = votes[key];
  const vote = async (good: boolean) => {
    onVote(key, 'sending');
    try {
      await send('POST', '/feedback/similar', { visitor: visitorId(), player_id: playerId, other_id: otherId, kind, variant, rank, similarity, good });
      onVote(key, { good });
    } catch { onVote(key, 'error'); }
  };
  const chosen = typeof verdict === 'object' ? verdict.good : null;
  return (
    <div className="feedback-line" role="group" aria-label={`Is ${otherName} a good match?`}>
      <span>Is {otherName} a good match?</span>
      <button type="button" className="chip" aria-pressed={chosen === true} disabled={verdict === 'sending'} onClick={() => void vote(true)}>Yes</button>
      <button type="button" className="chip" aria-pressed={chosen === false} disabled={verdict === 'sending'} onClick={() => void vote(false)}>No</button>
      {chosen !== null && <small>Saved, thanks.</small>}
      {verdict === 'error' && <small className="bad">Not saved.</small>}
    </div>
  );
}
