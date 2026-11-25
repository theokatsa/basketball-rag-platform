import { useMemo } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import { useApp } from '../AppContext';
import { Avatar } from '../components/Avatar';
import { BarTrend } from '../components/BarTrend';
import { LoadError, Loading, PlayerCell, TeamLogo } from '../components/Common';
import { signed, toZoneMap, useLeagueZones, ZoneCourt, zoneDiff, ZONES } from '../components/CourtZones';
import { useTeamList } from '../components/Dropdown';
import { BackIcon } from '../components/Icons';
import { logStat } from '../components/logStats';
import { RadarChart } from '../components/RadarChart';
import { formatStat, qualifies, statByKey } from '../stats';
import type { StatDef } from '../stats';
import { teamVars } from '../teamColors';
import type { Fit, GameLog, Matchup, PlayerProfile, PlayerScore, PlayerZoneRow, SeasonStat, SimilarPlayerResult } from '../types';
import { useApi } from '../useApi';
import { formatDate, radarMetrics, rankLabel } from '../utils';

const GROUPS: [string, string[]][] = [
  ['Scoring', ['points', 'usage', 'ts', 'efg', 'fta', 'threes']],
  ['Creating', ['assists', 'ast_pct', 'ast_to', 'turnovers']],
  ['Rebounding', ['rebounds', 'oreb_pct', 'dreb_pct']],
  ['Defense', ['steals', 'blocks', 'dfg_diff', 'def_rating', 'pf']],
  ['Impact', ['net_rating', 'plus_minus', 'pie', 'production']],
];
const LINE = ['points', 'rebounds', 'assists', 'steals', 'blocks', 'turnovers', 'minutes', 'fg', 'three', 'ft', 'ts', 'usage'];
const SPLIT = ['minutes', 'points', 'rebounds', 'assists', 'turnovers', 'ts', 'three', 'plus_minus', 'game_score'];
const joinWords = (words: string[]) => (words.length > 1 ? `${words.slice(0, -1).join(', ')} and ${words[words.length - 1]}` : words[0] ?? '');
const formatHeight = (h: string) => (/^\d+-\d+$/.test(h) ? `${h.replace('-', "'")}"` : h);
type Ranked = { s: StatDef; v: number; share: number; rank: number; of: number };

function Part({ title, note, children, wide }: { title: string; note?: string; children: ReactNode; wide?: boolean }) {
  return <section className={wide ? 'report-part wide' : 'report-part'}><h2>{title}</h2>{note && <p className="report-note">{note}</p>}{children}</section>;
}

