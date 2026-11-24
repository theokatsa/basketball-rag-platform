import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { LoadError, Loading, PageHead } from '../components/Common';
import { PlayerPicker } from '../components/PlayerPicker';
import { formatStat, playsPosition, POSITIONS, statByKey, STATS } from '../stats';
import { usePersisted } from '../usePersisted';

const W = 1000, H = 560, L = 64, B = 54, T = 20, R = 24;
const PRESETS: [string, string, string][] = [['Scoring vs efficiency', 'points', 'ts'], ['Playmaking vs turnovers', 'assists', 'turnovers'], ['Rebounds vs blocks', 'rebounds', 'blocks'], ['Age vs production', 'age', 'production']];
const COLORS: Record<string, string> = { Guard: '#ff6a13', Forward: '#ffc247', Center: '#6fa8f5' };
const mainPosition = (position: string | null) => (position ?? '').split('-')[0];

/** Labels near the right edge sit to the left of their dot. */
const flips = (cx: number) => cx > W - 190;

/** About eight round tick values across the range. */
function ticks(min: number, max: number): number[] {
  const raw = (max - min || 1) / 8;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * power).find((s) => s >= raw) ?? raw;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Number(v.toFixed(6)));
  return out;
}

export function Explorer() {
  const { players, totals, loading, error, open } = useApp();
  const [xKey, setX] = usePersisted('ex-x', 'points');
  const [yKey, setY] = usePersisted('ex-y', 'ts');
  const [position, setPosition] = usePersisted('ex-pos', '');
  const [minMinutes, setMinMinutes] = usePersisted('ex-min', 20);
  const [found, setFound] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const x = statByKey(xKey), y = statByKey(yKey);
  const view = useMemo(() => {
    const dots = players.flatMap((p) => {
      const t = totals[p.player_id];
      if ((p.games_played ?? 0) < 20 || (p.minutes ?? 0) < minMinutes || !playsPosition(p, position)) return [];
      if (t && [x, y].some((s) => s.attempts && s.attempts[0](t) < s.attempts[1])) return [];
      const xv = x.get(p, t), yv = y.get(p, t);
      return xv == null || yv == null ? [] : [{ p, xv, yv }];
    });
    if (!dots.length) return null;
    const range = (vs: number[]) => { const lo = Math.min(...vs), hi = Math.max(...vs), pad = (hi - lo || 1) * 0.05; return [lo - pad, hi + pad] as const; };
    const [x0, x1] = range(dots.map((d) => d.xv)), [y0, y1] = range(dots.map((d) => d.yv));
    const px = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
    const py = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - B - T);
    const mean = (vs: number[]) => vs.reduce((s, v) => s + v, 0) / vs.length;
    const mx = mean(dots.map((d) => d.xv)), my = mean(dots.map((d) => d.yv));
    const distance = (d: (typeof dots)[number]) => Math.hypot((d.xv - mx) / (x1 - x0), (d.yv - my) / (y1 - y0));
    // Label the players furthest from average, skipping labels that would collide.
    const labelBox = (d: (typeof dots)[number]) => { const cx = px(d.xv), width = d.p.full_name.length * 7.5 + 12; return flips(cx) ? { left: cx - width, right: cx + 8, y: py(d.yv) } : { left: cx - 8, right: cx + width, y: py(d.yv) }; };
    const boxes: ReturnType<typeof labelBox>[] = [];
    const labelled: typeof dots = [];
    for (const d of [...dots].sort((a, b) => distance(b) - distance(a))) {
      if (labelled.length >= 14) break;
      const box = labelBox(d);
      if (boxes.every((o) => box.right < o.left || box.left > o.right || Math.abs(box.y - o.y) > 17)) { labelled.push(d); boxes.push(box); }
    }
    return { dots, px, py, mx, my, xt: ticks(x0, x1), yt: ticks(y0, y1), labelled: new Set(labelled.map((d) => d.p.player_id)) };
  }, [players, totals, x, y, position, minMinutes]);
  if (error) return <LoadError message={error} />;
  const tip = view?.dots.find((d) => d.p.player_id === (hover ?? found));
  const statOptions = STATS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>);
  return (
    <>
      <PageHead title="Stat Explorer" intro="Every dot is a player. Click one to open the profile." />
      <div className="filter-bar"><div className="preset-row">{PRESETS.map(([name, a, b]) => <button type="button" className="chip" aria-pressed={xKey === a && yKey === b} key={name} onClick={() => { setX(a); setY(b); }}>{name}</button>)}</div></div>
      <section className="panel">
        <div className="filter-bar explorer-bar">
          <label>Across<select className="control-input" value={xKey} onChange={(e) => setX(e.target.value)}>{statOptions}</select></label>
          <label>Up<select className="control-input" value={yKey} onChange={(e) => setY(e.target.value)}>{statOptions}</select></label>
          <label>Position<select className="control-input" value={position} onChange={(e) => setPosition(e.target.value)}><option value="">All</option>{POSITIONS.map((p) => <option key={p} value={p}>{p}s</option>)}</select></label>
          <label className="inline-range">At least {minMinutes} minutes<input type="range" min={0} max={36} value={minMinutes} onChange={(e) => setMinMinutes(Number(e.target.value))} /></label>
          <PlayerPicker label="Highlight a player" placeholder="Highlight a player" onPick={setFound} />
        </div>
        {loading ? <Loading /> : !view ? <p className="status">No players match.</p> : (
          <>
            <div className="scatter-scroll">
              <svg viewBox={`0 0 ${W} ${H}`} className="scatter" role="img" aria-label={`${y.label} against ${x.label} for ${view.dots.length} players`}>
                {view.xt.map((v) => <g key={v}><line x1={view.px(v)} x2={view.px(v)} y1={T} y2={H - B} className="grid" /><text x={view.px(v)} y={H - B + 20} textAnchor="middle">{v}</text></g>)}
                {view.yt.map((v) => <g key={v}><line x1={L} x2={W - R} y1={view.py(v)} y2={view.py(v)} className="grid" /><text x={L - 10} y={view.py(v) + 4} textAnchor="end">{v}</text></g>)}
                <line x1={view.px(view.mx)} x2={view.px(view.mx)} y1={T} y2={H - B} className="mean" />
                <line x1={L} x2={W - R} y1={view.py(view.my)} y2={view.py(view.my)} className="mean" />
                <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" className="axis">{x.label}</text>
                <text transform={`translate(16 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" className="axis">{y.label}</text>
                {view.dots.map(({ p, xv, yv }) => <circle key={p.player_id} cx={view.px(xv)} cy={view.py(yv)} r={found === p.player_id ? 9 : 5.5} fill={COLORS[mainPosition(p.position)] ?? '#aaa'} className={`dot ${found != null && found !== p.player_id ? 'faded' : ''}`} onMouseEnter={() => setHover(p.player_id)} onMouseLeave={() => setHover(null)} onClick={() => open(p.player_id)}><title>{p.full_name}</title></circle>)}
                {view.dots.filter((d) => view.labelled.has(d.p.player_id) || d.p.player_id === found).map(({ p, xv, yv }) => { const right = flips(view.px(xv)); return <text key={p.player_id} x={view.px(xv) + (right ? -10 : 10)} y={view.py(yv) + 4} textAnchor={right ? 'end' : 'start'} className="dot-label">{p.full_name}</text>; })}
              </svg>
            </div>
            <div className="scatter-foot">
              <span className="scatter-legend">{Object.entries(COLORS).map(([name, color]) => <span key={name}><i style={{ background: color }} />{name}s</span>)}<span>Dashed lines are the average</span></span>
              <span aria-live="polite">{tip ? <><b>{tip.p.full_name}</b> {formatStat(x, tip.xv)} {x.short}, {formatStat(y, tip.yv)} {y.short}</> : `${view.dots.length} players`} {found != null && <button type="button" className="link-button" onClick={() => setFound(null)}>Clear highlight</button>}</span>
            </div>
          </>
        )}
      </section>
    </>
  );
}
