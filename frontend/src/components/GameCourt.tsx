import { useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import { colorVars } from '../teamColors';
import type { TeamColor } from '../teamColors';
import type { GameDetail, GameShot, TeamBox } from '../types';
import { teamLogo } from '../utils';
import { Avatar } from './Avatar';
import { Segmented, TeamLogo } from './Common';
import { zoneOf } from './CourtZones';
import { Dropdown } from './Dropdown';

const W = 940, H = 500;
const isThree = (s: GameShot) => s.shot_type.startsWith('3');
const pct = (made: number, att: number) => (att ? `${((made / att) * 100).toFixed(0)}%` : '–');

const AREAS: [string, (zone: string) => boolean][] = [
  ['At the rim', (z) => z === 'rim'], ['Rest of the paint', (z) => z.startsWith('lane')],
  ['Mid-range', (z) => ['ft', 'key'].includes(z) || z.startsWith('base') || z.startsWith('midw')],
  ['Corner threes', (z) => z.startsWith('corner')], ['Other threes', (z) => ['top', 'deep'].includes(z) || z.startsWith('wing') || z.startsWith('slot')],
];

/** Half of a full court. The away team attacks the left basket, the home team the right one. */
function HalfLines({ flip, color }: { flip?: boolean; color: TeamColor }) {
  return (
    <g transform={flip ? `translate(${W} 0) scale(-1 1)` : undefined}>
      <rect x={0} y={170} width={190} height={160} fill={color.fill} fillOpacity={color.edge === color.fill ? 0.4 : 0.85} />
      <g className="court-lines" fill="none">
        <rect x={0} y={170} width={190} height={160} /><rect x={0} y={190} width={190} height={120} className="thin" />
        <path d="M190 190A60 60 0 0 1 190 310" /><path d="M190 190A60 60 0 0 0 190 310" strokeDasharray="7 7" className="thin" />
        <path d="M0 30H141.5A237.5 237.5 0 0 1 141.5 470H0" /><path d="M44 210H52A40 40 0 0 1 52 290H44" />
        <line x1={43} x2={43} y1={220} y2={280} strokeWidth={3} /><circle cx={52} cy={250} r={7.5} className="court-hoop" />
      </g>
    </g>
  );
}

type Props = { game: GameDetail; away: TeamBox; home: TeamBox; colors: [TeamColor, TeamColor] };

export function GameCourt({ game, away, home, colors }: Props) {
  const [shooter, setShooter] = useState('');
  const [result, setResult] = useState<'all' | 'made' | 'missed'>('all');
  const [period, setPeriod] = useState('0');
  const [tip, setTip] = useState<{ index: number; x: number; y: number; width: number } | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const people = useMemo(() => new Map(game.players.map((p) => [p.player_id, p])), [game.players]);
  const periods = [...new Set(game.shots.map((s) => s.period))].sort((a, b) => a - b);
  const name = (p: number) => (p > 4 ? (p === 5 ? 'OT' : `OT${p - 4}`) : `Q${p}`);
  const picked = useMemo(() => game.shots.filter((s) => s.loc_y <= 418 && (!shooter || (shooter.startsWith('t') ? s.nba_team_id === Number(shooter.slice(1)) : s.player_id === Number(shooter))) && (period === '0' || s.period === Number(period))), [game.shots, shooter, period]);
  // Misses first, so makes are drawn on top.
  const shots = useMemo(() => picked.filter((s) => result === 'all' || s.shot_made === (result === 'made')).sort((a, b) => Number(a.shot_made) - Number(b.shot_made)), [picked, result]);
  const place = (s: GameShot) => (s.nba_team_id === home.nba_team_id ? [W - s.loc_y - 52, 250 + s.loc_x] : [s.loc_y + 52, 250 - s.loc_x]);
  const totals = [away, home].map((t) => {
    const own = picked.filter((s) => s.nba_team_id === t.nba_team_id);
    const of = (list: GameShot[]) => ({ made: list.filter((s) => s.shot_made).length, att: list.length });
    return { all: of(own), points: own.reduce((sum, s) => sum + (s.shot_made ? (isThree(s) ? 3 : 2) : 0), 0), areas: AREAS.map(([, test]) => of(own.filter((s) => test(zoneOf(s.loc_x, s.loc_y, isThree(s)))))) };
  });
  const most = Math.max(1, ...totals.flatMap((t) => t.areas.map((a) => a.att)));
  const reset = () => setTip(null);
  const onMove = (e: MouseEvent) => {
    const index = (e.target as Element).closest('[data-i]')?.getAttribute('data-i');
    const box = stage.current?.getBoundingClientRect();
    if (index == null || !box) { if (tip) reset(); return; }
    setTip({ index: Number(index), x: e.clientX - box.left, y: e.clientY - box.top, width: box.width });
  };
  const over = tip ? shots[tip.index] : undefined, person = over && people.get(over.player_id);
  const bar = (side: 0 | 1, k: number) => {
    const { att, made } = totals[side].areas[k];
    return <i className={side ? '' : 'left'} style={colorVars(colors[side])}><em className="att" style={{ width: `${(att / most) * 100}%` }} /><em className="made" style={{ width: `${(made / most) * 100}%` }} /></i>;
  };
  const figure = (side: 0 | 1, k: number) => { const { att, made } = totals[side].areas[k]; return <span><b>{pct(made, att)}</b><small>{made}/{att}</small></span>; };
  return (
    <section className="panel game-shots">
      <div className="panel-header"><div><h2>Shot map</h2><p>{away.full_name} shoot at the left basket, {home.full_name} at the right</p></div></div>
      <div className="filter-bar">
        <Dropdown label="Whose shots" value={shooter} onChange={(v) => { setShooter(v); reset(); }} search="Search players" options={[{ value: '', label: 'Both teams' }, ...[away, home].map((t) => ({ value: `t${t.nba_team_id}`, label: t.full_name, icon: <TeamLogo teamId={t.nba_team_id} size={22} /> })), ...[away, home].flatMap((t) => game.players.filter((p) => p.fga > 0 && p.nba_team_id === t.nba_team_id).map((p) => ({ value: String(p.player_id), label: p.full_name, note: `${p.fgm}/${p.fga}`, group: t.full_name })))]} />
        <Segmented label="Period" value={period} options={[['0', 'Whole game'], ...periods.map((p) => [String(p), name(p)] as [string, string])]} onChange={(v) => { setPeriod(v); reset(); }} />
        <Segmented label="Result" value={result} options={[['all', 'All'], ['made', 'Made'], ['missed', 'Missed']]} onChange={(v) => { setResult(v); reset(); }} />
      </div>
      <div className="scatter-scroll">
        <div className="full-court" ref={stage} onMouseMove={onMove} onMouseLeave={reset}>
          <svg viewBox={`-6 -6 ${W + 12} ${H + 12}`} role="img" aria-label={`${shots.length} shots, ${away.full_name} at ${home.full_name}`}>
            <defs>
              <pattern id="planks" width={W} height={50} patternUnits="userSpaceOnUse"><rect width={W} height={50} fill="#1a130d" /><rect width={W} height={25} fill="#1e160f" /><path d="M0 0H940M0 25H940" stroke="#0f0a06" strokeWidth={1} /></pattern>
              <linearGradient id="endl" x1="0" x2="1"><stop offset="0" stopColor={colors[0].glow} stopOpacity=".28" /><stop offset=".45" stopColor={colors[0].glow} stopOpacity="0" /></linearGradient>
              <linearGradient id="endr" x1="1" x2="0"><stop offset="0" stopColor={colors[1].glow} stopOpacity=".28" /><stop offset=".45" stopColor={colors[1].glow} stopOpacity="0" /></linearGradient>
            </defs>
            <rect width={W} height={H} fill="url(#planks)" /><rect width={W} height={H} fill="url(#endl)" /><rect width={W} height={H} fill="url(#endr)" />
            <image href={teamLogo(home.nba_team_id) ?? ''} x={W / 2 - 85} y={H / 2 - 85} width={170} height={170} opacity={0.3} />
            <HalfLines color={colors[0]} /><HalfLines color={colors[1]} flip />
            <g className="court-lines" fill="none"><rect width={W} height={H} /><line x1={W / 2} x2={W / 2} y1={0} y2={H} /><circle cx={W / 2} cy={H / 2} r={60} /></g>
            {shots.map((s, i) => {
              const [x, y] = place(s), color = colors[s.nba_team_id === home.nba_team_id ? 1 : 0];
              return <g key={i} data-i={i} transform={`translate(${x} ${y})`} className={`game-shot ${s.shot_made ? 'made' : 'missed'} ${tip?.index === i ? 'lit' : tip ? 'rest' : ''}`} style={colorVars(color)}><circle r={9} fill="transparent" />{s.shot_made ? <circle r={6} className="mark" /> : <path d="M-4.5 -4.5L4.5 4.5M4.5 -4.5L-4.5 4.5" className="mark" />}</g>;
            })}
          </svg>
          {over && person && tip && (
            <div className={`shot-tip game-tip ${tip.x > tip.width * 0.6 ? 'flip-x' : ''} ${tip.y > 180 ? 'flip-y' : ''}`} style={{ left: tip.x, top: tip.y }} role="tooltip">
              <div className="tip-player"><Avatar key={person.nba_player_id} name={person.full_name} nbaPlayerId={person.nba_player_id} className="player-thumb" /><span><b>{person.full_name}</b><small>{person.points} points, {person.fgm}/{person.fga} FG</small></span><span className={`shot-result ${over.shot_made ? 'made' : 'missed'}`}>{over.shot_made ? `+${isThree(over) ? 3 : 2}` : 'Missed'}</span></div>
              <dl><dt>Shot</dt><dd>{over.action_type}</dd><dt>Distance</dt><dd>{over.shot_distance} ft</dd><dt>Clock</dt><dd>{name(over.period)} {over.minutes_remaining}:{String(over.seconds_remaining).padStart(2, '0')}</dd></dl>
            </div>
          )}
        </div>
      </div>
      <div className="shot-legend"><span><i className="game-key made" />Made</span><span><i className="game-key miss" aria-hidden="true" />Missed</span><span>Hover a shot for details</span></div>
      <div className="area-table">
        {[away, home].map((t, i) => <div className={`area-team ${i ? 'right' : ''}`} key={t.nba_team_id}><TeamLogo teamId={t.nba_team_id} size={40} /><span><b>{totals[i].all.made}/{totals[i].all.att}, {pct(totals[i].all.made, totals[i].all.att)}</b><small>{totals[i].points} points from the field</small></span></div>)}
        {AREAS.map(([label], k) => <div className="area-row" key={label}>{figure(0, k)}{bar(0, k)}<strong>{label}</strong>{bar(1, k)}{figure(1, k)}</div>)}
      </div>
    </section>
  );
}