export function Report({ id }: { id: number }) {
  const { byId, players, totals, loading, error, open, openGame } = useApp();
  const teams = useTeamList();
  const stats = useApi<SeasonStat[]>(`/players/${id}/season-stats`);
  const profile = useApi<PlayerProfile>(`/players/${id}/profile`);
  const similar = useApi<SimilarPlayerResult[]>(`/players/${id}/similar?limit=6`);
  const logs = useApi<GameLog[]>(`/players/${id}/game-logs`);
  const shots = useApi<PlayerZoneRow[]>('/shots/zones');
  const fit = useApi<Fit>(`/insights/players/${id}/fit`);
  const scores = useApi<PlayerScore[]>('/insights/scores');
  const league = useLeagueZones();
  const zones = useMemo(() => (shots.data ? toZoneMap(shots.data.filter((r) => r.player_id === id)) : null), [shots.data, id]);
  const player = byId.get(id);
  const main = (player?.position ?? '').split('-')[0];
  /** Every number against regular players at the same position. */
  const ranked = useMemo(() => {
    if (!player) return [];
    const t = totals[id];
    const pool = players.filter((p) => (p.games_played ?? 0) >= 20 && (p.minutes ?? 0) >= 12 && (!main || (p.position ?? '').split('-')[0] === main));
    return GROUPS.map(([title, keys]) => [title, keys.flatMap((key): Ranked[] => {
      const s = statByKey(key), v = s.get(player, t);
      if (v == null || !qualifies(s, t)) return [];
      const values = pool.filter((p) => qualifies(s, totals[p.player_id])).map((p) => s.get(p, totals[p.player_id])).filter((x): x is number => x != null);
      const beaten = values.filter((x) => (s.lowerIsBetter ? x > v : x < v)).length;
      return [{ s, v, share: values.length ? beaten / values.length : 0, rank: values.length - beaten, of: values.length }];
    })] as const).filter(([, list]) => list.length);
  }, [player, players, totals, id, main]);
  const failed = error ?? stats.error ?? logs.error ?? shots.error;
  if (failed) return <LoadError message={failed} />;
  if (loading || !stats.data || !logs.data || !zones || (!profile.data && !profile.error) || (!similar.data && !similar.error) || (!fit.data && !fit.error)) return <Loading height="40rem" />;
  const season = stats.data[0];
  if (!player || !season) return <LoadError message="There are no statistics for this player." />;

  const t = totals[id];
  const games = logs.data;
  const score = scores.data?.find((x) => x.player_id === id);
  const all = ranked.flatMap(([, list]) => list);
  const find = (key: string) => all.find((r) => r.s.key === key);
  const lower = (text: string) => (text === 'Game Score' || text.slice(0, 2) === text.slice(0, 2).toUpperCase() ? text : text.charAt(0).toLowerCase() + text.slice(1));
  // Usage and fouls describe a role rather than a quality.
  const judged = all.filter((r) => !['usage', 'fta', 'plus_minus'].includes(r.s.key));
  const top = [...judged].sort((a, b) => b.share - a.share).filter((r) => r.share >= 0.75).slice(0, 5);
  const bottom = [...judged].sort((a, b) => a.share - b.share).filter((r) => r.share <= 0.33).slice(0, 5);
  const zoneRows = ZONES.flatMap((z) => { const own = zones.get(z.key), diff = zoneDiff(own, league?.get(z.key)); return own && own.att >= 20 && diff != null ? [{ z, own, diff }] : []; }).sort((a, b) => b.diff - a.diff);
  const bestZone = zoneRows[0], worstZone = zoneRows[zoneRows.length - 1];
  const taken = ZONES.reduce((sum, z) => sum + (zones.get(z.key)?.att ?? 0), 0);
  const leagueTaken = league ? ZONES.reduce((sum, z) => sum + (league.get(z.key)?.att ?? 0), 0) : 0;
  const diet = (['Paint', 'Mid-range', 'Three'] as const).map((group) => {
    const sum = (map: typeof zones) => ZONES.filter((z) => z.group === group).reduce((acc, z) => { const x = map.get(z.key); return { att: acc.att + (x?.att ?? 0), made: acc.made + (x?.made ?? 0) }; }, { att: 0, made: 0 });
    const own = sum(zones), base = league ? sum(league) : { att: 0, made: 0 };
    return { group, own, share: taken ? own.att / taken : 0, leagueShare: leagueTaken ? base.att / leagueTaken : 0, pct: own.att ? own.made / own.att : null, leaguePct: base.att ? base.made / base.att : null };
  });
  const quality = ZONES.reduce((acc, z) => { const own = zones.get(z.key), base = league?.get(z.key), worth = z.group === 'Three' ? 3 : 2; if (!own || !base) return acc; return { points: acc.points + own.made * worth, expected: acc.expected + own.att * (base.made / base.att) * worth }; }, { points: 0, expected: 0 });
  const making = taken ? (quality.points - quality.expected) / taken : 0;
  const average = (list: GameLog[], key: string) => { const s = logStat(key), v = s.average(list); return v == null ? '–' : s.text(v); };
  const recent = games.slice(0, 10);
  const pointsOf = (list: GameLog[]) => logStat('points').average(list) ?? 0;
  const swing = games.length >= 20 ? pointsOf(recent) - pointsOf(games.slice(10)) : 0;
  const spread = Math.sqrt(games.reduce((sum, l) => sum + (l.points - pointsOf(games)) ** 2, 0) / Math.max(1, games.length));

  const usage = find('usage'), assist = find('ast_pct'), threes = diet[2];
  const role = [
    (usage?.share ?? 0) >= 0.8 ? 'a first option on offense' : (usage?.share ?? 0) >= 0.5 ? 'a regular part of the offense' : 'a low-usage player who finishes what others create',
    (assist?.share ?? 0) >= 0.8 && 'a main creator for teammates',
    threes.share >= 0.5 ? 'most shots come from three' : diet[0].share >= 0.6 ? 'lives in the paint' : diet[1].share >= 0.35 ? 'leans on the mid-range' : 'spreads shots around the floor',
  ].filter((x): x is string => Boolean(x));
  const strengths = [
    ...top.map((r) => `${rankLabel(r.rank)} of ${r.of} ${main ? `${main.toLowerCase()}s` : 'players'} in ${lower(r.s.label)} (${formatStat(r.s, r.v)}).`),
    bestZone && bestZone.diff > 2 && `Shoots ${signed(bestZone.diff)} points above the league from ${bestZone.z.label.toLowerCase()} (${bestZone.own.made}/${bestZone.own.att}).`,
    making > 0.05 && `Makes ${making.toFixed(2)} more points per shot than an average shooter would from the same spots.`,
    swing >= 3 && `In form: ${signed(swing)} points per game over the last 10.`,
  ].filter((x): x is string => Boolean(x));
  const concerns = [
    ...bottom.map((r) => `${rankLabel(r.rank)} of ${r.of} ${main ? `${main.toLowerCase()}s` : 'players'} in ${lower(r.s.label)} (${formatStat(r.s, r.v)}).`),
    worstZone && worstZone !== bestZone && worstZone.diff < -2 && `Shoots ${signed(worstZone.diff)} points against the league from ${worstZone.z.label.toLowerCase()} (${worstZone.own.made}/${worstZone.own.att}).`,
    making < -0.05 && `Makes ${Math.abs(making).toFixed(2)} fewer points per shot than an average shooter from the same spots.`,
    swing <= -3 && `Out of form: ${signed(swing)} points per game over the last 10.`,
    season.games_played < 50 && `Played ${season.games_played} games, so the sample is limited.`,
  ].filter((x): x is string => Boolean(x));
  const splits: [string, GameLog[]][] = [['Season', games], ['Last 5', games.slice(0, 5)], ['Last 10', recent], ['Last 20', games.slice(0, 20)], ['Home', games.filter((l) => l.is_home)], ['Away', games.filter((l) => !l.is_home)], ['Wins', games.filter((l) => l.won)], ['Losses', games.filter((l) => !l.won)]];
  const chron = [...games].reverse();
  const highs = [...games].sort((a, b) => (logStat('game_score').value(b) ?? 0) - (logStat('game_score').value(a) ?? 0)).slice(0, 5);
  const facts = [player.club_full_name, player.position, (t?.season_age ?? player.age) != null && `${t?.season_age ?? player.age} years old in ${season.season}`, profile.data?.height && formatHeight(profile.data.height), profile.data?.weight && `${profile.data.weight} lb`, `${season.games_played} games`].filter(Boolean).join(', ');
  const matchups = (title: string, rows: Matchup[]) => <div><h3>{title}</h3>{rows.length ? <ul className="report-list">{rows.slice(0, 4).map((m) => { const p = byId.get(m.other_id); return p && <li key={m.other_id}><PlayerCell player={p} note={`${m.possessions.toFixed(0)} possessions, ${m.fgm}/${m.fga} FG`} /><span><b>{m.per100.toFixed(0)}</b><small>usually {m.expected.toFixed(0)}</small></span></li>; })}</ul> : <p className="report-note">Not enough tracked possessions.</p>}</div>;
  const teamRows = (rows: Fit['teams']) => <ul className="report-list">{rows.map((x) => { const team = teams.find((k) => k.id === x.team_id); return <li key={x.team_id}><span className="team-inline"><TeamLogo teamId={x.team_id} size={28} /><span><b>{team?.name}</b><small>{x.games} games, {x.points.toFixed(1)} pts</small></span></span><span><b>{x.game_score.toFixed(1)}</b><small>Game Score</small></span></li>; })}</ul>;
  const tone = (share: number) => (share >= 0.8 ? 'elite' : share >= 0.5 ? 'good' : share >= 0.25 ? 'mid' : 'low');
  return (
    <>
      <div className="detail-topbar report-actions"><button type="button" className="back-button" onClick={() => open(id)}><BackIcon />Back to profile</button><button type="button" className="submit-button" onClick={() => window.print()}>Print or save as PDF</button></div>
      <article className="report" style={teamVars(player.club_team_id)}>
        <header className="report-head">
          <span className="report-ghost"><TeamLogo teamId={player.club_team_id} size={380} /></span>
          <Avatar key={player.nba_player_id} name={player.full_name} nbaPlayerId={player.nba_player_id} className="report-photo" />
          <div><p>Scouting report, {season.season}</p><h1>{player.full_name}</h1><p>{facts}</p></div>
          {score && <dl className="report-scores">{([['Overall', score.score], ['Offense', score.offense], ['Defense', score.defense]] as const).map(([label, v]) => <div key={label}><dd style={{ '--share': v / 100 } as CSSProperties}><b>{v}</b></dd><dt>{label}</dt></div>)}</dl>}
        </header>
        <dl className="report-stats">{LINE.map((key) => { const s = statByKey(key), v = s.get(player, t), r = find(key); return <div key={key}><dt>{s.short}</dt><dd>{formatStat(s, v)}</dd><dd className="tile-note">{r ? `${rankLabel(r.rank)} of ${r.of}` : ' '}</dd></div>; })}</dl>
        <p className="report-note under">Ranks are among {main ? `${main.toLowerCase()}s` : 'players'} with 20 games and 12 minutes a game. Scores run from 0 to 100 among rotation players.</p>

        <div className="report-body">
          <Part title="Summary" wide><p className="report-lead">{player.full_name} is {joinWords(role.slice(0, -1))}; {role[role.length - 1]}. Averages {season.points.toFixed(1)} points, {season.rebounds.toFixed(1)} rebounds and {season.assists.toFixed(1)} assists in {season.minutes.toFixed(0)} minutes{t?.net_rating != null ? `, and the team is ${signed(t.net_rating)} points per 100 possessions with them on the court` : ''}. Scoring varies by about {spread.toFixed(1)} points from night to night.</p></Part>
          <Part title="Strengths">{strengths.length ? <ul className="report-points good">{strengths.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="report-note">No number stands out at this position.</p>}</Part>
          <Part title="Concerns">{concerns.length ? <ul className="report-points bad">{concerns.map((x) => <li key={x}>{x}</li>)}</ul> : <p className="report-note">No clear statistical weakness.</p>}</Part>

          <Part title="Every skill, ranked" note={`Against other ${main ? `${main.toLowerCase()}s` : 'players'}`} wide>
            <div className="report-skills">{ranked.map(([title, list]) => <div key={title}><h3>{title}</h3>{list.map(({ s, v, share, rank, of }) => <div className="skill-row" key={s.key}><span>{s.label}</span><b>{formatStat(s, v)}</b><i><em className={tone(share)} style={{ width: `${Math.max(3, share * 100)}%` }} /></i><small>{rankLabel(rank)} of {of}</small></div>)}</div>)}</div>
          </Part>

          <Part title="Production profile"><RadarChart series={[{ name: player.full_name, color: '#ff6a13', metrics: radarMetrics(season, 'all') }]} label="Percentile radar" /><p className="report-note">Box score totals against the whole league.</p></Part>
          <Part title="Shooting by zone"><ZoneCourt label="Shooting by zone" zones={zones} league={league} /><p className="report-note">Orange is above the league average, blue below.</p></Part>

          <Part title="Shot selection" wide>
            <table className="report-table"><thead><tr><th scope="col">Area</th><th scope="col">Shots</th><th scope="col">Share of shots</th><th scope="col">League share</th><th scope="col">Made</th><th scope="col">League made</th><th scope="col">Difference</th></tr></thead>
              <tbody>{diet.map((d) => { const gap = d.pct != null && d.leaguePct != null ? (d.pct - d.leaguePct) * 100 : null; return <tr key={d.group}><th scope="row">{d.group}</th><td>{d.own.made}/{d.own.att}</td><td>{(d.share * 100).toFixed(0)}%</td><td>{(d.leagueShare * 100).toFixed(0)}%</td><td>{d.pct == null ? '–' : `${(d.pct * 100).toFixed(1)}%`}</td><td>{d.leaguePct == null ? '–' : `${(d.leaguePct * 100).toFixed(1)}%`}</td><td className={gap == null ? '' : gap > 0 ? 'up' : 'down'}>{gap == null ? '–' : signed(gap)}</td></tr>; })}</tbody></table>
            {taken > 0 && <p className="report-facts"><span><b>{(quality.expected / taken).toFixed(2)}</b> shot quality: what an average shooter would score per shot</span><span><b>{(quality.points / taken).toFixed(2)}</b> actual points per shot</span><span><b className={making > 0 ? 'up' : 'down'}>{signed(making, 2)}</b> shot making</span></p>}
            <div className="report-zones"><div><h3>Best zones</h3>{zoneRows.slice(0, 3).map(({ z, own, diff }) => <p key={z.key}><span>{z.label}</span>{own.made}/{own.att}<b className={diff > 0 ? 'up' : 'down'}>{signed(diff)}</b></p>)}</div><div><h3>Weakest zones</h3>{[...zoneRows].reverse().slice(0, 3).map(({ z, own, diff }) => <p key={z.key}><span>{z.label}</span>{own.made}/{own.att}<b className={diff > 0 ? 'up' : 'down'}>{signed(diff)}</b></p>)}</div></div>
          </Part>

          <Part title="Season, game by game" note="Game Score. The line is the average of the last 5 games." wide><BarTrend label="Game Score" digits={1} height={220} points={chron.map((l) => ({ key: l.nba_game_id ?? '', value: logStat('game_score').value(l), won: l.won, title: `${l.is_home ? 'vs' : '@'} ${l.opponent}, ${formatDate(l.game_date)}`, note: `${l.points} pts, ${l.rebounds} reb, ${l.assists} ast` }))} onPick={openGame} /></Part>
          <Part title="Splits" wide>
            <div className="report-scroll"><table className="report-table"><thead><tr><th scope="col">Games</th><th scope="col">Number</th>{SPLIT.map((k) => <th scope="col" key={k}>{logStat(k).label}</th>)}</tr></thead><tbody>{splits.map(([label, list]) => <tr key={label}><th scope="row">{label}</th><td>{list.length}</td>{SPLIT.map((k) => <td key={k}>{average(list, k)}</td>)}</tr>)}</tbody></table></div>
          </Part>
          <Part title="Best games" wide><ul className="report-games">{highs.map((l) => <li key={l.nba_game_id}><button type="button" onClick={() => l.nba_game_id && openGame(l.nba_game_id)}><strong>{l.points}</strong><span><TeamLogo teamId={l.opponent_id} size={24} />{l.is_home ? 'vs' : '@'} {l.opponent}</span><small>{l.rebounds} reb, {l.assists} ast, {l.field_goals_made}/{l.field_goals_attempted} FG</small><small>{formatDate(l.game_date)}, {l.won ? 'won' : 'lost'} {l.team_points}–{l.opponent_points}</small></button></li>)}</ul></Part>

          {fit.data && (
            <>
              <Part title="Individual matchups" note="Points per 100 possessions when one guards the other, at least 25 possessions" wide><div className="report-four">{matchups('Easiest defenders', fit.data.easiest_defenders)}{matchups('Toughest defenders', fit.data.toughest_defenders)}{matchups('Defends well', fit.data.best_stops)}{matchups('Struggles to defend', fit.data.worst_stops)}</div></Part>
              {fit.data.teams.length > 5 && <Part title="Teams faced" note="Average Game Score, at least 2 games" wide><div className="report-four two"><div><h3>Best against</h3>{teamRows(fit.data.teams.slice(0, 4))}</div><div><h3>Worst against</h3>{teamRows(fit.data.teams.slice(-4).reverse())}</div></div></Part>}
              <Part title="Ideal teammates" note="A statistical fit: covers weaker skills without needing the same ball"><ul className="report-list">{fit.data.ideal_teammates.slice(0, 5).map((x) => { const p = byId.get(x.player_id); return p && <li key={x.player_id}><PlayerCell player={p} note={x.reasons.length ? `Brings ${x.reasons.join(', ')}` : 'Strong all-round fit'} /><span><b>{x.score}</b><small>overall</small></span></li>; })}</ul></Part>
            </>
          )}
          <Part title="Comparable players" note="Closest statistical profiles"><ul className="report-list">{(similar.data ?? []).slice(0, 5).map((r) => { const p = byId.get(r.player_id); return p && <li key={r.player_id}><PlayerCell player={p} note={r.shared_traits.slice(0, 2).join(', ') || undefined} /><span><b>{Math.round(r.similarity * 100)}%</b><small>match</small></span></li>; })}</ul></Part>
        </div>
      </article>
    </>
  );
}
