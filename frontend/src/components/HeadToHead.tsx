import { useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import { useApp } from '../AppContext';
import { teamVars } from '../teamColors';
import type { GameLog, HeadToHead as Duel } from '../types';
import { formatDate } from '../utils';
import { Avatar } from './Avatar';
import { Loading, TeamLogo } from './Common';
import type { Entry, Logs } from './CompareTrends';
import { logStat } from './logStats';

const AVERAGES = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'ts', 'minutes', 'game_score'];
/** Possessions at the scorer's own rate mixed in, the same as on the server. */
const PRIOR = 60;
const pct = (made: number, att: number) => (att ? `${((made / att) * 100).toFixed(0)}%` : '–');
const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
const gameScore = (l: GameLog) => logStat('game_score').value(l) ?? 0;

type Meeting = { id: string; date: string; a: GameLog; b: GameLog };
/** Games both played on opposite teams. Ids say which team each was on that night. */
function meetingsOf(a: GameLog[], b: GameLog[]): Meeting[] {
  const other = new Map(b.map((l) => [l.nba_game_id, l]));
  return a.flatMap((l) => { const m = other.get(l.nba_game_id); return m && l.nba_game_id && m.opponent_id !== l.opponent_id ? [{ id: l.nba_game_id, date: l.game_date ?? '', a: l, b: m }] : []; });
}

