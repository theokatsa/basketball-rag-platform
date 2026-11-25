import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { LoadError, Loading, PageHead, Segmented, TeamLogo } from '../components/Common';
import { StatSelect, TeamSelect } from '../components/Dropdown';
import { CloseIcon } from '../components/Icons';
import { PlayerPicker } from '../components/PlayerPicker';
import { formatStat, playsPosition, POSITIONS, qualifies, statByKey } from '../stats';
import type { StatDef } from '../stats';
import { colorVars, teamColor } from '../teamColors';
import type { PlayerDirectoryRow } from '../types';
import { usePersisted } from '../usePersisted';

const W = 1000, H = 600, L = 64, B = 56, T = 20, R = 24;
const PRESETS: [string, string, string][] = [['Scoring vs efficiency', 'points', 'ts'], ['Usage vs efficiency', 'usage', 'ts'], ['Playmaking vs turnovers', 'assists', 'turnovers'], ['Rebounds vs blocks', 'rebounds', 'blocks'], ['Offense vs defense', 'off_rating', 'def_rating'], ['Age vs production', 'age', 'production']];
const COLORS: Record<string, string> = { Guard: '#e8590c', Forward: '#9085e9', Center: '#199e70' };
const mainPosition = (position: string | null) => (position ?? '').split('-')[0];
const colorOf = (position: string | null) => COLORS[mainPosition(position)] ?? '#aaa';

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
  const { players, totals, byId, loading, error, open } = useApp();
  const [xKey, setX] = usePersisted('ex-x', 'points');
  const [yKey, setY] = usePersisted('ex-y', 'ts');
  const [position, setPosition] = usePersisted('ex-pos', '');
  const [club, setClub] = usePersisted('ex-club', '');
  const [minMinutes, setMinMinutes] = usePersisted('ex-min', 20);
  const [found, setFound] = usePersisted<number | null>('ex-found', null);
  const [hover, setHover] = useState<number | null>(null);
  const x = statByKey(xKey), y = statByKey(yKey);
  const view = useMemo(() => {
    const dots = players.flatMap((p) => {
      const t = totals[p.player_id];
      if (p.player_id !== found && ((p.games_played ?? 0) < 20 || (p.minutes ?? 0) < minMinutes || !playsPosition(p, position) || !qualifies(x, t) || !qualifies(y, t))) return [];
      const xv = x.get(p, t), yv = y.get(p, t);
      return xv == null || yv == null ? [] : [{ p, xv, yv }];
    });
    if (!dots.length) return null;
    const range = (vs: number[]) => { const lo = Math.min(...vs), hi = Math.max(...vs), pad = (hi - lo || 1) * 0.06; return [lo - pad, hi + pad] as const; };
    const [x0, x1] = range(dots.map((d) => d.xv)), [y0, y1] = range(dots.map((d) => d.yv));
    const px = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
    const py = (v: number) => H - B - ((v - y0) / (y1 - y0)) * (H - B - T);
    const mean = (vs: number[]) => vs.reduce((s, v) => s + v, 0) / vs.length;
    const mx = mean(dots.map((d) => d.xv)), my = mean(dots.map((d) => d.yv));
    const cov = dots.reduce((s, d) => s + (d.xv - mx) * (d.yv - my), 0);
    const r = cov / Math.sqrt(dots.reduce((s, d) => s + (d.xv - mx) ** 2, 0) * dots.reduce((s, d) => s + (d.yv - my) ** 2, 0) || 1);
    return { dots, px, py, mx, my, r, xt: ticks(x0, x1), yt: ticks(y0, y1) };
  }, [players, totals, x, y, position, minMinutes, found]);
  if (error) return <LoadError message={error} />;
  const tip = hover != null && hover !== found ? view?.dots.find((d) => d.p.player_id === hover) : undefined;
  const star = view?.dots.find((d) => d.p.player_id === found);
  const starPlayer = found != null ? byId.get(found) : undefined;
  const starTeam = starPlayer?.club_team_id ?? null;
  const focused = Boolean(club) || found != null;
  /** With a highlight on, only the highlighted team and player keep a colour: their team's. */
  const inFocus = (p: PlayerDirectoryRow) => (club ? p.club_full_name === club : p.club_team_id === starTeam);
  const size = (p: PlayerDirectoryRow) => 3.5 + (p.minutes ?? 0) / 10;
  const look = (p: PlayerDirectoryRow) => (!focused ? { fill: colorOf(p.position), className: 'dot' } : inFocus(p) ? { className: 'dot team' } : { className: 'dot out' });
  const ordered = view ? (focused ? [...view.dots].sort((a, b) => Number(inFocus(a.p)) - Number(inFocus(b.p))) : view.dots).filter((d) => d.p.player_id !== found) : [];
  const teamNames = [...new Map((view?.dots ?? []).filter((d) => focused && (inFocus(d.p) || d.p.player_id === found)).map((d) => [d.p.club_team_id, d.p])).values()];
  const rank = (value: number, s: StatDef, axis: 'xv' | 'yv') => 1 + view!.dots.filter((o) => (s.lowerIsBetter ? o[axis] < value : o[axis] > value)).length;
  return (
    <>
      <PageHead title="Stat Explorer" intro="Every dot is a player. Hover for details, click to open the profile." />
      <div className="filter-bar"><div className="preset-row">{PRESETS.map(([name, a, b]) => <button type="button" className="chip" aria-pressed={xKey === a && yKey === b} key={name} onClick={() => { setX(a); setY(b); }}>{name}</button>)}</div></div>
      <section className="panel explorer-panel">
        <div className="explorer-top">
          <div className="axis-pick"><StatSelect label="Up" showLabel value={yKey} onChange={setY} /><button type="button" className="swap-button" title="Swap the two axes" aria-label="Swap the two axes" onClick={() => { setX(yKey); setY(xKey); }}>⇄</button><StatSelect label="Across" showLabel value={xKey} onChange={setX} /></div>
          <div className="axis-pick"><TeamSelect value={club} onChange={setClub} all="Highlight a team" label="Highlight a team" />{starPlayer ? <button type="button" className="star-chip" onClick={() => setFound(null)} aria-label={`Stop highlighting ${starPlayer.full_name}`}><Avatar key={starPlayer.nba_player_id} name={starPlayer.full_name} nbaPlayerId={starPlayer.nba_player_id} className="player-thumb" />{starPlayer.full_name}<CloseIcon /></button> : <PlayerPicker label="Highlight a player" placeholder="Highlight a player" onPick={setFound} />}</div>
        </div>
        <div className="filter-bar">
          <Segmented label="Position" value={position} options={[['', 'All'], ...POSITIONS.map((p) => [p, `${p}s`] as [string, string])]} onChange={setPosition} />
          <label className="inline-range">At least {minMinutes} minutes<input type="range" min={0} max={36} value={minMinutes} onChange={(e) => setMinMinutes(Number(e.target.value))} /></label>
          {view && <span className="count-label">{view.dots.length} players, correlation {view.r.toFixed(2)}</span>}
        </div>
        {loading ? <Loading /> : !view ? <p className="status">No players match.</p> : (
          <>
            <div className="scatter-scroll">
              <div className="chart-stage">
                <svg viewBox={`0 0 ${W} ${H}`} className="scatter" role="img" aria-label={`${y.label} against ${x.label} for ${view.dots.length} players`}>
                  <rect x={x.lowerIsBetter ? L : view.px(view.mx)} y={y.lowerIsBetter ? view.py(view.my) : T} width={x.lowerIsBetter ? view.px(view.mx) - L : W - R - view.px(view.mx)} height={y.lowerIsBetter ? H - B - view.py(view.my) : view.py(view.my) - T} className="quad-best" />
                  {view.xt.map((v) => <g key={v}><line x1={view.px(v)} x2={view.px(v)} y1={T} y2={H - B} className="grid" /><text x={view.px(v)} y={H - B + 20} textAnchor="middle">{v}</text></g>)}
                  {view.yt.map((v) => <g key={v}><line x1={L} x2={W - R} y1={view.py(v)} y2={view.py(v)} className="grid" /><text x={L - 10} y={view.py(v) + 4} textAnchor="end">{v}</text></g>)}
                  <line x1={view.px(view.mx)} x2={view.px(view.mx)} y1={T} y2={H - B} className="mean" />
                  <line x1={L} x2={W - R} y1={view.py(view.my)} y2={view.py(view.my)} className="mean" />
                  <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" className="axis">{x.label}</text>
                  <text transform={`translate(16 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" className="axis">{y.label}</text>
                  {ordered.map(({ p, xv, yv }) => (
                    <g key={p.player_id} className="dot-group" style={colorVars(teamColor(p.club_team_id))} onMouseEnter={() => setHover(p.player_id)} onMouseLeave={() => setHover(null)} onClick={() => open(p.player_id)}>
                      <circle cx={view.px(xv)} cy={view.py(yv)} r={11} fill="transparent" /><circle cx={view.px(xv)} cy={view.py(yv)} r={size(p) + (focused && inFocus(p) ? 3 : 0)} {...look(p)} />
                    </g>
                  ))}
                  {tip && <circle cx={view.px(tip.xv)} cy={view.py(tip.yv)} r={size(tip.p) + 3} style={colorVars(teamColor(tip.p.club_team_id))} className="dot-top team" />}
                  {star && <g className="dot-star" style={colorVars(teamColor(star.p.club_team_id))} onClick={() => open(star.p.player_id)}><circle cx={view.px(star.xv)} cy={view.py(star.yv)} r={22} className="halo team" /><circle cx={view.px(star.xv)} cy={view.py(star.yv)} r={11.5} className="dot-top team" /><text x={Math.min(W - 110, Math.max(L + 100, view.px(star.xv)))} y={view.py(star.yv) < 70 ? view.py(star.yv) + 42 : view.py(star.yv) - 30} textAnchor="middle" className="dot-label">{star.p.full_name}</text></g>}
                </svg>
                {tip && (
                  <div className={`scatter-tip rich ${view.px(tip.xv) > W * 0.6 ? 'flip' : ''} ${view.py(tip.yv) > H * 0.6 ? 'up' : ''}`} style={{ left: `${(view.px(tip.xv) / W) * 100}%`, top: `${(view.py(tip.yv) / H) * 100}%` }} role="tooltip">
                    <div className="tip-player"><Avatar key={tip.p.nba_player_id} name={tip.p.full_name} nbaPlayerId={tip.p.nba_player_id} className="player-thumb" /><span><b>{tip.p.full_name}</b><small>{tip.p.club_full_name}, {tip.p.position}</small></span><TeamLogo teamId={tip.p.club_team_id} size={26} /></div>
                    <dl><dt>{y.label}</dt><dd>{formatStat(y, tip.yv)} <small>{rank(tip.yv, y, 'yv')} of {view.dots.length}</small></dd><dt>{x.label}</dt><dd>{formatStat(x, tip.xv)} <small>{rank(tip.xv, x, 'xv')} of {view.dots.length}</small></dd></dl>
                    <p>{tip.p.points?.toFixed(1)} pts, {tip.p.rebounds?.toFixed(1)} reb, {tip.p.assists?.toFixed(1)} ast in {tip.p.minutes?.toFixed(0)} min</p>
                  </div>
                )}
              </div>
            </div>
            <div className="scatter-foot">
              <span className="scatter-legend">{focused ? <>{teamNames.map((p) => <span key={p.club_team_id} style={colorVars(teamColor(p.club_team_id))}><i className="fill" />{p.club_full_name}</span>)}<span><i className="out-key" />Everyone else</span></> : Object.entries(COLORS).map(([name, color]) => <span key={name}><i style={{ background: color }} />{name}s</span>)}<span>Bigger dots play more minutes</span><span>Dashed lines are the average</span><span><i className="quad-key" />Better than average on both</span></span>
              {star && <span><b>{star.p.full_name}</b> {formatStat(x, star.xv)} {x.short} ({rank(star.xv, x, 'xv')} of {view.dots.length}), {formatStat(y, star.yv)} {y.short} ({rank(star.yv, y, 'yv')} of {view.dots.length})</span>}
            </div>
          </>
        )}
      </section>
    </>
  );
}
