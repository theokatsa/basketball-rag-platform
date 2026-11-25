import { useEffect, useMemo, useState } from 'react';
import { useApp } from '../AppContext';
import { formatStat, qualifies, statByKey } from '../stats';
import type { Fit, Matchup, PlayerDetailData, SimilarPlayerResult } from '../types';
import { useApi } from '../useApi';
import { teamVars } from '../teamColors';
import { fractionPct, radarMetrics, rankLabel } from '../utils';
import { Avatar } from './Avatar';
import { Loading, PlayerCell, Segmented, TeamLogo } from './Common';
import { signed } from './CourtZones';
import { useTeamList } from './Dropdown';
import { GameLogs } from './GameLogs';
import { BackIcon, CompareIcon, HeartIcon } from './Icons';
import { RadarChart, toneFor } from './RadarChart';
import { ShotChart } from './ShotChart';

type Props = { detail: PlayerDetailData | null; loading: boolean; error: string | null; onBack: () => void };
type Section = 'overview' | 'shots' | 'games' | 'similar' | 'fit';
const SECTIONS: [Section, string][] = [['overview', 'Overview'], ['shots', 'Shot chart'], ['games', 'Game log'], ['similar', 'Similar players'], ['fit', 'Teammates and opponents']];

/** The bars show other things than the radar: efficiency, rates and impact. */
const BARS: [string, string[]][] = [
  ['Scoring', ['ts', 'efg', 'usage', 'fta', 'threes']],
  ['Creating', ['ast_pct', 'ast_to', 'turnovers']],
  ['Rebounding', ['oreb_pct', 'dreb_pct']],
  ['Defense', ['dfg_diff', 'def_rating', 'pf']],
  ['Impact', ['net_rating', 'pie', 'production']],
];
const formatHeight = (h: string) => (/^\d+-\d+$/.test(h) ? `${h.replace('-', "'")}"` : h);