/** One direction of the matchup: what the scorer did while this defender guarded them. */
function Guarding({ scorer, defender, duel }: { scorer: Entry; defender: Entry; duel?: Duel }) {
  if (!duel || duel.possessions < 1) return <div className="guard none"><h4>{scorer.p.full_name} against {defender.p.full_name}</h4><p className="status">Not tracked against each other for at least 5 possessions.</p></div>;
  const per100 = (duel.points / duel.possessions) * 100;
  const edge = ((duel.points + (PRIOR * duel.usual) / 100) / (duel.possessions + PRIOR)) * 100 - duel.usual;
  const scale = Math.max(per100, duel.usual, 1) * 1.1;
  const verdict = duel.possessions < 25 ? 'Too few possessions to judge' : edge > 2 ? `${scorer.p.full_name.split(' ').slice(-1)} scores more than usual` : edge < -2 ? `${defender.p.full_name.split(' ').slice(-1)} holds them below their average` : 'Close to the usual level';
  const facts: [string, string][] = [['Field goals', `${duel.fgm}/${duel.fga}, ${pct(duel.fgm, duel.fga)}`], ['Threes', `${duel.tpm}/${duel.tpa}`], ['Free throws', `${duel.ftm}/${duel.fta}`], ['Points', duel.points.toFixed(0)], ['Assists', duel.ast.toFixed(0)], ['Turnovers forced', duel.tov.toFixed(0)], ['Shots blocked', duel.blk.toFixed(0)], ['Time guarded', `${clock(duel.seconds)} in ${duel.games} ${duel.games === 1 ? 'game' : 'games'}`]];
  return (
    <div className="guard" style={{ '--side': scorer.color } as CSSProperties}>
      <h4>{scorer.p.full_name} against {defender.p.full_name}</h4>
      <div className="guard-main"><strong>{per100.toFixed(0)}</strong><span>points per 100 possessions<small>{duel.possessions.toFixed(0)} possessions tracked</small></span></div>
      <div className="guard-bars"><span>Here</span><i><em style={{ width: `${(per100 / scale) * 100}%` }} /></i><b>{per100.toFixed(0)}</b><span>Usually</span><i className="usual"><em style={{ width: `${(duel.usual / scale) * 100}%` }} /></i><b>{duel.usual.toFixed(0)}</b></div>
      <p className={`guard-verdict ${duel.possessions < 25 ? '' : edge > 2 ? 'up' : edge < -2 ? 'down' : ''}`}>{verdict}</p>
      <dl>{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </div>
  );
}

export function HeadToHead({ entries, logs, duels }: { entries: Entry[]; logs: Logs | null; duels: Duel[] | null }) {
  const { openGame } = useApp();
  const pairs = useMemo(() => entries.flatMap((a, i) => entries.slice(i + 1).map((b) => [a, b] as const)), [entries]);
  const [chosen, setChosen] = useState(0);
  const [a, b] = pairs[Math.min(chosen, pairs.length - 1)];
  const meetings = useMemo(() => (logs ? meetingsOf(logs[a.id] ?? [], logs[b.id] ?? []) : []), [logs, a.id, b.id]);
  const duel = (off: number, def: number) => duels?.find((d) => d.off_player_id === off && d.def_player_id === def);
  if (!logs || !duels) return <section className="panel"><Loading height="20rem" /></section>;
  const wins = [meetings.filter((m) => m.a.won).length, meetings.filter((m) => m.b.won).length];
  const better = [meetings.filter((m) => gameScore(m.a) > gameScore(m.b)).length, meetings.filter((m) => gameScore(m.b) > gameScore(m.a)).length];
  const face = (e: Entry, i: number) => (
    <div className={`duel-face ${i ? 'right' : ''}`} style={{ ...teamVars(e.p.club_team_id), '--side': e.color } as CSSProperties}>
      <span className="duel-logo"><TeamLogo teamId={e.p.club_team_id} size={170} /></span>
      <Avatar key={e.p.nba_player_id} name={e.p.full_name} nbaPlayerId={e.p.nba_player_id} className="podium-photo" />
      <span className="duel-name"><b>{e.p.full_name}</b><small>{e.p.club_full_name}</small></span>
    </div>
  );
  return (
    <section className="panel duel">
      <div className="panel-header"><div><h2>Head to head</h2><p>Games against each other in 2024-25, and what happens when one guards the other</p></div></div>
      {pairs.length > 1 && <div className="duel-pairs" role="group" aria-label="Pair of players">{pairs.map(([x, y], i) => <button type="button" key={`${x.id}-${y.id}`} aria-pressed={x.id === a.id && y.id === b.id} onClick={() => setChosen(i)}><i style={{ background: x.color }} />{x.p.full_name}<em>vs</em><i style={{ background: y.color }} />{y.p.full_name}</button>)}</div>}
      <div className="duel-hero">
        {face(a, 0)}
        <div className="duel-score">{meetings.length ? <><p><strong>{wins[0]}</strong><span>–</span><strong>{wins[1]}</strong></p><small>wins in {meetings.length} {meetings.length === 1 ? 'meeting' : 'meetings'}</small><small>Better Game Score: {better[0]}–{better[1]}</small></> : <small>{a.p.club_team_id === b.p.club_team_id ? 'Teammates: no games against each other' : 'No games against each other this season'}</small>}</div>
        {face(b, 1)}
      </div>
      {meetings.length > 0 && (
        <div className="duel-cols">
          <div>
            <h3 className="sub-head">Averages when they meet</h3>
            <div className="duel-averages">
              {AVERAGES.map((key) => {
                const s = logStat(key), va = s.average(meetings.map((m) => m.a)), vb = s.average(meetings.map((m) => m.b));
                const usual = [s.average(logs[a.id] ?? []), s.average(logs[b.id] ?? [])];
                const max = Math.max(Math.abs(va ?? 0), Math.abs(vb ?? 0), 0.001);
                const lead = va == null || vb == null || va === vb || key === 'minutes' ? -1 : (va > vb) !== (key === 'turnovers') ? 0 : 1;
                const side = (v: number | null, i: number) => <span className={lead === i ? 'better' : ''}>{v == null ? '–' : s.text(v)}<small>{usual[i] == null ? '' : `season ${s.text(usual[i])}`}</small></span>;
                return <div key={key}>{side(va, 0)}<i className="left"><em style={{ width: `${(Math.abs(va ?? 0) / max) * 100}%`, background: a.color }} /></i><b>{s.label}</b><i><em style={{ width: `${(Math.abs(vb ?? 0) / max) * 100}%`, background: b.color }} /></i>{side(vb, 1)}</div>;
              })}
            </div>
          </div>
          <div>
            <h3 className="sub-head">Every meeting</h3>
            <ul className="duel-games">
              {meetings.map((m) => <li key={m.id}><button type="button" onClick={() => openGame(m.id)}><span className="duel-date">{formatDate(m.date)}<small>{m.a.won ? a.p.full_name.split(' ').slice(-1) : b.p.full_name.split(' ').slice(-1)} won {Math.max(m.a.team_points, m.a.opponent_points)}–{Math.min(m.a.team_points, m.a.opponent_points)}</small></span>{[m.a, m.b].map((l, i) => { const top = gameScore(l) > gameScore(i ? m.a : m.b); return <span key={i} className={`duel-line ${top ? 'better' : ''}`} style={{ '--side': i ? b.color : a.color } as CSSProperties}><b>{l.points}</b> pts <b>{l.rebounds}</b> reb <b>{l.assists}</b> ast<small>{l.field_goals_made}/{l.field_goals_attempted} FG, Game Score {gameScore(l).toFixed(1)}</small></span>; })}</button></li>)}
            </ul>
          </div>
        </div>
      )}
      <h3 className="sub-head second">When they guard each other</h3>
      <div className="guard-cols"><Guarding scorer={a} defender={b} duel={duel(a.id, b.id)} /><Guarding scorer={b} defender={a} duel={duel(b.id, a.id)} /></div>
      <p className="radar-note">Guarding data is the NBA’s matchup tracking: the time one defender was the main one on a scorer. The verdict mixes in {PRIOR} possessions at the scorer’s usual rate, so a short hot streak does not decide it.</p>
    </section>
  );
}
