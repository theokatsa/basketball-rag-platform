import { useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { BarTrend } from '../components/BarTrend';
import { LoadError, Loading, PageHead, PlayerCell, RowActions, Segmented, TeamLogo } from '../components/Common';
import { toZoneMap, useLeagueZones, ZoneCourt, ZoneList } from '../components/CourtZones';
import { Dropdown } from '../components/Dropdown';
import { BackIcon } from '../components/Icons';
import { Pagination, usePaged } from '../components/Pagination';
import { formatStat, statByKey } from '../stats';
import { teamColor, teamVars } from '../teamColors';
import type { TeamSide, TeamSummary, TeamZoneRow } from '../types';
import { useApi } from '../useApi';
import { usePersisted } from '../usePersisted';
import { formatDate, rankLabel } from '../utils';

type Metric = { key: string; label: string; get: (t: TeamSummary) => number; digits?: number; suffix?: string; signed?: boolean; lower?: boolean; neutral?: boolean };
const side = (key: string, label: string, where: 'offense' | 'defense', field: keyof TeamSide, options: Partial<Metric> = {}): Metric => ({ key, label, get: (t) => t[where][field], ...options });
const METRICS: Metric[] = [
  { key: 'win_pct', label: 'Winning %', get: (t) => t.win_pct * 100, suffix: '%' },
  { key: 'net', label: 'Net rating', get: (t) => t.net_rating, signed: true },
  side('off', 'Offensive rating', 'offense', 'off_rating'), side('def', 'Defensive rating', 'defense', 'off_rating', { lower: true }),
  { key: 'pace', label: 'Pace', get: (t) => t.pace, neutral: true }, side('ppg', 'Points', 'offense', 'points'), side('oppg', 'Points allowed', 'defense', 'points', { lower: true }),
  side('efg', 'Effective FG%', 'offense', 'efg', { suffix: '%' }), side('tov', 'Turnover %', 'offense', 'tov_pct', { suffix: '%', lower: true }), side('orb', 'Offensive rebound %', 'offense', 'oreb_pct', { suffix: '%' }), side('ftr', 'Free throws per 100 shots', 'offense', 'ft_rate'),
  side('defg', 'Opponent effective FG%', 'defense', 'efg', { suffix: '%', lower: true }), side('dtov', 'Turnovers forced %', 'defense', 'tov_pct', { suffix: '%' }), side('dorb', 'Opponent off. rebound %', 'defense', 'oreb_pct', { suffix: '%', lower: true }), side('dftr', 'Opponent free throws per 100 shots', 'defense', 'ft_rate', { lower: true }),
  side('fg', 'Field goal %', 'offense', 'fg_pct', { suffix: '%' }), side('three', 'Three-point %', 'offense', 'three_pct', { suffix: '%' }), side('rate3', 'Share of shots from three', 'offense', 'three_rate', { suffix: '%', neutral: true }), side('ft', 'Free throw %', 'offense', 'ft_pct', { suffix: '%' }),
  side('reb', 'Rebounds', 'offense', 'reb'), side('ast', 'Assists', 'offense', 'ast'), side('stl', 'Steals', 'offense', 'stl'), side('blk', 'Blocks', 'offense', 'blk'), side('tovs', 'Turnovers', 'offense', 'tov', { lower: true }),
];
/** Ready-made pairs for the map: name, up, across. */
const PAIRS: [string, string, string][] = [
  ['Offense and defense', 'def', 'off'], ['Shooting and opponent shooting', 'defg', 'efg'], ['Pace and offense', 'off', 'pace'], ['Three-point volume and accuracy', 'three', 'rate3'],
  ['Turnovers and turnovers forced', 'dtov', 'tov'], ['Rebounding at both ends', 'dorb', 'orb'], ['Assists and turnovers', 'tovs', 'ast'], ['Steals and blocks', 'blk', 'stl'], ['Free throws at both ends', 'dftr', 'ftr'], ['Wins and net rating', 'win_pct', 'net'],
];
const metric = (key: string) => METRICS.find((m) => m.key === key) ?? METRICS[0];
const show = (m: Metric, v: number) => `${m.signed && v > 0 ? '+' : ''}${v.toFixed(m.digits ?? 1)}${m.suffix ?? ''}`;
const rankIn = (all: TeamSummary[], m: Metric, team: TeamSummary) => 1 + all.filter((t) => (m.lower ? m.get(t) < m.get(team) : m.get(t) > m.get(team))).length;
const record = ([w, l]: [number, number]) => `${w}–${l}`;
const strength = (rank: number) => (30 - rank) / 29;

function useRosters() {
  const { players } = useApp();
  return useMemo(() => {
    const map = new Map<number, typeof players>();
    for (const p of players) if (p.club_team_id != null) map.set(p.club_team_id, [...(map.get(p.club_team_id) ?? []), p]);
    for (const roster of map.values()) roster.sort((a, b) => (b.points ?? 0) - (a.points ?? 0));
    return map;
  }, [players]);
}

export function Teams() {
  const { go, byId, loading } = useApp();
  const { data, error } = useApi<TeamSummary[]>('/team-summaries');
  const rosters = useRosters();
  const [view, setView] = usePersisted<'standings' | 'cards' | 'map'>('teams-view', 'standings');
  const [sort, setSort] = usePersisted('teams-sort', 'win_pct');
  const [hover, setHover] = useState<number | null>(null);
  const [upKey, setUp] = usePersisted('teams-map-up', 'def');
  const [acrossKey, setAcross] = usePersisted('teams-map-across', 'off');
  const [conference, setConference] = usePersisted<'all' | 'East' | 'West'>('teams-map-conf', 'all');
  if (error) return <LoadError message={error} />;
  if (!data || loading) return <><PageHead title="Teams" intro="" /><Loading height="40rem" /></>;
  const m = metric(sort);
  const sorted = [...data].sort((a, b) => (m.lower ? m.get(a) - m.get(b) : m.get(b) - m.get(a)));
  const top = (t: TeamSummary, key: string) => { const s = statByKey(key); const p = [...(rosters.get(t.team_id) ?? [])].filter((x) => (x.games_played ?? 0) >= 20).sort((a, b) => (s.get(b) ?? 0) - (s.get(a) ?? 0))[0]; return p && { p, v: formatStat(s, s.get(p)) }; };
  const mini = (t: TeamSummary) => <span className="mini-results" role="img" aria-label={`Last 10 games: ${record(t.last10)}`}>{t.results.slice(-10).map((r) => <i key={r.game_id} className={r.won ? 'w' : 'l'} />)}</span>;
  const standings = (conference: 'East' | 'West') => {
    const rows = data.filter((t) => t.conference === conference).sort((a, b) => b.wins - a.wins || b.margin - a.margin);
    return (
      <section className="panel standings" key={conference}>
        <div className="panel-header"><h2>{conference}ern Conference</h2></div>
        <table>
          <thead><tr><th scope="col">Team</th><th scope="col">W–L</th><th scope="col">GB</th><th scope="col">Off</th><th scope="col">Def</th><th scope="col">Net</th><th scope="col">Last 10</th></tr></thead>
          <tbody>{rows.map((t, i) => (
            <tr key={t.team_id} style={teamVars(t.team_id)} className={`team-row ${i === 5 || i === 9 ? 'cut' : ''}`} onClick={() => go('team', t.team_id)}>
              <th scope="row"><button type="button" className="player-link"><span className="rank-no">{i + 1}</span><TeamLogo teamId={t.team_id} size={30} /><span>{t.name}</span></button></th>
              <td><b>{t.wins}–{t.losses}</b></td><td>{i ? ((rows[0].wins - t.wins + t.losses - rows[0].losses) / 2).toFixed(1) : '–'}</td>
              <td>{t.offense.off_rating.toFixed(1)}</td><td>{t.defense.off_rating.toFixed(1)}</td><td className={t.net_rating > 0 ? 'pos' : 'neg'}>{show(metric('net'), t.net_rating)}</td><td>{mini(t)}</td>
            </tr>))}</tbody>
        </table>
        <p className="radar-note">Lines mark sixth place and tenth place. Ties are ordered by point difference, not the league’s tiebreakers.</p>
      </section>
    );
  };
  const W = 1000, H = 580, L = 70, R = 30, T = 24, B = 54;
  const up = metric(upKey), across = metric(acrossKey);
  const mean = (v: number[]) => v.reduce((sum, n) => sum + n, 0) / v.length;
  const xs = data.map(across.get), ys = data.map(up.get), mx = mean(xs), my = mean(ys);
  const range = (v: number[]) => { const lo = Math.min(...v), hi = Math.max(...v), pad = (hi - lo || 1) * 0.08; return [lo - pad, hi + pad] as const; };
  const [x0, x1] = range(xs), [y0, y1] = range(ys);
  // Axes turn around when lower is better, so the top right corner is always the good one.
  const px = (v: number) => L + (across.lower ? (x1 - v) / (x1 - x0) : (v - x0) / (x1 - x0)) * (W - L - R);
  const py = (v: number) => T + (up.lower ? (v - y0) / (y1 - y0) : (y1 - v) / (y1 - y0)) * (H - T - B);
  const steps = (a: number, b: number) => { const raw = (b - a) / 8, power = 10 ** Math.floor(Math.log10(raw)), size = [1, 2, 5, 10].map((k) => k * power).find((k) => k >= raw) ?? raw; const out: number[] = []; for (let v = Math.ceil(a / size) * size; v <= b + 1e-9; v += size) out.push(Number(v.toFixed(4))); return out; };
  const over = data.find((t) => t.team_id === hover);
  const shown = (t: TeamSummary) => conference === 'all' || t.conference === conference;
  const correlation = (() => { const cov = xs.reduce((sum, v, i) => sum + (v - mx) * (ys[i] - my), 0); return cov / Math.sqrt(xs.reduce((sum, v) => sum + (v - mx) ** 2, 0) * ys.reduce((sum, v) => sum + (v - my) ** 2, 0) || 1); })();
  const better = (x: Metric, v: number, than: number) => (x.lower ? v < than : v > than);
  const both = data.filter((t) => better(across, across.get(t), mx) && better(up, up.get(t), my));
  const plain = up.neutral || across.neutral; // a fast pace is a style, not a quality
  const axisName = (x: Metric) => `${x.label}${x.lower ? ' (lower is better)' : ''}`;
  const options = METRICS.map((x) => ({ value: x.key, label: x.label }));
  return (
    <>
      <PageHead title="Teams" intro="Standings, ratings and rosters for 2024-25."><Segmented label="View" value={view} options={[['standings', 'Standings'], ['cards', 'Team cards'], ['map', 'Team map']]} onChange={setView} /></PageHead>
      {view === 'standings' && <div className="two-col standings-grid">{standings('East')}{standings('West')}</div>}
      {view === 'cards' && (
        <>
          <div className="filter-bar"><Dropdown label="Sort by" showLabel value={sort} options={METRICS.map((x) => ({ value: x.key, label: x.label }))} onChange={setSort} search="Search statistics" /></div>
          <div className="team-grid rich">
            {sorted.map((t, i) => {
              const scorer = top(t, 'points');
              return (
                <button type="button" className="team-card rich team-tint" style={teamVars(t.team_id)} key={t.team_id} onClick={() => go('team', t.team_id)}>
                  <span className="team-card-logo"><TeamLogo teamId={t.team_id} size={150} /></span>
                  <span className="team-card-head"><TeamLogo teamId={t.team_id} size={64} /><span><small>{t.city}</small><b>{t.nickname}</b></span><span className="team-card-rank">{i + 1}</span></span>
                  <span className="team-card-big"><strong>{t.wins}–{t.losses}</strong><span><b>{show(m, m.get(t))}</b><small>{m.label}</small></span></span>
                  <span className="team-card-bars">{([['Offense', 'off'], ['Defense', 'def']] as const).map(([label, key]) => { const r = rankIn(data, metric(key), t); return <span key={key}><small>{label}</small><i><em style={{ width: `${4 + strength(r) * 96}%` }} /></i><b>{rankLabel(r)}</b></span>; })}</span>
                  <span className="team-card-foot">{mini(t)}{scorer && <small>{scorer.p.full_name} {scorer.v}</small>}</span>
                </button>
              );
            })}
          </div>
        </>
      )}
      {view === 'map' && (
        <>
          <div className="filter-bar"><div className="preset-row">{PAIRS.map(([name, a, b]) => <button type="button" className="chip" aria-pressed={upKey === a && acrossKey === b} key={name} onClick={() => { setUp(a); setAcross(b); }}>{name}</button>)}</div></div>
          <section className="panel explorer-panel">
            <div className="explorer-top">
              <div className="axis-pick"><Dropdown label="Up" showLabel value={upKey} options={options} onChange={setUp} search="Search statistics" /><button type="button" className="swap-button" title="Swap the two axes" aria-label="Swap the two axes" onClick={() => { setUp(acrossKey); setAcross(upKey); }}>⇄</button><Dropdown label="Across" showLabel value={acrossKey} options={options} onChange={setAcross} search="Search statistics" /></div>
              <Segmented label="Conference" value={conference} options={[['all', 'Both conferences'], ['East', 'East'], ['West', 'West']]} onChange={setConference} />
            </div>
            <div className="scatter-scroll"><div className="chart-stage">
              <svg viewBox={`0 0 ${W} ${H}`} className="scatter" role="img" aria-label={`${up.label} against ${across.label} for 30 teams`}>
                <rect x={px(mx)} y={T} width={W - R - px(mx)} height={py(my) - T} className="quad-best" />
                {steps(x0, x1).map((v) => <g key={v}><line x1={px(v)} x2={px(v)} y1={T} y2={H - B} className="grid" /><text x={px(v)} y={H - B + 20} textAnchor="middle">{v}</text></g>)}
                {steps(y0, y1).map((v) => <g key={v}><line x1={L} x2={W - R} y1={py(v)} y2={py(v)} className="grid" /><text x={L - 8} y={py(v) + 4} textAnchor="end">{v}</text></g>)}
                <line x1={px(mx)} x2={px(mx)} y1={T} y2={H - B} className="mean" /><line x1={L} x2={W - R} y1={py(my)} y2={py(my)} className="mean" />
                <text x={W - R - 10} y={T + 20} textAnchor="end" className="quad-text">{plain ? 'Above average on both' : 'Better at both'}</text><text x={L + 10} y={H - B - 12} className="quad-text">{plain ? 'Below average on both' : 'Worse at both'}</text>
                <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" className="axis">{axisName(across)}</text>
                <text transform={`translate(18 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" className="axis">{axisName(up)}</text>
                {[...data].sort((a, b) => Number(a.team_id === hover) - Number(b.team_id === hover)).map((t) => {
                  const x = px(across.get(t)), y = py(up.get(t)), big = hover === t.team_id ? 26 : 18;
                  return <g key={t.team_id} className="team-dot" style={teamVars(t.team_id)} opacity={!shown(t) ? 0.12 : hover == null || hover === t.team_id ? 1 : 0.35} onMouseEnter={() => setHover(t.team_id)} onMouseLeave={() => setHover(null)} onClick={() => go('team', t.team_id)}><circle cx={x} cy={y} r={big + 3} className="team-ring" /><image href={`https://cdn.nba.com/logos/nba/${t.team_id}/primary/L/logo.svg`} x={x - big + 4} y={y - big + 4} width={(big - 4) * 2} height={(big - 4) * 2}><title>{t.name}</title></image></g>;
                })}
              </svg>
              {over && <div className={`scatter-tip ${px(across.get(over)) > W * 0.65 ? 'flip' : ''} ${py(up.get(over)) > H * 0.6 ? 'up' : ''}`} style={{ left: `${(px(across.get(over)) / W) * 100}%`, top: `${(py(up.get(over)) / H) * 100}%` }}><b>{over.name}, {over.wins}–{over.losses}</b>{[up, across].map((x) => <span key={x.key}>{x.label} {show(x, x.get(over))}, {rankLabel(rankIn(data, x, over))}</span>)}<span>Net rating {show(metric('net'), over.net_rating)}</span></div>}
            </div></div>
            <div className="scatter-foot"><span>Dashed lines are the league average.{plain ? '' : ' Top right is always best.'} Click a logo to open the team.</span><span>Correlation <b>{correlation.toFixed(2)}</b></span></div>
            <p className="radar-note">{plain ? 'Above average on both' : 'Better than average at both'}: {both.length ? both.sort((a, b) => b.net_rating - a.net_rating).map((t) => t.nickname).join(', ') : 'nobody'}.</p>
          </section>
        </>
      )}
      {view !== 'map' && <p className="radar-note">{byId.size} players. A player counts for the last team of their 2024-25 season.</p>}
    </>
  );
}

