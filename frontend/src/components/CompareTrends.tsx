import { useEffect, useMemo, useState } from 'react';
import type { GameLog, PlayerDirectoryRow } from '../types';
import { usePersisted } from '../usePersisted';
import { smoothPath, useWidth } from '../useWidth';
import { formatDate } from '../utils';
import { Loading, Segmented } from './Common';
import { Dropdown } from './Dropdown';
import { LOG_STATS, logStat } from './logStats';

export type Entry = { id: number; p: PlayerDirectoryRow; color: string };
export type Logs = Record<number, GameLog[]>;

/** Game logs of every compared player, newest first; null while loading. */
export function useLogs(entries: Entry[]): Logs | null {
  const ids = entries.map((e) => e.id).join(',');
  const [state, setState] = useState<{ ids: string; logs: Logs } | null>(null);
  useEffect(() => {
    if (!ids) return;
    let cancelled = false;
    void Promise.all(ids.split(',').map(async (id) => {
      try { const r = await fetch(`/api/players/${id}/game-logs`); return [Number(id), r.ok ? ((await r.json()) as GameLog[]) : []] as const; } catch { return [Number(id), []] as const; }
    })).then((list) => { if (!cancelled) setState({ ids, logs: Object.fromEntries(list) }); });
    return () => { cancelled = true; };
  }, [ids]);
  return state?.ids === ids ? state.logs : null;
}

type Period = 'season' | 'before' | 'after' | '30' | '20' | '10' | 'custom';
type Step = 'game' | 'week' | 'month';
/** The 2025 All-Star break: no games from February 14 to 18. */
const BREAK = '2025-02-16';
const PERIODS: { value: Period; label: string }[] = [{ value: 'season', label: 'Whole season' }, { value: 'before', label: 'Before the All-Star break' }, { value: 'after', label: 'After the All-Star break' }, { value: '30', label: 'Last 30 games' }, { value: '20', label: 'Last 20 games' }, { value: '10', label: 'Last 10 games' }, { value: 'custom', label: 'Choose months' }];
const monthName = (m: string, long = false) => new Date(`${m}-01T00:00:00`).toLocaleDateString('en-US', long ? { month: 'long', year: 'numeric' } : { month: 'short' });
/** Monday of the week a date falls in. */
const weekOf = (date: string) => { const d = new Date(`${date}T00:00:00Z`); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7)); return d.toISOString().slice(0, 10); };
const TABLE = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'ts', 'three', 'minutes', 'plus_minus', 'game_score'];