/** Percentile ranks among rotation players (20 games, 12 minutes), optionally at one position. */
function Strengths({ detail }: { detail: PlayerDetailData }) {
  const { players, totals, byId } = useApp();
  const [scope, setScope] = useState<'position' | 'all'>('position');
  const { player, profile, stats } = detail;
  const latest = stats[0];
  const position = profile.position;
  const main = position?.split('-')[0] ?? '';
  const active = position ? scope : 'all';
  const row = byId.get(player.id);
  const groups = useMemo(() => {
    if (!row) return [];
    const pool = players.filter((p) => (p.games_played ?? 0) >= 20 && (p.minutes ?? 0) >= 12 && (active === 'all' || (p.position ?? '').split('-')[0] === main));
    return BARS.map(([title, keys]) => [title, keys.flatMap((key) => {
      const s = statByKey(key), t = totals[player.id], v = s.get(row, t);
      if (v == null || !qualifies(s, t)) return [];
      const values = pool.filter((p) => qualifies(s, totals[p.player_id])).map((p) => s.get(p, totals[p.player_id])).filter((x): x is number => x != null);
      const beaten = values.filter((x) => (s.lowerIsBetter ? x > v : x < v)).length;
      return [{ s, v, share: values.length ? beaten / values.length : 0, rank: values.length - beaten, of: values.length }];
    })] as const).filter(([, list]) => list.length);
  }, [players, totals, row, player.id, active, main]);
  if (!latest) return null;
  return (
    <section className="panel wide">
      <div className="panel-header">
        <div><h2>Strengths</h2><p>{active === 'position' ? `Compared with other ${main.toLowerCase()}s` : 'Compared with every player'}</p></div>
        {position && <Segmented label="Comparison group" value={scope} options={[['position', `${main}s`], ['all', 'League']]} onChange={setScope} />}
      </div>
      <div className="profile-body wide">
        <div><h3 className="sub-head">Production</h3><RadarChart series={[{ name: player.full_name, color: '#ff6a13', metrics: radarMetrics(latest, active) }]} label={`Percentile radar chart for ${player.full_name}`} /><p className="radar-note">Box score totals per game.</p></div>
        <div><h3 className="sub-head">Efficiency and impact</h3>
          <div className="strength-groups">
            {groups.map(([title, list]) => (
              <div key={title}><h4>{title}</h4>{list.map(({ s, v, share, rank, of }) => <div key={s.key} className="strength-row" title={`${rank} of ${of}`}><span>{s.label}</span><b>{formatStat(s, v)}<small>{share >= 0.5 ? `top ${Math.max(1, Math.round((1 - share) * 100))}%` : `bottom ${Math.max(1, Math.round(share * 100))}%`}</small></b><i><em style={{ width: `${Math.max(2, share * 100)}%`, background: toneFor(share) }} /></i></div>)}</div>
            ))}
            {!groups.length && <p className="status">Too few minutes for these rates.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function Similar({ similar, playerId }: { similar: SimilarPlayerResult[]; playerId: number }) {
  const { byId, user, compareIds, setCompareIds, go } = useApp();
  const [chosen, setChosen] = useState(0);
  const [viewed, setViewed] = useState<{ player_id: number; viewers: number; audience: number }[] | null>(null);
  useEffect(() => {
    let cancelled = false;
    // Asked fresh every time: this list changes as people use the site.
    fetch(`/api/players/${playerId}/also-viewed`).then((r) => (r.ok ? r.json() : [])).then((list) => { if (!cancelled) setViewed(list); }).catch(() => { if (!cancelled) setViewed([]); });
    return () => { cancelled = true; };
  }, [playerId]);
  const own = byId.get(playerId);
  const focus = similar[chosen];
  const other = focus && byId.get(focus.player_id);
  const show = (v: number, percent: boolean) => `${v.toFixed(1)}${percent ? '%' : ''}`;
  const compare = (id: number) => { setCompareIds([playerId, id, ...compareIds.filter((c) => c !== playerId && c !== id)].slice(0, 2)); go('compare'); };
  return (
    <>
      <section className="panel wide">
        <div className="panel-header"><div><h2>Similar players</h2><p>Closest statistical profiles. Pick one to see why.</p></div></div>
        {!similar.length ? <p className="status">No similar profiles available.</p> : (
          <div className="similar-split">
            <div className="similar-pick" role="group" aria-label="Similar players">
              {similar.map((r, i) => { const p = byId.get(r.player_id); return p && <button type="button" key={r.player_id} aria-pressed={i === chosen} onClick={() => setChosen(i)}><Avatar key={p.nba_player_id} name={p.full_name} nbaPlayerId={p.nba_player_id} className="player-thumb" /><span><b>{p.full_name}</b><small>{p.club}, {p.position}</small></span><strong>{Math.round(r.similarity * 100)}%</strong></button>; })}
            </div>
            {focus && other && own && (
              <div className="why">
                <div className="why-head"><h3>Why {other.full_name}?</h3><button type="button" className="ghost-button" onClick={() => compare(other.player_id)}><CompareIcon />Full comparison</button></div>
                {focus.shared_traits.length > 0 && <p>Shared strengths: {focus.shared_traits.join(', ')}.</p>}
                <table className="why-table">
                  <thead><tr><th scope="col">Closest numbers</th><th scope="col">{own.full_name}</th><th scope="col">{other.full_name}</th><th scope="col">Match</th></tr></thead>
                  <tbody>{focus.alike.map((t) => <tr key={t.label}><th scope="row">{t.label}</th><td>{show(t.own, t.percent)}</td><td>{show(t.other, t.percent)}</td><td><i><em style={{ width: `${t.closeness * 100}%` }} /></i></td></tr>)}</tbody>
                  {focus.apart.length > 0 && <><thead><tr><th scope="col" colSpan={4}>Where they differ</th></tr></thead><tbody>{focus.apart.map((t) => <tr key={t.label}><th scope="row">{t.label}</th><td>{show(t.own, t.percent)}</td><td>{show(t.other, t.percent)}</td><td><i className="low"><em style={{ width: `${Math.max(4, t.closeness * 100)}%` }} /></i></td></tr>)}</tbody></>}
                </table>
                <p className="radar-note">The match percentage compares twelve statistics measured against the league that season. Percentages on few attempts are pulled toward average.</p>
                <PlayerCell player={other} note="Open profile" />
              </div>
            )}
          </div>
        )}
      </section>
      <section className="panel wide">
        <div className="panel-header"><div><h2>Users who viewed {own?.full_name ?? 'this player'} also viewed</h2><p>From pages opened in the same visit by signed-in users</p></div></div>
        {viewed == null ? <Loading height="5rem" /> : viewed.length ? <div className="suggest-grid">{viewed.map((v) => { const p = byId.get(v.player_id); return p && <PlayerCell key={v.player_id} player={p} note={`${v.viewers} of ${v.audience} ${v.audience === 1 ? 'viewer' : 'viewers'}`} />; })}</div> : <p className="status">{user ? 'Nothing yet. It fills up as people look at several players in one visit.' : 'Nothing yet. Sign in and your visits help build this list.'}</p>}
      </section>
    </>
  );
}

function FitPanels({ playerId }: { playerId: number }) {
  const { byId } = useApp();
  const teams = useTeamList();
  const { data, error } = useApi<Fit>(`/insights/players/${playerId}/fit`);
  if (error) return <section className="panel wide"><p className="status">No teammate and opponent data for this player.</p></section>;
  if (!data) return <div className="wide"><Loading height="24rem" /></div>;
  const matchups = (title: string, note: string, rows: Matchup[]) => (
    <div className="fit-list"><h3>{title}</h3><p>{note}</p>
      {rows.length ? <ul>{rows.slice(0, 5).map((m) => { const p = byId.get(m.other_id); return p && <li key={m.other_id}><PlayerCell player={p} note={`${m.points.toFixed(0)} pts, ${m.fgm}/${m.fga} FG in ${m.possessions.toFixed(0)} possessions`} /><span className="fit-figure"><b>{m.per100.toFixed(0)}</b><small>usually {m.expected.toFixed(0)}</small></span></li>; })}</ul> : <p className="status">Not enough tracked possessions.</p>}
    </div>
  );
  const pairs = [...data.pairs];
  const teamRow = (t: Fit['teams'][number]) => { const team = teams.find((x) => x.id === t.team_id); return <li key={t.team_id}><span className="team-inline"><TeamLogo teamId={t.team_id} size={30} /><span><b>{team?.name}</b><small>{t.games} games, {t.points.toFixed(1)} pts, {t.rebounds.toFixed(1)} reb, {t.assists.toFixed(1)} ast</small></span></span><span className="fit-figure"><b>{t.game_score.toFixed(1)}</b><small>Game Score</small></span></li>; };
  const pairRow = (x: Fit['pairs'][number]) => { const p = byId.get(x.other_id); return p && <li key={`${x.other_id}${x.nba_team_id}`}><PlayerCell player={p} note={`${x.minutes.toFixed(0)} minutes together`} /><span className="fit-figure"><b className={x.net_rating > 0 ? 'up' : 'down'}>{signed(x.net_rating)}</b><small>net per 100</small></span></li>; };
  return (
    <>
      <section className="panel wide">
        <div className="panel-header"><div><h2>Ideal teammates</h2><p>Players on other teams who cover weaker skills without needing the same ball</p></div></div>
        <div className="ideal-grid">{data.ideal_teammates.map((t) => { const p = byId.get(t.player_id); return p && <article key={t.player_id}><PlayerCell player={p} /><p>{t.reasons.length ? `Brings ${t.reasons.join(', ')}.` : 'Strong all-round fit.'}</p><small>{t.usage.toFixed(0)}% usage, overall score {t.score}</small></article>; })}</div>
        <p className="radar-note">Skills below average that a teammate should cover: {data.skills.filter((s) => s.z < -0.25).sort((a, b) => a.z - b.z).slice(0, 4).map((s) => s.label).join(', ') || 'none stand out'}. This is a statistical fit, not a trained model.</p>
      </section>
      {pairs.length > 0 && (
        <section className="panel wide">
          <div className="panel-header"><div><h2>Actual pairings</h2><p>Team net rating with both on the court, at least 200 minutes</p></div></div>
          <div className="fit-cols"><div className="fit-list"><h3>Best</h3><ul>{pairs.slice(0, 5).map(pairRow)}</ul></div><div className="fit-list"><h3>Worst</h3><ul>{pairs.slice(Math.max(5, pairs.length - 5)).reverse().map(pairRow)}</ul></div></div>
        </section>
      )}
      <section className="panel wide">
        <div className="panel-header"><div><h2>Best and worst opponents</h2><p>Points per 100 possessions in tracked matchups of at least 25 possessions. Small samples count less in the order.</p></div></div>
        <div className="fit-cols four">
          {matchups('Easiest defenders', 'Scores more than usual against them', data.easiest_defenders)}
          {matchups('Toughest defenders', 'Scores less than usual against them', data.toughest_defenders)}
          {matchups('Defends well', 'They score less than usual', data.best_stops)}
          {matchups('Struggles to defend', 'They score more than usual', data.worst_stops)}
        </div>
      </section>
      {data.teams.length > 5 && (
        <section className="panel wide">
          <div className="panel-header"><div><h2>Teams faced</h2><p>Average Game Score, at least 2 games</p></div></div>
          <div className="fit-cols"><div className="fit-list"><h3>Best against</h3><ul>{data.teams.slice(0, 5).map(teamRow)}</ul></div><div className="fit-list"><h3>Worst against</h3><ul>{data.teams.slice(-5).reverse().map(teamRow)}</ul></div></div>
        </section>
      )}
    </>
  );
}

export function PlayerDetail({ detail, loading, error, onBack }: Props) {
  const { favoriteIds, toggleFavorite, compareWith, byId, go } = useApp();
  const [section, setSection] = useState<Section>('overview');
  if (!detail) {
    return (
      <section className="player-detail">
        <div className="detail-topbar"><button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button></div>
        {loading && !error
          ? <div className="skeleton-block" aria-busy="true" aria-label="Loading player"><span className="skeleton" style={{ height: '13rem' }} /><span className="skeleton" style={{ height: '6rem' }} /><span className="skeleton" style={{ height: '20rem' }} /></div>
          : <div className="panel"><p className="status error" role="alert">{error ?? 'Player not found.'}</p></div>}
      </section>
    );
  }
  const { player, profile, stats, logs, shots, similar } = detail;
  const favorite = favoriteIds.includes(player.id);
  const row = byId.get(player.id);
  const latest = stats[0];
  const facts = [row?.club_full_name, profile.position, profile.age != null && `${profile.age} years old`, profile.height && formatHeight(profile.height), profile.weight && `${profile.weight} lb`].filter(Boolean);
  const tiles: [string, string, number | null][] = latest
    ? [
        ['Points', latest.points.toFixed(1), latest.points_rank], ['Rebounds', latest.rebounds.toFixed(1), latest.rebounds_rank], ['Assists', latest.assists.toFixed(1), latest.assists_rank],
        ['Steals', latest.steals.toFixed(1), latest.steals_rank], ['Blocks', latest.blocks.toFixed(1), latest.blocks_rank], ['Turnovers', latest.turnovers.toFixed(1), null],
        ['Minutes', latest.minutes.toFixed(1), null], ['FG%', fractionPct(latest.field_goal_pct), latest.field_goal_rank], ['3P%', fractionPct(latest.three_point_pct), latest.three_point_rank], ['FT%', fractionPct(latest.free_throw_pct), latest.free_throw_rank],
      ]
    : [];
  return (
    <section className="player-detail">
      <div className="detail-topbar">
        <button type="button" className="back-button" onClick={onBack}><BackIcon />Back</button>
        <div className="detail-actions">
          <button type="button" className="ghost-button accent" onClick={() => setSection('shots')}>Shot chart</button>
          <button type="button" className="ghost-button" onClick={() => go('report', player.id)}>Scouting report</button>
          <button type="button" className="ghost-button" onClick={() => compareWith(player.id)}><CompareIcon />Compare with…</button>
          <button type="button" className="ghost-button" aria-pressed={favorite} onClick={() => toggleFavorite(player.id)}><HeartIcon filled={favorite} />{favorite ? 'Shortlisted' : 'Shortlist'}</button>
        </div>
      </div>

      <header className="detail-hero team-tint" style={teamVars(row?.club_team_id)}>
        <span className="detail-hero-logo"><TeamLogo teamId={row?.club_team_id ?? null} size={360} /></span>
        <div className="detail-hero-main">
          <Avatar name={player.full_name} nbaPlayerId={player.nba_player_id} className="detail-mark" />
          <div className="detail-title">
            <h2>{player.full_name}</h2>
            <ul className="fact-list">{facts.map((fact) => <li key={String(fact)}>{fact}</li>)}</ul>
          </div>
          {latest && <p className="hero-season">{latest.season}<span>{latest.games_played} games</span></p>}
        </div>
        {latest
          ? <dl className="stat-tiles">{tiles.map(([label, value, rank]) => <div key={label} className={rank != null && rank <= 25 ? 'elite' : ''}><dt>{label}</dt><dd>{value}</dd><dd className="tile-note">{rank != null ? `${rankLabel(rank)} in league` : 'per game'}</dd></div>)}</dl>
          : <p className="status">No season statistics available.</p>}
      </header>

      <nav className="section-tabs" aria-label="Profile sections">{SECTIONS.map(([key, label]) => <button type="button" key={key} aria-current={section === key ? 'true' : undefined} onClick={() => setSection(key)}>{label}</button>)}</nav>

      <div className="detail-grid">
        {section === 'overview' && <Strengths detail={detail} />}
        {section === 'shots' && <section className="panel wide"><div className="panel-header"><div><h2>Shot chart</h2></div></div>{shots ? <ShotChart shots={shots} /> : <span className="skeleton" style={{ height: '30rem' }} />}</section>}
        {section === 'games' && (logs ? <GameLogs logs={logs} /> : <section className="panel wide"><span className="skeleton" style={{ height: '20rem' }} /></section>)}
        {section === 'similar' && <Similar similar={similar} playerId={player.id} />}
        {section === 'fit' && <FitPanels playerId={player.id} />}
      </div>
    </section>
  );
}