const PROFILE: [string, string[]][] = [
  ['Offense', ['off', 'efg', 'tov', 'orb', 'ftr', 'three', 'rate3', 'ast']],
  ['Defense', ['def', 'defg', 'dtov', 'dorb', 'dftr', 'stl', 'blk', 'oppg']],
];
const ROSTER = ['minutes', 'points', 'rebounds', 'assists', 'steals', 'blocks', 'ts', 'three', 'usage', 'net_rating'];

type Targets = { needs: { label: string; z: number }[]; targets: { player_id: number; score: number; reasons: string[] }[] };

/** Players elsewhere who are strong where this team is weak. */
function TargetPanel({ id }: { id: number }) {
  const { byId } = useApp();
  const [position, setPosition] = usePersisted('targets-pos', '');
  const { data, error } = useApi<Targets>(`/insights/teams/${id}/targets?limit=6${position ? `&position=${position}` : ''}`);
  if (error) return null;
  const weak = data?.needs.filter((n) => n.z < -0.3).slice(0, 3).map((n) => n.label) ?? [];
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Players who would help</h2><p>{weak.length ? `Strong where this squad is weakest: ${weak.join(', ')}` : 'No clear weakness against other squads'}</p></div><Segmented label="Position" value={position} options={[['', 'All'], ['Guard', 'Guards'], ['Forward', 'Forwards'], ['Center', 'Centers']]} onChange={setPosition} /></div>
      {!data ? <Loading height="9rem" /> : <div className="ideal-grid">{data.targets.map((t) => { const p = byId.get(t.player_id); return p && <article key={t.player_id}><div className="result-head"><PlayerCell player={p} /><RowActions player={p} /></div><p>Brings {t.reasons.join(', ')}.</p><small>Overall score {t.score} of 100</small></article>; })}</div>}
      <p className="radar-note">A statistical match. Contracts and availability are not in the database.</p>
    </section>
  );
}