export function CompareTrends({ entries, logs }: { entries: Entry[]; logs: Logs | null }) {
  const [key, setKey] = usePersisted('cmp-trend', 'points');
  const [period, setPeriod] = usePersisted<Period>('cmp-period', 'season');
  const [step, setStep] = usePersisted<Step>('cmp-step', 'month');
  const [from, setFrom] = usePersisted('cmp-from', '2024-10');
  const [to, setTo] = usePersisted('cmp-to', '2025-04');
  const [place, setPlace] = usePersisted<'all' | 'home' | 'away'>('cmp-place', 'all');
  const [hover, setHover] = useState<number | null>(null);
  const [stage, W] = useWidth<HTMLDivElement>();
  const stat = logStat(key);
  const months = useMemo(() => [...new Set(Object.values(logs ?? {}).flat().map((l) => (l.game_date ?? '').slice(0, 7)))].filter(Boolean).sort(), [logs]);
  /** Oldest first, inside the chosen period. */
  const picked = useMemo(() => new Map(entries.map((e) => {
    const all = (logs?.[e.id] ?? []).filter((l) => l.game_date && (place === 'all' || l.is_home === (place === 'home')));
    const list = period === 'before' ? all.filter((l) => l.game_date! < BREAK) : period === 'after' ? all.filter((l) => l.game_date! > BREAK) : period === 'custom' ? all.filter((l) => l.game_date!.slice(0, 7) >= from && l.game_date!.slice(0, 7) <= to) : period === 'season' ? all : all.slice(0, Number(period));
    return [e.id, [...list].reverse()] as const;
  })), [entries, logs, period, from, to, place]);
  if (!logs) return <Loading height="26rem" />;

  const bucket = (l: GameLog) => (step === 'week' ? weekOf(l.game_date!) : l.game_date!.slice(0, 7));
  const least = step === 'month' ? 3 : 1;
  const longest = Math.max(0, ...[...picked.values()].map((l) => l.length));
  const slots = step === 'game' ? Array.from({ length: longest }, (_, i) => String(i + 1)) : [...new Set([...picked.values()].flat().map(bucket))].sort();
  const series = entries.map((e) => {
    const games = picked.get(e.id) ?? [];
    const points = step === 'game'
      // Game by game each point is the average of the last five, or single games are all noise.
      ? slots.map((_, i) => (i < games.length && i >= Math.min(4, games.length - 1) ? stat.average(games.slice(Math.max(0, i - 4), i + 1)) : null))
      : slots.map((slot) => { const inside = games.filter((l) => bucket(l) === slot); return inside.length >= least ? stat.average(inside) : null; });
    return { e, games, points };
  });
  const values = series.flatMap((s) => s.points).filter((v): v is number => v != null);
  const H = 320, L = 48, R = 24, T = 18, B = 34;
  const low = Math.min(...values), high = Math.max(...values), pad = (high - low || 1) * 0.14;
  const lo = values.length ? (low >= 0 ? Math.max(0, low - pad) : low - pad) : 0, hi = values.length ? high + pad : 1;
  const x = (i: number) => L + (slots.length > 1 ? (i / (slots.length - 1)) * (W - L - R) : (W - L - R) / 2);
  const y = (v: number) => T + ((hi - v) / (hi - lo || 1)) * (H - T - B);
  const raw = (hi - lo || 1) / 4, power = 10 ** Math.floor(Math.log10(raw)), size = [1, 2, 5, 10].map((m) => m * power).find((v) => v >= raw) ?? raw;
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / size) * size; v <= hi; v += size) ticks.push(Number(v.toFixed(4)));
  const slotName = (slot: string) => (step === 'month' ? monthName(slot) : step === 'week' ? formatDate(slot).replace(/, \d{4}$/, '') : slot);
  const every = Math.max(1, Math.ceil(slots.length / Math.max(2, Math.floor(W / 90))));
  const tipName = (slot: string, i: number) => (step === 'month' ? monthName(slot, true) : step === 'week' ? `Week of ${formatDate(slot)}` : `Game ${i + 1}, average of 5`);
  const bestOf = (k: string) => { const s = logStat(k), list = series.map(({ games }) => s.average(games)).filter((v): v is number => v != null); return list.length > 1 ? (k === 'turnovers' ? Math.min(...list) : Math.max(...list)) : null; };
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Over time</h2><p>Pick a period and how to group it. Everything below follows.</p></div></div>
      <div className="filter-bar">
        <Dropdown label="Period" value={period} options={PERIODS} onChange={(v) => { setPeriod(v as Period); setHover(null); }} />
        {period === 'custom' && <><Dropdown label="From" value={from} options={months.map((m) => ({ value: m, label: `From ${monthName(m, true)}` }))} onChange={(m) => { setFrom(m); if (m > to) setTo(m); }} /><Dropdown label="To" value={to} options={months.map((m) => ({ value: m, label: `To ${monthName(m, true)}` }))} onChange={(m) => { setTo(m); if (m < from) setFrom(m); }} /></>}
        <Segmented label="Group by" value={step} options={[['game', 'Game by game'], ['week', 'By week'], ['month', 'By month']]} onChange={(v) => { setStep(v); setHover(null); }} />
        <Segmented label="Place" value={place} options={[['all', 'All games'], ['home', 'Home'], ['away', 'Away']]} onChange={setPlace} />
      </div>
      <div className="stat-tabs wrap" role="group" aria-label="Statistic">{LOG_STATS.map((s) => <button type="button" key={s.key} aria-pressed={s.key === key} onClick={() => setKey(s.key)}>{s.label}</button>)}</div>
      <div className="scatter-legend trend-legend">{series.map(({ e, games }) => { const v = stat.average(games); return <span key={e.id}><i style={{ background: e.color }} />{e.p.full_name} <b>{v == null ? '–' : stat.text(v)}</b> <small>{games.length} games</small></span>; })}</div>
      <div className="line-stage" ref={stage}>
        {values.length < 2 ? <p className="status">Not enough games in this period. Try a wider one{step === 'month' ? ' or a finer grouping' : ''}.</p> : (
          <>
            <svg width={W} height={H} className="line-chart" role="img" aria-label={`${stat.label} over time`} onMouseLeave={() => setHover(null)} onMouseMove={(ev) => { const at = ev.clientX - ev.currentTarget.getBoundingClientRect().left; setHover(Math.max(0, Math.min(slots.length - 1, Math.round(((at - L) / (W - L - R)) * (slots.length - 1))))); }}>
              {ticks.map((v) => <g key={v}><line x1={L} x2={W - R} y1={y(v)} y2={y(v)} className="grid" /><text x={L - 8} y={y(v) + 4} textAnchor="end">{v}{stat.suffix ?? ''}</text></g>)}
              {slots.map((slot, i) => (i % every === 0 || i === slots.length - 1) && (i === slots.length - 1 || slots.length - 1 - i >= every * 0.6) && <text key={slot} x={x(i)} y={H - 10} textAnchor="middle">{slotName(slot)}</text>)}
              {hover != null && <line x1={x(hover)} x2={x(hover)} y1={T} y2={H - B} className="mean" />}
              {series.map(({ e, points }) => {
                const line = points.flatMap((v, i) => (v == null ? [] : [[x(i), y(v)] as const]));
                return <g key={e.id}><path d={smoothPath(line)} fill="none" stroke="#141416" strokeWidth={7} strokeOpacity={0.7} /><path d={smoothPath(line)} fill="none" stroke={e.color} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />{step !== 'game' && line.map(([cx, cy]) => <circle key={cx} cx={cx} cy={cy} r={slots.length > 14 ? 3.5 : 4.5} fill={e.color} stroke="#141416" strokeWidth={2} />)}</g>;
              })}
              {hover != null && series.map(({ e, points }) => points[hover] != null && <circle key={e.id} cx={x(hover)} cy={y(points[hover])} r={6.5} fill={e.color} stroke="#fff" strokeWidth={2} />)}
            </svg>
            {hover != null && <div className={`scatter-tip ${hover > slots.length / 2 ? 'flip' : ''}`} style={{ left: x(hover), top: '10%' }}><b>{tipName(slots[hover], hover)}</b>{series.map(({ e, games, points }) => <span key={e.id}><i style={{ background: e.color }} />{e.p.full_name} {points[hover] == null ? '–' : stat.text(points[hover])}{step !== 'game' && points[hover] != null ? `, ${games.filter((l) => bucket(l) === slots[hover]).length} games` : ''}</span>)}</div>}
          </>
        )}
      </div>
      {step === 'month' && <p className="radar-note">A month needs at least 3 games to show.</p>}
      <h3 className="sub-head second">Averages in this period</h3>
      <div className="detail-records-scroll open">
        <table className="detail-records-table period-table">
          <thead><tr><th scope="col">Player</th><th scope="col">Games</th><th scope="col">W–L</th>{TABLE.map((k) => <th scope="col" key={k}>{logStat(k).label}</th>)}</tr></thead>
          <tbody>{series.map(({ e, games }) => <tr key={e.id}><th scope="row"><span className="cmp-court-name"><i style={{ background: e.color }} />{e.p.full_name}</span></th><td>{games.length}</td><td>{games.filter((l) => l.won).length}–{games.filter((l) => !l.won).length}</td>{TABLE.map((k) => { const s = logStat(k), v = s.average(games), best = bestOf(k); return <td key={k} className={v != null && best != null && v === best ? 'best' : ''}>{v == null ? '–' : s.text(v)}</td>; })}</tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}