/** Teams with the same way of playing, whatever their strength. */
function SimilarTeams({ id, all }: { id: number; all: TeamSummary[] }) {
  const { go } = useApp();
  const { data, error } = useApi<{ team_id: number; similarity: number; shared: string[] }[]>(`/insights/teams/${id}/similar?limit=4`);
  if (error) return null;
  return (
    <section className="panel">
      <div className="panel-header"><div><h2>Teams that play alike</h2><p>By pace, shot selection and how possessions are won, not by strength</p></div></div>
      {!data ? <Loading height="7rem" /> : <div className="ideal-grid">{data.map((s) => { const t = all.find((x) => x.team_id === s.team_id); return t && <article key={t.team_id}><button type="button" className="player-link" onClick={() => go('team', t.team_id)}><TeamLogo teamId={t.team_id} size={34} /><span className="player-name">{t.name}</span></button><p>{s.shared.length ? `Both: ${s.shared.join(', ')}.` : 'Alike overall, with no single trait standing out.'}</p><small>{Math.round(s.similarity * 100)}% match, {t.wins}–{t.losses}</small></article>; })}</div>}
      <p className="radar-note">A typical pair of teams scores 25%.</p>
    </section>
  );
}

export function Team({ id }: { id: number }) {
  const { loading, error, totals, go, openGame } = useApp();
  const { data, error: teamError } = useApi<TeamSummary[]>('/team-summaries');
  const roster = useRosters().get(id) ?? [];
  const [end, setEnd] = useState<'offense' | 'defense'>('offense');
  const shots = useApi<TeamZoneRow[]>(`/shots/team-zones?side=${end}`);
  const league = useLeagueZones();
  const [hover, setHover] = useState<string | null>(null);
  const [where, setWhere] = useState<'all' | 'home' | 'away'>('all');
  const [result, setResult] = useState<'all' | 'won' | 'lost'>('all');
  const [sort, setSort] = useState('points');
  const zones = useMemo(() => (shots.data ? toZoneMap(shots.data.filter((r) => r.team_id === id)) : null), [shots.data, id]);
  const team = data?.find((t) => t.team_id === id);
  const games = useMemo(() => [...(team?.results ?? [])].reverse().filter((g) => (where === 'all' || g.home === (where === 'home')) && (result === 'all' || g.won === (result === 'won'))), [team, where, result]);
  const paged = usePaged(games, 10, `${id}${where}${result}`);
  if (error || teamError) return <LoadError message={(error ?? teamError)!} />;
  if (loading || !data) return <Loading height="30rem" />;
  if (!team) return <LoadError message="This team was not found." />;
  const byTeam = new Map(data.map((t) => [t.team_id, t]));
  const place = data.filter((t) => t.conference === team.conference && (t.wins > team.wins || (t.wins === team.wins && t.margin > team.margin))).length + 1;
  const sortStat = statByKey(sort);
  const rows = [...roster].sort((a, b) => ((sortStat.get(b, totals[b.player_id]) ?? -Infinity) - (sortStat.get(a, totals[a.player_id]) ?? -Infinity)) * (sortStat.lowerIsBetter ? -1 : 1));
  const best = team.results.reduce((a, b) => (b.points - b.opponent_points > a.points - a.opponent_points ? b : a));
  const worst = team.results.reduce((a, b) => (b.points - b.opponent_points < a.points - a.opponent_points ? b : a));
  const tiles: [string, string, string][] = [
    ['Home', record(team.home), ''], ['Away', record(team.away), ''], ['Within 5 points', record(team.close), ''], ['Last 10', record(team.last10), team.streak > 0 ? `Won last ${team.streak}` : `Lost last ${-team.streak}`],
    ...(['net', 'off', 'def', 'pace'] as const).map((k) => [metric(k).label, show(metric(k), metric(k).get(team)), rankLabel(rankIn(data, metric(k), team))] as [string, string, string]),
  ];
  return (
    <>
      <div className="detail-topbar team-back"><button type="button" className="back-button" onClick={() => go('teams')}><BackIcon />All teams</button></div>
      <header className="team-hero rich team-tint" style={teamVars(team.team_id)}>
        <span className="team-hero-ghost"><TeamLogo teamId={team.team_id} size={420} /></span>
        <TeamLogo teamId={team.team_id} size={130} />
        <div><h1>{team.name}</h1><p>{rankLabel(place)} in the {team.conference}. Founded {team.founded}.</p></div>
        <p className="team-record"><strong>{team.wins}–{team.losses}</strong><span>{(team.win_pct * 100).toFixed(1)}% won</span></p>
        <dl className="stat-tiles team-tiles">{tiles.map(([label, value, note]) => <div key={label}><dt>{label}</dt><dd>{value}</dd><dd className="tile-note">{note || ' '}</dd></div>)}</dl>
      </header>
      <div className="team-leaders">
        {['points', 'rebounds', 'assists', 'steals', 'blocks'].map((key) => {
          const stat = statByKey(key);
          const leader = [...roster].filter((p) => (p.games_played ?? 0) >= 20).sort((a, b) => (stat.get(b) ?? 0) - (stat.get(a) ?? 0))[0];
          return leader && <div className="panel" key={key}><small>{stat.label}</small><strong>{formatStat(stat, stat.get(leader))}</strong><PlayerCell player={leader} note="" /></div>;
        })}
      </div>
      <section className="panel">
        <div className="panel-header"><div><h2>Season, game by game</h2><p>Winning margin, wins in colour. The line is the average of the last 5 games. Click a bar for the box score.</p></div></div>
        <BarTrend label="Margin" signed tone="result" points={team.results.map((g) => ({ key: g.game_id, value: g.points - g.opponent_points, won: g.won, title: `${g.home ? 'vs' : 'at'} ${byTeam.get(g.opponent_id)?.name ?? ''}`, note: `${formatDate(g.date)}, ${g.points}–${g.opponent_points}` }))} onPick={openGame} height={240} color={teamColor(id).glow} />
        <p className="radar-note">Biggest win: {best.points}–{best.opponent_points} {best.home ? 'vs' : 'at'} {byTeam.get(best.opponent_id)?.nickname}. Biggest loss: {worst.points}–{worst.opponent_points} {worst.home ? 'vs' : 'at'} {byTeam.get(worst.opponent_id)?.nickname}.</p>
      </section>
      <div className="two-col">
        {PROFILE.map(([title, keys]) => (
          <section className="panel" key={title}>
            <div className="panel-header"><div><h2>{title}</h2><p>Rank among 30 teams</p></div></div>
            <div className="rank-rows">{keys.map((k) => { const x = metric(k), r = rankIn(data, x, team); return <div key={k}><span>{x.label}</span><b>{show(x, x.get(team))}</b><i><em className={r <= 10 ? 'high' : r > 20 ? 'low' : ''} style={{ width: `${4 + strength(r) * 96}%` }} /></i><small>{rankLabel(r)}</small></div>; })}</div>
          </section>
        ))}
      </div>
      <section className="panel">
        <div className="panel-header"><div><h2>{end === 'offense' ? 'Where they shoot' : 'What they give up'}</h2><p>FG% against the league average from each zone</p></div><Segmented label="End of the court" value={end} options={[['offense', 'Their shots'], ['defense', 'Opponents’ shots']]} onChange={setEnd} /></div>
        {shots.error ? <p className="status error">{shots.error}</p> : !zones ? <Loading /> : (
          <div className="shot-chart"><ZoneCourt label={`${team.name}, ${end}, by zone`} zones={zones} league={league} hover={hover} onHover={setHover} /><ZoneList zones={zones} league={league} hover={hover} onHover={setHover} /></div>
        )}
      </section>
      <section className="panel">
        <div className="panel-header"><h2>Roster</h2><span className="count-label">{roster.length} players</span></div>
        <div className="detail-records-scroll open">
          <table className="detail-records-table roster-table">
            <thead><tr><th scope="col">Player</th><th scope="col">Age</th><th scope="col">GP</th>{ROSTER.map((k) => <th scope="col" key={k} title={statByKey(k).label} className={sort === k ? 'sorted' : ''} aria-sort={sort === k ? 'descending' : 'none'}><button type="button" className="sort-heading" onClick={() => setSort(k)}>{statByKey(k).short}</button></th>)}<th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>{rows.map((p) => <tr key={p.player_id}><th scope="row"><PlayerCell player={p} note={p.position ?? ''} /></th><td>{formatStat(statByKey('age'), statByKey('age').get(p, totals[p.player_id]))}</td><td>{p.games_played}</td>{ROSTER.map((k) => <td key={k} className={sort === k ? 'sorted-cell' : ''}>{formatStat(statByKey(k), statByKey(k).get(p, totals[p.player_id]))}</td>)}<td><RowActions player={p} /></td></tr>)}</tbody>
          </table>
        </div>
      </section>
      <TargetPanel id={id} />
      <SimilarTeams id={id} all={data} />
      <section className="panel">
        <div className="panel-header"><div><h2>Results</h2><p>{games.length} games</p></div><div className="panel-tools"><Segmented label="Place" value={where} options={[['all', 'All'], ['home', 'Home'], ['away', 'Away']]} onChange={setWhere} /><Segmented label="Result" value={result} options={[['all', 'All'], ['won', 'Won'], ['lost', 'Lost']]} onChange={setResult} /></div></div>
        <ul className="result-list">{paged.items.map((g) => <li key={g.game_id}><button type="button" onClick={() => openGame(g.game_id)}><span className="result-date">{formatDate(g.date)}</span><span className={`result-mark ${g.won ? 'w' : 'l'}`}>{g.won ? 'W' : 'L'}</span><span className="result-opponent">{g.home ? 'vs' : 'at'} <TeamLogo teamId={g.opponent_id} size={26} /> {byTeam.get(g.opponent_id)?.name}</span><b>{g.points}–{g.opponent_points}</b></button></li>)}</ul>
        <Pagination page={paged.page} pageCount={paged.pageCount} onPage={paged.onPage} label="Result pages" />
      </section>
    </>
  );
}
